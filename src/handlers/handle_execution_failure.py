import json
from typing import List
from typing import TypedDict

from aws_lambda_powertools.utilities.idempotency import IdempotencyConfig
from aws_lambda_powertools.utilities.idempotency import idempotent
from aws_lambda_typing.context import Context
from jit_utils.lambda_decorators import exception_handler
from jit_utils.lambda_decorators.exception_handler import logger
from jit_utils.logger import logger_customer_id
from jit_utils.logger.logger import add_label
from jit_utils.models.execution import ExecutionStatus
from jit_utils.utils.aws.idempotency import get_persistence_layer

from src.lib.cores.execution_events import send_task_completion_event
from src.lib.cores.execution_events import send_trigger_execution_failed_event
from src.lib.cores.utils.parsing_utils import try_parse_dict
from src.lib.data.executions_manager import ExecutionsManager
from src.lib.models.execution_models import BaseExecutionIdentifiers
from src.lib.models.execution_models import FailedTriggersEvent


class ExecutionFailureUnexpectedEvent(Exception):
    def __init__(self):
        super().__init__("Got an unexpected event to handle - not handling")


class OnFailureLambdaDestinationRequestContext(TypedDict):
    requestId: str
    functionArn: str
    condition: str
    approximateInvokeCount: int


class OnFailureLambdaDestinationResponsePayload(TypedDict):
    errorMessage: str
    errorType: str
    stackTrace: List[str]


class OnFailureLambdaDestinationEvent(TypedDict):
    """
    TypedDict representing the event for the on failure destination of a lambda invocation.
    Declared here since no suitable event in aws_lambda_typing
    """
    requestContext: OnFailureLambdaDestinationRequestContext
    requestPayload: dict
    responsePayload: OnFailureLambdaDestinationResponsePayload


def get_original_lambda_input(original_event: dict) -> dict:
    if "detail" in original_event:
        return original_event["detail"]
    elif "Records" in original_event:
        image = original_event["Records"][0]["dynamodb"]["NewImage"]
        return ExecutionsManager().parse_dynamodb_item_to_python_dict(image)
    else:
        raise ExecutionFailureUnexpectedEvent()


@idempotent(
    persistence_store=get_persistence_layer(),
    config=IdempotencyConfig(
        event_key_jmespath="requestContext.requestId",
        raise_on_no_idempotency_key=True,
    ),
)
@exception_handler(exceptions=[ExecutionFailureUnexpectedEvent])
@logger_customer_id(auto=True)
def handler(event: OnFailureLambdaDestinationEvent, context: Context) -> None:
    """
    This function is called when a possible error happens during the execution flow, and for some reason we can't revive
    for this error.
    This function will gracefully cancel the failed execution (that will be reflected both in our BE and in UI).

    This function can handle executions that have already started being processed in the system, as well as executions
    that didn't.
    Supported events:
    * HandleExistingExecutionFailureEvent (for any case the execution exists in the DB)
    * BulkTriggerExecutionEvent/TriggerExecutionEvent (for trigger execution when execution doesn't exist in the DB)
    """
    logger.info(event)
    original_event = event["requestPayload"]
    error_message = event["responsePayload"]["errorMessage"]
    request_context = event["requestContext"]
    logger.info(f"handling execution failure {error_message=}, for {request_context=}")

    original_lambda_input = get_original_lambda_input(original_event)

    if execution_details := try_parse_dict(original_lambda_input, BaseExecutionIdentifiers):
        """
        We got an event about existing failed execution in the system
        """
        add_label("customer_id", execution_details.tenant_id)
        add_label("jit_event_id", execution_details.jit_event_id)
        add_label("execution_id", execution_details.execution_id)
        logger.info(f"Execution exists, {execution_details=}")
        send_task_completion_event(
            completion_status=ExecutionStatus.FAILED,
            tenant_id=execution_details.tenant_id,
            execution_id=execution_details.execution_id,
            jit_event_id=execution_details.jit_event_id,
            error_message="Failed during the execution flow",
        )
        return

    if failed_triggers_event := try_parse_dict(json.loads(error_message), FailedTriggersEvent):
        """
        We got an event about failing execution triggers
        """
        failed_triggers = failed_triggers_event.failed_triggers
        add_label("customer_id", failed_triggers[0].context.jit_event.tenant_id)
        add_label("jit_event_id", failed_triggers[0].context.jit_event.jit_event_id)
        add_label("execution_id", "")  # Empty string, so it won't be tagged with the last value
        logger.info(f"Got failed triggers event with message {failed_triggers_event.failure_message}")
        for failed_trigger in failed_triggers:
            send_trigger_execution_failed_event(failed_trigger)
        return

    raise ExecutionFailureUnexpectedEvent()

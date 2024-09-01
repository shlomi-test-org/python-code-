from datetime import datetime
from typing import Union

from aws_lambda_powertools.utilities.idempotency import IdempotencyConfig
from aws_lambda_powertools.utilities.idempotency import idempotent
from aws_lambda_typing.context import Context
from aws_lambda_typing.events import DynamoDBStreamEvent
from aws_lambda_typing.events import EventBridgeEvent
from dateutil.parser import parse
from jit_utils.lambda_decorators import feature_flags_init_client
from jit_utils.lambda_decorators import lambda_warmup_handler
from jit_utils.lambda_decorators import limit_lambda_invocations
from jit_utils.logger import custom_labels
from jit_utils.logger import CustomLabel
from jit_utils.logger import logger
from jit_utils.logger import logger_customer_id
from jit_utils.logger.logger import add_label
from jit_utils.utils.aws.idempotency import get_persistence_layer
from pydantic import ValidationError

from src.lib.cores.executions_core import complete_execution, retry_execution_if_needed, \
    fetch_execution_from_base_execution_ids
from src.lib.data.executions_manager import ExecutionsManager
from src.lib.exceptions import ExecutionNotExistException, StatusTransitionException
from src.lib.exceptions import MultipleCompletesExceptions
from jit_utils.models.execution import Execution, BaseExecutionIdentifiers
from src.lib.models.execution_models import UpdateRequest


@logger_customer_id(auto=True)
@lambda_warmup_handler
@idempotent(
    persistence_store=get_persistence_layer(),
    config=IdempotencyConfig(
        # id is the unique identifier from EventBridge event, the fallback is from DynamoDB stream
        event_key_jmespath='id || Records[0].eventID',
        raise_on_no_idempotency_key=True,
    ),
)
@custom_labels([CustomLabel(field_name='execution_id', label_name='execution_id', auto=True),
                CustomLabel(field_name='jit_event_id', label_name='jit_event_id', auto=True)])
@limit_lambda_invocations(max_invocations=5000)
@feature_flags_init_client()
def complete_execution_handler(event: Union[EventBridgeEvent, DynamoDBStreamEvent], context: Context) -> None:
    """
    This function is called when 2 conditions are met:
    1. A control has reported that it has completed (successfully or not)
    2. The control findings have been uploaded (or an error occurred while uploading)

    We apply idempotency protection on this lambda, to avoid clearing more resources than it needs to,
    and to avoid sending multiple continuation events to EventBridge.
    """
    logger.info(f"Completing execution of {event=}")

    if 'detail-type' in event:
        add_label('event_source', 'event_bridge')
        event: EventBridgeEvent
        update_request = UpdateRequest(**event['detail'])
        execution = fetch_execution_from_base_execution_ids(BaseExecutionIdentifiers(**update_request.dict()))
    else:
        add_label('event_source', 'dynamodb_stream')
        event: DynamoDBStreamEvent
        new_image = event['Records'][0]['dynamodb']['NewImage']

        parsed_execution = ExecutionsManager().parse_dynamodb_item_to_python_dict(new_image)
        logger.info(f'{parsed_execution=}')
        execution = Execution(**parsed_execution)
        logger.info(f"{execution=}")

        now = execution.completed_at or datetime.utcnow().isoformat()
        update_request = UpdateRequest(
            tenant_id=execution.tenant_id,
            jit_event_id=execution.jit_event_id,
            execution_id=execution.execution_id,
            status=execution.control_status,
            completed_at=now,
            completed_at_ts=int(parse(now).timestamp()),
        )

    # If the execution is in a state that we should retry, we will retry it
    did_retry, failure = retry_execution_if_needed(execution, update_request.errors)
    if did_retry:
        return
    elif failure:
        update_request.error_body = failure.json()
        update_request.run_id = failure.run_id
    try:
        updated_execution = complete_execution(update_request, execution)
        logger.info(f'{updated_execution=}')
    except (ValidationError, ExecutionNotExistException):
        logger.exception("Complete execution event corrupted")
    except MultipleCompletesExceptions:
        logger.warning("We attempted to complete the execution more than once")
    except StatusTransitionException:
        logger.warning("We attempted to complete the execution with a status that is not allowed")

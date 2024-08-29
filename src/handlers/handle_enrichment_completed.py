import json

from aws_lambda_powertools.utilities.idempotency import IdempotencyConfig
from aws_lambda_powertools.utilities.idempotency import idempotent
from aws_lambda_typing.events import EventBridgeEvent
from jit_utils.aws_clients.sfn import SFNClient
from jit_utils.lambda_decorators import lambda_warmup_handler
from jit_utils.logger import custom_labels
from jit_utils.logger import CustomLabel
from jit_utils.logger import logger
from jit_utils.logger import logger_customer_id
from jit_utils.models.execution import ExecutionStatus
from jit_utils.utils.aws.idempotency import get_persistence_layer
from jit_utils.utils.encoding import MultiTypeJSONEncoder

from jit_utils.models.execution import Execution


@logger_customer_id(auto=True)
@lambda_warmup_handler
@idempotent(
    persistence_store=get_persistence_layer(),
    config=IdempotencyConfig(
        event_key_jmespath='id',
        raise_on_no_idempotency_key=True,
    ),
)
@custom_labels(
    [
        CustomLabel(field_name='execution_id', label_name='execution_id', auto=True),
        CustomLabel(field_name='jit_event_id', label_name='jit_event_id', auto=True),
    ]
)
def handler(event: EventBridgeEvent, __) -> None:
    """
    This function is invoked when an execution is completed.
    Sends task success/failure to Step Function from trigger service.
    """
    logger.info(f"Handling enrichment completed {event=}")
    #  Add the reason it failed and add it to the task failure condition
    execution = Execution(**event['detail'])

    # TODO: remove this condition once we have all executions with task_token
    task_token = execution.task_token or (
            execution.additional_attributes and execution.additional_attributes.get('task_token')
    )
    if not task_token:
        logger.error(
            f"Execution {execution.execution_id} has no task token, cannot send task success/failure to step function"
        )
        return

    if execution.status == ExecutionStatus.COMPLETED and execution.job_output:
        SFNClient().send_task_success(
            task_token=task_token,
            output=json.dumps(execution.job_output)
        )
    else:
        execution_json = json.dumps(
            execution.dict(exclude_none=True, exclude={'context', 'steps', 'additional_attributes'}),
            cls=MultiTypeJSONEncoder,
        )
        SFNClient().send_task_failure(
            task_token=task_token,
            cause=execution_json,
            error=f"Control failed with status {execution.control_status}"
        )

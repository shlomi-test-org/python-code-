from aws_lambda_powertools.utilities.idempotency import IdempotencyConfig
from aws_lambda_powertools.utilities.idempotency import idempotent
from aws_lambda_typing.events import EventBridgeEvent
from jit_utils.lambda_decorators import feature_flags_init_client
from jit_utils.lambda_decorators import lambda_warmup_handler
from jit_utils.logger import custom_labels
from jit_utils.logger import CustomLabel
from jit_utils.logger import logger
from jit_utils.logger import logger_customer_id
from jit_utils.models.execution import ExecutionStatus
from jit_utils.utils.aws.idempotency import get_persistence_layer

from src.lib.cores.execution_events import send_task_completion_event
from src.lib.cores.executions_core import dispatched_request_core
from src.lib.exceptions import ExecutionNotExistException
from src.lib.exceptions import StatusTransitionException
from src.lib.models.execution_models import ExecutionDispatchUpdateEvent


@logger_customer_id(auto=True)
@lambda_warmup_handler
@idempotent(
    persistence_store=get_persistence_layer(),
    config=IdempotencyConfig(
        event_key_jmespath='id',
        raise_on_no_idempotency_key=True,
    ),
)
@feature_flags_init_client()
@custom_labels([CustomLabel(field_name='execution_id', label_name='execution_id', auto=True),
                CustomLabel(field_name='jit_event_id', label_name='jit_event_id', auto=True)])
def handler(event: EventBridgeEvent, __) -> None:
    """
    This function is called when a job is dispatched.
    """
    logger.info(f"Updating execution status to Dispatched. {event=}")
    event = ExecutionDispatchUpdateEvent(**event["detail"])

    try:
        dispatched_request_core(event)
    except StatusTransitionException as ex:
        logger.warning(f"Got StatusTransitionException={ex}, skipping operation")
    except ExecutionNotExistException as ex:
        # Logging the error, so we will be notified in the errors channel
        logger.exception(ex)

        send_task_completion_event(
            completion_status=ExecutionStatus.FAILED,
            tenant_id=event.tenant_id,
            execution_id=event.execution_id,
            jit_event_id=event.jit_event_id,
            error_message="There was an error during the execution process",
        )

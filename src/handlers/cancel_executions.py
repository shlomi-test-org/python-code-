from aws_lambda_powertools.utilities.idempotency import IdempotencyConfig
from aws_lambda_powertools.utilities.idempotency import idempotent
from aws_lambda_typing.events import EventBridgeEvent
from jit_utils.lambda_decorators.exception_handler import logger
from jit_utils.logger import logger_customer_id
from jit_utils.utils.aws.idempotency import get_persistence_layer
from pydantic import ValidationError

from src.lib.cores.cancel_event_handler.cancel_event_handler_factory import CancelEventTypes
from src.lib.cores.cancel_event_handler.cancel_event_handler_factory import get_cancel_event_handler


@idempotent(
    persistence_store=get_persistence_layer(),
    config=IdempotencyConfig(
        event_key_jmespath="id",
        raise_on_no_idempotency_key=True,
    ),
)
@logger_customer_id(auto=True)
def handler(event: EventBridgeEvent, __) -> None:
    """
    This function is called to handle system events that should cancel executions and remove them from the execution
    queue (no need to run these executions anymore).
    """
    event_type = event["detail-type"]
    event_body = event["detail"]
    logger.info(f"Handling {event_type=}")

    try:
        cancel_event_type = CancelEventTypes(event_type)
        cancel_event_handler = get_cancel_event_handler(cancel_event_type, event_body)
        cancel_event_handler.handle()
    except ValidationError:
        logger.exception(f"Got bad payload {event_body} for this cancel event")
    except ValueError:
        logger.exception(f"Got unsupported {event_type=}")

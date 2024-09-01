from aws_lambda_typing.context import Context
from aws_lambda_typing.events import EventBridgeEvent

from jit_utils.aws_clients.decorators import eventbridge_deferred_message_handler
from jit_utils.logger import logger, CustomLabel, custom_labels
from jit_utils.lambda_decorators import exception_handler, lambda_warmup_handler, feature_flags_init_client

from src.lib.cores.event_translation.rerun_event_translation import rerun_idempotency_config
from src.lib.cores.translate_core import dispatch_jit_event_from_raw_event


@exception_handler()
@lambda_warmup_handler
@feature_flags_init_client()
@eventbridge_deferred_message_handler
@custom_labels(
    [
        CustomLabel(
            field_name='event_type',
            label_name='webhook_event_type',
            auto=True
        ),
    ]
)
def handler(event: EventBridgeEvent, context: Context) -> None:
    logger.info("Got event to translate to jit event")
    logger.debug(f"{event=}")
    rerun_idempotency_config.register_lambda_context(lambda_context=context)  # type: ignore
    dispatch_jit_event_from_raw_event(event)

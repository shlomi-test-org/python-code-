from aws_lambda_powertools.utilities.idempotency import IdempotencyConfig
from aws_lambda_powertools.utilities.idempotency import idempotent
from jit_utils.lambda_decorators import exception_handler
from jit_utils.lambda_decorators import feature_flags_init_client
from jit_utils.lambda_decorators import lambda_warmup_handler
from jit_utils.lambda_decorators import logger_cleanup_sensitive_data
from jit_utils.logger import custom_labels
from jit_utils.logger import CustomLabel
from jit_utils.logger import logger
from jit_utils.logger import logger_customer_id
from jit_utils.utils.aws.idempotency import get_persistence_layer

from src.lib.cores.executions_core import dispatch_executions

from src.lib.data.executions_manager import ExecutionsManager
from src.lib.models.execution_models import MultipleExecutionsIdentifiers


@logger_customer_id(auto=True)
@lambda_warmup_handler
@idempotent(
    persistence_store=get_persistence_layer(),
    config=IdempotencyConfig(
        event_key_jmespath='id',
        raise_on_no_idempotency_key=True,
    ),
)
@exception_handler()
@feature_flags_init_client()
@custom_labels(
    [
        CustomLabel(field_name='jit_event_id', label_name='jit_event_id', auto=True),
    ]
)
@logger_cleanup_sensitive_data()
def handler(event, __) -> None:
    logger.info(f"Starting job runner lambda with {event=}")
    execution_identifiers = MultipleExecutionsIdentifiers(**event["detail"])
    executions = ExecutionsManager().get_executions_for_multiple_identifiers(execution_identifiers)
    dispatch_executions(executions)

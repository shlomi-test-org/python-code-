from aws_lambda_powertools.utilities.idempotency import IdempotencyConfig
from aws_lambda_powertools.utilities.idempotency import idempotent
from aws_lambda_typing.events import EventBridgeEvent
from jit_utils.lambda_decorators import feature_flags_init_client
from jit_utils.lambda_decorators import lambda_warmup_handler
from jit_utils.logger import custom_labels
from jit_utils.logger import CustomLabel
from jit_utils.logger import logger
from jit_utils.logger import logger_customer_id
from jit_utils.models.findings.events import UploadFindingsStatusEvent
from jit_utils.utils.aws.idempotency import get_persistence_layer

from src.lib.cores.executions_core import update_upload_findings_status


@lambda_warmup_handler
@idempotent(
    persistence_store=get_persistence_layer(),
    config=IdempotencyConfig(
        event_key_jmespath="id",
        raise_on_no_idempotency_key=True,
    ),
)
@feature_flags_init_client()
@logger_customer_id(auto=True)
@custom_labels(
    [
        CustomLabel(
            field_name="execution_id",
            label_name="execution_id",
            auto=True,
        ),
        CustomLabel(
            field_name="jit_event_id",
            label_name="jit_event_id",
            auto=True,
        ),
    ]
)
def handler(event: EventBridgeEvent, __) -> None:
    """
    This function is called findings are uploaded for an execution.
    """
    logger.info(f"Finished uploading findings for an execution {event=}")
    request = UploadFindingsStatusEvent(**event["detail"])

    logger.info(f"Update findings uploaded request request: {request}")
    update_upload_findings_status(request)

from jit_utils.logger import logger

from src.lib.clients.execution_log import ExecutionLogManager
from src.lib.clients.execution_log import GetLogStreamResponse
from src.lib.constants import EXECUTION_LOGS_S3_BUCKET
from src.lib.models.log_models import GetTruncatedLogWithPresignedResult


def get_execution_log_truncated_with_presigned_url_read(
        tenant_id: str,
        jit_event_id: str,
        execution_id: str,
        max_bytes: int,
        bucket: str = EXECUTION_LOGS_S3_BUCKET
) -> GetTruncatedLogWithPresignedResult:
    """Returns the execution log truncated to max_bytes and a presigned url to read the full log.

    If the log was not found, an ExecutionLogNotFoundException will be raised.
    """

    client = ExecutionLogManager(
        tenant_id=tenant_id,
        jit_event_id=jit_event_id,
        execution_id=execution_id,
        bucket=bucket
    )
    log_stream: GetLogStreamResponse = client.get_log_stream()
    presigned_url_read = client.get_log_presigned_url_read()

    if log_stream.content_length <= max_bytes:
        logger.info(f"Execution log file is smaller than max_bytes ({log_stream.content_length} <= {max_bytes})")
        return GetTruncatedLogWithPresignedResult(
            content=log_stream.stream.read().decode('utf-8'),
            truncated=False,
            presigned_url_read=presigned_url_read
        )

    return GetTruncatedLogWithPresignedResult(
        content=log_stream.stream.read(amt=max_bytes).decode('utf-8'),
        truncated=True,
        presigned_url_read=presigned_url_read
    )

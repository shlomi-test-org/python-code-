from urllib.parse import unquote_plus

from aws_lambda_typing.events import S3Event
from aws_lambda_typing.events.s3 import S3EventRecord
from jit_utils.aws_clients.s3 import S3Client
from jit_utils.lambda_decorators import exception_handler
from jit_utils.logger import logger
from jit_utils.logger.logger import add_label, alert

from src.lib.cores.print_exec_logs_from_s3_core import get_execution_from_control_logs_and_notify_slack
from src.lib.models.log_models import ControlLogs


def _get_control_logs_from_s3(event: S3Event) -> ControlLogs:
    s3 = S3Client()
    record: S3EventRecord = event["Records"][0]
    bucket_name: str = record["s3"]["bucket"]["name"]
    key: str = unquote_plus(record["s3"]["object"]["key"], encoding="utf-8")
    stream = s3.client.get_object(Bucket=bucket_name, Key=key)["Body"]
    s3_url = f"https://s3.console.aws.amazon.com/s3/object/{bucket_name}?prefix={key}"
    return ControlLogs.initialize(key=key, stream=stream, s3_url=s3_url)


@exception_handler()
def handler(event: S3Event, _):
    """
    This Lambda prints the events from the control executions.
    This allows us to see what is happening in the remote controls,
    as the execution logs will be on CloudWatch, and therefore we can see them on Epsagon.
    """
    logger.info(f"Got a new logs bucket S3 {event=}")

    try:
        control_logs = _get_control_logs_from_s3(event)
    except ValueError:
        alert("Failed to get control logs from S3.",
              log_exception_stacktrace=True,
              alert_type="FAILED_TO_GET_CONTROL_LOGS_FROM_S3")
        return

    logger.info(f"S3 object url to view and download the logs: {control_logs.s3_url}")

    add_label("customer_id", control_logs.tenant_id)
    add_label("jit_event_id", control_logs.jit_event_id)
    add_label("execution_id", control_logs.execution_id)

    get_execution_from_control_logs_and_notify_slack(control_logs)

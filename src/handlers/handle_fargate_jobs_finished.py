from http import HTTPStatus
from typing import List
from typing import Tuple

from aws_lambda_typing.context import Context
from aws_lambda_typing.events import EventBridgeEvent
from jit_utils.logger import alert
from jit_utils.logger import logger
from jit_utils.logger.logger import add_label
from jit_utils.models.execution import ExecutionStatus
from mypy_boto3_batch.type_defs import JobDetailTypeDef

from src.lib.aws_common import send_container_task_finish_event
from src.lib.cores.execution_events import send_task_completion_event
from src.lib.cores.fargate.common import get_batch_job_properties
from src.lib.cores.fargate.fargate_core import FargateHandler
from src.lib.exceptions import EventMissingStartOrFinish
from src.lib.exceptions import NonJitTaskError


def handle_batch_jobs_failure(event: EventBridgeEvent, context: Context):
    """
    Handles an event where AWS Batch job changes to failed state
    """
    logger.info(f"Received failed batch job event (fargate): {event=}")
    job_detail: JobDetailTypeDef = event["detail"]
    # will notify slack with error
    _make_alert(job_detail)
    job_container_env_vars: List = job_detail["container"]["environment"]
    batch_job_failure: str = job_detail.get(
        "statusReason", "Unknown Failure Reason"
    )

    batch_job_properties = get_batch_job_properties(job_container_env_vars)
    if not batch_job_properties:
        raise NonJitTaskError(event=event, extra_msg="Missing batch job properties.")

    add_label("customer_id", batch_job_properties.tenant_id)
    add_label("jit_event_id", batch_job_properties.jit_event_id)
    add_label("execution_id", batch_job_properties.execution_id)
    send_task_completion_event(
        completion_status=ExecutionStatus.FAILED,
        tenant_id=batch_job_properties.tenant_id,
        execution_id=batch_job_properties.execution_id,
        jit_event_id=batch_job_properties.jit_event_id,
        error_message=batch_job_failure,
    )


def _make_alert(job_detail: JobDetailTypeDef):
    job_definition, job_link, logs_link = _make_labels(job_detail)
    add_label("job_link", job_link)
    add_label("logs_link", logs_link)
    add_label("job_definition", job_definition)
    alert(
        message="Batch job failed. See tags for more info.",
        alert_type='Execution Batch Job Failed'
    )


def _make_labels(job_detail: JobDetailTypeDef) -> Tuple[str, str, str]:
    job_id = job_detail["jobId"]
    log_group = job_detail["container"]["logConfiguration"]["options"]["awslogs-group"].replace("/", '$252F')
    log_stream = job_detail["container"]["logStreamName"].replace("/", '$252F')
    job_link = f"https://console.aws.amazon.com/batch/home?#jobs/fargate/detail/{job_id}"
    logs_link = (
        f"https://console.aws.amazon.com/cloudwatch/home?#logsV2:log-groups/log-group/"
        f"{log_group}/log-events/{log_stream}"
    )
    job_definition = job_detail["jobDefinition"].split("/")[1].split(":")[0]
    return job_definition, job_link, logs_link


def handle_ecs_jobs_completion(event: EventBridgeEvent, context: Context):
    """
    Handles an event when ECS job finishes (completion/failure) - and calculates pricing.
    Fargate pricing works like this:
    - Duration of run - minimum 1 minute for linux based machines, 15 minutes for windows based
    CPU/Memory - depending on cpu-architecture - for on demand (spots will not be calculated)
    1. per vCPU per hour
    2. per GB per hour
    3. per Storage GB per hour, where 20GB of ephemeral storage is free
    Note - data transfer costs are not added to the calculation.
    """
    handler = FargateHandler()
    try:
        data = handler.parse_ecs_event(event)
    except EventMissingStartOrFinish:  # Events that fail to start / end - we cannot measure
        logger.warning("ECS task submitted without pullStartAt / stoppedAt")
        raise
    except NonJitTaskError as e:  # This was an ECS task that was submitted which not jit one, will skip.
        logger.error(
            f"Event is not JIT event: {e.extra_msg}, {event=}"
        )
        return

    add_label("customer_id", data.tenant_id)
    add_label("jit_event_id", data.jit_event_id)
    add_label("execution_id", data.execution_id)

    price = handler.calculate_task_price(data)
    send_container_task_finish_event(ecs_data=data, price=price)
    return HTTPStatus.OK

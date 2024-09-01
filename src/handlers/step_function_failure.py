import dataclasses
import datetime
import json
import os

from aws_lambda_powertools.utilities.idempotency import idempotent, IdempotencyConfig
from aws_lambda_typing.context import Context
from aws_lambda_typing.events import EventBridgeEvent
from jit_utils.aws_clients.sqs import SQSClient as InternalSQSClient
from jit_utils.event_models import CodeRelatedJitEvent, JitEventTypes
from jit_utils.event_models.trigger_event import CodeRelatedInternalFailureEvent
from jit_utils.logger import logger_customer_id, logger
from jit_utils.logger.customer_id_finders import tenant_id_from_eventbridge_message
from jit_utils.logger.logger import add_label
from jit_utils.models.execution import ExecutionStatus
from jit_utils.models.slack.entities import InternalSlackMessageBody
from jit_utils.utils.aws.idempotency import get_persistence_layer
from pydantic import parse_obj_as

from src.lib.constants import ENV_NAME, SLACK_CHANNEL_NAME_ERRORS, SEND_INTERNAL_NOTIFICATION_QUEUE_NAME, \
    STATE_MACHINE_EXECUTION_URL_PREFIX, TRIGGER_SERVICE
from src.lib.cores.jit_event_life_cycle.jit_event_life_cycle_handler import JitEventLifeCycleHandler


@logger_customer_id(customer_id_finder=tenant_id_from_eventbridge_message)
@idempotent(
    persistence_store=get_persistence_layer(),
    config=IdempotencyConfig(
        event_key_jmespath='id',
        raise_on_no_idempotency_key=True,
    ),
)
def handler(event: EventBridgeEvent, _: Context) -> None:
    """
    Handle a failed step function
    """
    logger.info(f"Handling step function failure {event=}")

    logger.info("Updating the jit event life cycle with asset finished running")
    state_machine_input = json.loads(event["detail"]["input"])
    jit_event: JitEventTypes = parse_obj_as(JitEventTypes, state_machine_input["jit_event"])  # type: ignore
    add_label("jit_event_id", jit_event.jit_event_id)

    JitEventLifeCycleHandler().asset_completed(
        tenant_id=jit_event.tenant_id,
        jit_event_id=jit_event.jit_event_id,
    )

    # Failed enrichment can come from multiple jit event types, such as CodeRelatedJitEvent or ManuelExecutionJitEvent,
    # but currently we want to propagate the failure only for CodeRelatedJitEvent to expose the feature gradually.
    if isinstance(jit_event, CodeRelatedJitEvent):
        internal_failure_event = CodeRelatedInternalFailureEvent(
            tenant_id=jit_event.tenant_id,
            jit_event=jit_event,
            failure_message="Internal failure Enrichment Step Function",
        )
        internal_failure_event.propagate_internal_failure_event(source_service=TRIGGER_SERVICE)
        add_label("pr_scan_failed_before_executions", "true")

    try:
        # cause field is a stringified JSON containing execution
        cause_details = json.loads(event["detail"]["cause"])
        status = cause_details.get("status")
        if status == ExecutionStatus.WATCHDOG_TIMEOUT.value:
            logger.info("Skipping sending slack message due to status: watchdog_timeout")
            return
    except Exception as e:
        logger.info(f"Failed to parse execution status from cause field: {e}, will continue to report error")

    logger.info("Extracting relevant information from the event")
    execution_arn = event["detail"]["executionArn"]
    status = event["detail"]["status"]
    start_date = datetime.datetime.fromtimestamp(event["detail"]["startDate"] / 1000).isoformat()
    stop_date = datetime.datetime.fromtimestamp(event["detail"]["stopDate"] / 1000).isoformat()
    error = event["detail"]["error"]

    logger.info("Crafting the message to send to slack")
    slack_message_text = (
        f"(= ФェФ=) `Step Function Failure Alert` (= ФェФ=)\n"
        f"Status: `{status}`\n"
        f"Error: `{error}`\n"
        f"Start Time: {start_date}\n"
        f"End Time: {stop_date}\n"
        f"Execution URL: {STATE_MACHINE_EXECUTION_URL_PREFIX}{execution_arn}"
    )

    channel_id = SLACK_CHANNEL_NAME_ERRORS.format(env_name=os.environ[ENV_NAME])
    slack_message = InternalSlackMessageBody(channel_id=channel_id, text=slack_message_text)

    logger.info("Sending the message to the internal notification queue")
    InternalSQSClient().send_message(
        SEND_INTERNAL_NOTIFICATION_QUEUE_NAME,
        json.dumps(dataclasses.asdict(slack_message))
    )

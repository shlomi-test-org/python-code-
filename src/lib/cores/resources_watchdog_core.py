import json
import os
from datetime import datetime
from itertools import chain
from typing import List, Dict
from typing import Optional
from uuid import uuid4

from aws_lambda_typing.events.sqs import SQSMessage
from jit_utils.aws_clients.sqs import SQSClient as InternalSQSClient
from jit_utils.logger import logger
from jit_utils.models.execution import ExecutionStatus
from jit_utils.models.execution import VendorFailureReason

from src.lib.clients.sqs import SQSClient
from src.lib.constants import ENV_NAME, SlackMessageBlock
from src.lib.constants import EXCEEDED_TIME_LIMITATION_ERROR
from src.lib.constants import EXECUTION_COMPLETE_EVENT_DETAIL_TYPE
from src.lib.constants import MAX_BATCH_SIZE
from src.lib.constants import SEND_INTERNAL_NOTIFICATION_QUEUE_NAME
from src.lib.constants import SLACK_CHANNEL_NAME_FREE_RESOURCES_ERRORS
from src.lib.constants import SLACK_CHANNEL_NAME_RESOURCE_EXPIRED_ERRORS
from src.lib.constants import SLACK_CHANNEL_NAME_USER_MISCONFIG
from src.lib.constants import WATCHDOG_EVENT_QUEUE_NAME
from src.lib.cores.execution_runner import get_execution_runner
from src.lib.cores.executions_core import send_execution_event, update_execution_with_vendor_failure
from src.lib.cores.utils.transactions import execute_resource_freeing_transaction
from src.lib.data.executions_manager import ExecutionsManager
from src.lib.exceptions import StatusTransitionException, MultipleCompletesExceptions
from src.lib.models.client_models import InternalSlackMessageBody
from src.lib.models.execution_models import ControlStatusDetails
from jit_utils.models.execution import Execution
from src.lib.models.execution_models import ExecutionWithVendorLogs
from src.lib.models.execution_models import UpdateRequest


def find_executions_to_terminate_and_push_to_queue() -> int:
    """
    Finds executions that need to be terminated and pushes them to the queue.
    """
    executions_to_terminate_count = _find_executions_to_terminate_and_push_to_queue()
    logger.info(
        f"and {executions_to_terminate_count} executions to terminate (new watchdog logic)"
    )
    return executions_to_terminate_count


def _find_executions_to_terminate_and_push_to_queue() -> int:
    """
    Finds executions that need to be terminated and pushes them to the queue.
    """
    start_key = None
    has_finished = False
    total = 0
    executions_manager = ExecutionsManager()
    sqs_client = SQSClient()
    while not has_finished:
        executions_to_terminate, next_key = executions_manager.get_executions_to_terminate(start_key, MAX_BATCH_SIZE)
        start_key = next_key
        total += len(executions_to_terminate)
        messages_to_send = []
        for execution in executions_to_terminate:
            messages_to_send.append({
                'Id': str(uuid4()),
                'MessageBody': execution.json(),
                'MessageGroupId': 'resources_watchdog',
            })
        if messages_to_send:
            logger.info(f'Sending {len(messages_to_send)} messages to queue {WATCHDOG_EVENT_QUEUE_NAME}')
            sqs_client.send_fifo_messages_batch(WATCHDOG_EVENT_QUEUE_NAME, messages_to_send)

        if not next_key:
            has_finished = True
    logger.info(f"Found {total} executions to terminate")
    return total


def terminate_execution_and_free_resources_core(to_terminate: List[Execution]) -> List[Execution]:
    """
    Terminate executions and free their resources that are in the queue.
    :param to_terminate: A list of Execution instances to terminate and free their resources
    :returns: A list of Execution that failed the operation
    """
    logger.info(f"Terminating the executions {to_terminate}")
    execution_freed_resources = []
    failed_to_update_executions = []

    for execution in to_terminate:
        try:
            updated_execution = _update_execution_and_free_resources(execution)
        except (StatusTransitionException, MultipleCompletesExceptions):
            # exec was already in a completed status, we don't need to free the resources or timeout the execution again
            continue
        except Exception as exc:
            # A broad exception is used here since we have to catch any failure in order to let the lambda know which
            # messages should be sent back to the queue.
            # Otherwise, we will not try to free the resource again or won't put it in the DLQ if needed
            logger.error(exc)
            failed_to_update_executions.append(execution)
        else:
            # since we are sending the updated_execution object to be notified, we need to change its status (which
            # is watchdog_timeout after the resource got freed) to the status that the execution got stuck in
            updated_execution.status = execution.status
            logger.info(
                f"Trying to terminate the run of execution={execution.execution_id} for Tenant={execution.tenant_id}")
            runner = get_execution_runner(execution)

            if execution.status < ExecutionStatus.RUNNING:
                # If status is RUNNING -> don't fetch vendor error, since the vendor succeeded to start the execution
                # statuses bigger than RUNNING (completed, failed, etc.) should not get here
                logger.info(f"{execution.status=} in not in running state - should check for vendor error")
                execution = update_execution_with_vendor_failure(execution)
            _terminate_run(execution)
            execution_freed_resources.append(
                ExecutionWithVendorLogs(**execution.dict(), vendor_logs_url=runner.logs_url)
            )

    forward_about_expired_resource_to_notification_service(execution_freed_resources)
    return failed_to_update_executions


def _terminate_run(execution: Execution) -> None:
    runner = get_execution_runner(execution)
    if runner.can_terminate():
        logger.info("Terminating the run")
        runner.terminate()


def _update_execution_and_free_resources(execution_to_terminate: Execution) -> Execution:
    now = datetime.utcnow()
    update_execution_status = UpdateRequest(
        tenant_id=execution_to_terminate.tenant_id,
        execution_id=execution_to_terminate.execution_id,
        jit_event_id=execution_to_terminate.jit_event_id,
        status=ExecutionStatus.WATCHDOG_TIMEOUT.value,
        completed_at=now.isoformat(),
        completed_at_ts=int(now.timestamp()),
        status_details=ControlStatusDetails(
            message=EXCEEDED_TIME_LIMITATION_ERROR
        )
    )

    # TODO: if exception happens in the resource freeing transaction, we will retry even if the resource was freed
    updated_execution_attributes = execute_resource_freeing_transaction(
        execution_to_terminate=execution_to_terminate,
        update_execution_status=update_execution_status,
    )

    updated_execution = Execution(**{
        **execution_to_terminate.dict(),
        **updated_execution_attributes.dict(exclude_none=True),
    })
    send_execution_event(updated_execution.json(exclude_none=True), EXECUTION_COMPLETE_EVENT_DETAIL_TYPE)
    return updated_execution


def format_channel_name(base_channel_name: str) -> str:
    environment_name = os.environ[ENV_NAME]
    return base_channel_name.format(env_name=environment_name)


def create_slack_message_body(channel_name: str, message_text: str, blocks: List[Dict]) -> \
        Optional[InternalSlackMessageBody]:
    if blocks:
        return InternalSlackMessageBody(channel_id=channel_name, text=message_text, blocks=blocks)
    return None


def _render_resource_expired_slack_messages(
    resource_management_blocks: List[SlackMessageBlock],
    user_misconfig_blocks: List[SlackMessageBlock],
) -> List[InternalSlackMessageBody]:
    message_text = "Resource expired"
    resource_management_channel = format_channel_name(SLACK_CHANNEL_NAME_RESOURCE_EXPIRED_ERRORS)
    user_misconfig_channel = format_channel_name(SLACK_CHANNEL_NAME_USER_MISCONFIG)

    slack_messages = [
        create_slack_message_body(resource_management_channel, message_text, resource_management_blocks),
        create_slack_message_body(user_misconfig_channel, message_text, user_misconfig_blocks)
    ]
    logger.info(f"rendered slack messages: list: \n{slack_messages}")
    # Filter out None values in case there are no blocks for a message
    return [message for message in slack_messages if message]


def contains_user_misconfig_failure_reasons(execution: ExecutionWithVendorLogs) -> bool:
    if not execution.error_body:
        return False

    user_misconfig_failure_reasons = [
        VendorFailureReason.BAD_USER_CONFIGURATIONS,
        VendorFailureReason.NO_GITHUB_CI_MINUTES,
        # Add as many reasons as you need here.
    ]

    return any(failure_reason in execution.error_body for failure_reason in user_misconfig_failure_reasons)


def forward_about_expired_resource_to_notification_service(executions: List[ExecutionWithVendorLogs]):
    """
    Forwards a message to the notification service about expired resources of an execution.
    :param executions: List of Execution instances that were canceled and their resources were freed
    """
    if not executions:
        logger.info("No message  are being freed - skip sending slack message")
        return

    logger.info(f"Sending a message to a Slack channel about {len(executions)} expired executions")
    resource_mgmt_blocks = []
    user_misconfig_blocks = []
    for execution in executions:
        # TODO: deprecate body_error after the new CES is implemented
        if execution.user_input_errors or contains_user_misconfig_failure_reasons(execution):
            user_misconfig_blocks.append(_generate_user_error_slack_msg_block(execution))
        else:
            resource_mgmt_blocks.append(_generate_slack_msg_block(execution))

    iter_resource_mgmt_blocks = list(chain.from_iterable(resource_mgmt_blocks))
    iter_user_misconfig_blocks = list(chain.from_iterable(user_misconfig_blocks))

    forward_slack_messages_to_notification_service_via_sqs(
        messages=_render_resource_expired_slack_messages(iter_resource_mgmt_blocks, iter_user_misconfig_blocks),
    )


def _generate_user_error_slack_msg_block(execution: ExecutionWithVendorLogs) -> List:
    # Handle user input errors and error_body
    error_messages: List[str] = []
    for error in execution.user_input_errors:
        logger.info(f"Adding user input error: {error.error_body}")
        error_messages.append(error.error_body)

    if execution.error_body:
        # Attempt to parse the error_body JSON and extract the internal error_body message
        logger.info("Trying to parse the error_body as JSON, in order to extract the internal error message")
        try:
            parsed_error_body = json.loads(execution.error_body)
            # Use the entire error_body if the specific key doesn't exist
            internal_error_message = parsed_error_body.get('error_body', execution.error_body)
            logger.info(f"Extracted internal error message: {internal_error_message}")
            error_messages.append(internal_error_message)
        except json.JSONDecodeError:
            logger.info("Failed to parse the error_body as JSON, using the original error_body string")
            # If parsing fails, display the original error_body string
            error_messages.append(execution.error_body)
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{execution.job_name} job failed for user: {execution.context.asset.owner}",
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Tenant ID:* {execution.tenant_id}\n"
                    f"*Asset Name:* {execution.asset_name}\n"
                    f"*Errors:*\n" + "\n".join(error_messages)
                )
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*DEBUG INFO*\n"
                    f"*jit_event_name:* {execution.jit_event_name}\n"
                    f"*jit_event_id:* {execution.jit_event_id}\n"
                    f"*execution_id:* {execution.execution_id}\n"
                    f"*run_id:* {execution.run_id}\n"
                )
            },
        },
        {
            "type": "divider",
        }
    ]


def _generate_slack_msg_block(execution: ExecutionWithVendorLogs) -> List:
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{execution.job_name} timeout for {execution.context.asset.owner}",
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*tenant_id:* {execution.tenant_id}\n"
                    f"*owner:* {execution.context.asset.owner}\n"
                    f"*asset_name:* {execution.asset_name}\n"
                    f"*jit_event_id:* {execution.jit_event_id}\n"
                    f"*jit_event_name:* {execution.jit_event_name}\n"
                    f"*execution_id:* {execution.execution_id}\n"
                    f"*run_id:* {execution.run_id}\n"
                    f"*error_body:* {execution.error_body}\n"
                )
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"`watchdog termination time:` {datetime.utcnow().isoformat()}\n"
                    f"*created_at:* {execution.created_at}\n"
                    f"*dispatched_at:* {execution.dispatched_at}\n"
                    f"*registered_at:* {execution.registered_at}\n"
                    f"*completed_at:* {execution.completed_at}\n"
                )
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*status:* {execution.status}\n"
                    f"*control_status:* {execution.control_status}\n"
                    f"*upload_findings_status:* {execution.upload_findings_status}\n"
                    f"*status_details:* {execution.status_details}\n"
                )
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*control_name:* {execution.control_name}\n"
                    f"*job_name:* {execution.job_name}\n"
                    f"*job_runner:* {execution.job_runner}\n"
                    f"*resource_type:* {execution.resource_type}\n"
                    f"*vendor_job_logs_url:* {execution.vendor_logs_url}"
                )
            },
        },
        {
            "type": "divider",
        }
    ]


def forward_free_resource_failed_msg_to_notification_service(messages: List[SQSMessage]) -> None:
    """
    Format a failed free resource SQS message to a Slack message and forward it to notification service
    :param messages: List of SQSMessage instances
    """
    channel_id = SLACK_CHANNEL_NAME_FREE_RESOURCES_ERRORS.format(env_name=os.environ[ENV_NAME])
    slack_messages: List[InternalSlackMessageBody] = []
    for message in messages:
        slack_messages.append(InternalSlackMessageBody(channel_id=channel_id,
                                                       text=f"Resource {message['body']} could not be freed"))
    forward_slack_messages_to_notification_service_via_sqs(messages=slack_messages)


def forward_slack_messages_to_notification_service_via_sqs(messages: List[InternalSlackMessageBody]) -> None:
    """
    Just a wrapper above send_message to send multiple messages from a list

    Forwards SQS messages to the notification service
    :param messages: List of SQS messages
    """
    sqs_client = InternalSQSClient()
    for message in messages:
        sqs_client.send_message(
            SEND_INTERNAL_NOTIFICATION_QUEUE_NAME,
            message.json()
        )

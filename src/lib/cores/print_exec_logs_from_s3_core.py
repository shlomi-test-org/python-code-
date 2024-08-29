import os
from typing import List

from jit_utils.models.execution import ExecutionStatus
from jit_utils.models.controls import ControlType

from src.lib.constants import ENV_NAME, JIT_EXECUTION_OUTPUTS_BUCKET_NAME, S3_BUCKET_FORMAT
from src.lib.constants import SLACK_CHANNEL_CONTROL_ERRORS_NAME
from src.lib.cores.resources_watchdog_core import forward_slack_messages_to_notification_service_via_sqs
from src.lib.data.executions_manager import ExecutionsManager
from src.lib.models.client_models import InternalSlackMessageBody
from jit_utils.models.execution import Execution
from src.lib.models.log_models import ControlLogs


def did_control_fail(execution: Execution) -> bool:
    """
    Determine if the control failed based on the execution status and has_findings flag
    if the control is a detection control, we will check the has_findings flag
    otherwise we will check only the execution status since the has_findings flag is not relevant
    regardless of the control type, if the execution has an error body or stderr, we will consider the control failed
    """
    if execution.error_body:
        return True
    elif execution.control_type == ControlType.DETECTION:
        return execution.status == ExecutionStatus.FAILED and not execution.has_findings
    else:
        return execution.status == ExecutionStatus.FAILED


def get_execution_from_control_logs_and_notify_slack(control_logs: ControlLogs) -> None:
    """
    Get the execution from the control logs and notify slack if the control failed

    :param control_logs: The control logs

    :return: None

    :raises Exception: If the execution could not be found
    """

    # Fetch execution status from the control logs
    executions_manager = ExecutionsManager()
    execution = executions_manager.get_execution_by_jit_event_id_and_execution_id(
        tenant_id=control_logs.tenant_id,
        jit_event_id=control_logs.jit_event_id,
        execution_id=control_logs.execution_id
    )

    if not execution:
        raise Exception(
            f'Could not find execution for tenant {control_logs.tenant_id} '
            f'and jit_event_id {control_logs.jit_event_id} '
            f'and execution_id {control_logs.execution_id}')

    # Determine if the control failed
    if did_control_fail(execution):
        owner = execution.context.installation.owner if execution.context.installation else 'Not Available'
        s3_tool_outputs = S3_BUCKET_FORMAT.format(
            bucket_name=JIT_EXECUTION_OUTPUTS_BUCKET_NAME,
            object_key=f"{execution.tenant_id}/{execution.jit_event_id}-{execution.execution_id}/"
        )

        # send slack failed control message
        notification_text = f"Control: {execution.control_name} failed (ㅠ﹏ㅠ) \n" \
                            f"Tenant: {execution.tenant_id} \n" \
                            f"Owner: {owner} \n" \
                            f"Asset: {execution.context.asset.asset_name} \n" \
                            f"S3 logs url: {control_logs.s3_url} \n" \
                            f"S3 tool outputs url: {s3_tool_outputs} \n" \
                            f"jit_event_name: {execution.jit_event_name} \n" \
                            f"jit_event_id: {execution.jit_event_id} \n" \
                            f"execution_id: {execution.execution_id} \n" \
                            f"Error body: ```{execution.error_body}``` \n" \
                            f"stderr: ```{execution.stderr}``` \n" \
                            "`====================Execution Log Done===================`"
        channel_id = SLACK_CHANNEL_CONTROL_ERRORS_NAME.format(env_name=os.environ[ENV_NAME])
        slack_messages: List[InternalSlackMessageBody] = [
            InternalSlackMessageBody(channel_id=channel_id, text=notification_text)
        ]

        forward_slack_messages_to_notification_service_via_sqs(slack_messages)

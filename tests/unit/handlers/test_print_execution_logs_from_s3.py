import os
import uuid
from io import BytesIO
from typing import Dict
from unittest.mock import Mock
from unittest.mock import patch

import boto3
import pytest
from botocore.response import StreamingBody
from moto import mock_s3, mock_sqs

from src.handlers.print_execution_logs_from_s3 import handler
from src.lib.constants import EXECUTION_LOG_PRINT_MAX_CHUNK_SIZE, SEND_INTERNAL_NOTIFICATION_QUEUE_NAME
from src.lib.models.client_models import InternalSlackMessageBody
from src.lib.models.execution_models import ExecutionStatus
from tests.mocks.execution_mocks import MOCK_EXECUTION
from tests.mocks.execution_mocks import MOCK_EXECUTION_ENRICHMENT

TEST_TENANT_ID = str(uuid.uuid4())
TEST_JIT_EVENT_ID = str(uuid.uuid4())
TEST_EXECUTION_ID = str(uuid.uuid4())

NON_CONTROL_LOGS_COUNT = 1
slack_message_mock = [
    InternalSlackMessageBody(
        text='Control: control-0 failed (ㅠ﹏ㅠ) \n'
        'Tenant: 686154ad-93a8-43d6-8bdb-34b3145f1537 \n'
        'Owner: owner \n'
        'Asset: test_repo \n'
        'S3 logs url: https://s3.console.aws.amazon.com/s3/object/jit-execution-logs-dev?prefix='
        '686154ad-93a8-43d6-8bdb-34b3145f1537/'
        'dd7cb9e9-dca6-4012-9401-63a842ee77e9-8429eb01-2ecb-43fc-933f-4e20480f5306.log \n'
        'S3 tool outputs url: https://s3.console.aws.amazon.com/s3/buckets/'
        f'jit-execution-outputs-{os.getenv("ENV_NAME", "local")}?prefix=686154ad-93a8-43d6-8bdb-34b3145f1537/'
        'dd7cb9e9-dca6-4012-9401-63a842ee77e9-8429eb01-2ecb-43fc-933f-4e20480f5306/ \n'
        'jit_event_name: pull_request_created \n'
        'jit_event_id: dd7cb9e9-dca6-4012-9401-63a842ee77e9 \n'
        'execution_id: 8429eb01-2ecb-43fc-933f-4e20480f5306 \n'
        'Error body: ```None``` \n'
        'stderr: ```None``` \n'
        '`====================Execution Log Done===================`',
        channel_id=f'jit-control-errors-{os.getenv("ENV_NAME", "local")}',
        blocks=None)
]


def _generate_event(key: str) -> Dict:
    return {"Records": [{"s3": {"bucket": {"name": "jit-execution-logs-dev"}, "object": {"key": key}}}]}


def test_handler_large_content_size(mocker, monkeypatch):
    content = b"aa" * EXECUTION_LOG_PRINT_MAX_CHUNK_SIZE

    mock_stream = {"Body": StreamingBody(BytesIO(content), len(content))}
    mocker.patch(
        "src.handlers.print_execution_logs_from_s3.S3Client",
        return_value=Mock(client=Mock(get_object=Mock(return_value=mock_stream))),
    )
    # mock execution
    mocker.patch(
        "src.lib.data.executions_manager.ExecutionsManager.get_execution_by_jit_event_id_and_execution_id",
        return_value=MOCK_EXECUTION
    )

    with mock_s3(), mock_sqs():  # Mock the s3 service to avoid ConnectionError during the handler
        sqs_client = boto3.client("sqs", region_name="us-east-1")
        sqs_client.create_queue(QueueName=SEND_INTERNAL_NOTIFICATION_QUEUE_NAME)

        monkeypatch.delenv('LOCALSTACK_HOSTNAME', raising=False)
        handler(_generate_event(f"{TEST_TENANT_ID}/{TEST_JIT_EVENT_ID}-{TEST_EXECUTION_ID}.log"), {})


@patch("src.handlers.print_execution_logs_from_s3.logger")
def test_handler__bad_object_key(logger, mocker):
    mocker.patch("src.handlers.print_execution_logs_from_s3.S3Client")

    handler(_generate_event("aaaaaaa.log"), {})

    assert logger.info.call_count == NON_CONTROL_LOGS_COUNT


@pytest.mark.parametrize("execution", [MOCK_EXECUTION, MOCK_EXECUTION_ENRICHMENT])
def test_handler_with_failed_execution(mocker, executions_manager, execution):
    """
    Test that the handler forwards the Slack message to the notification service
    """
    content = "You have been tested"

    mock_stream = {"Body": StreamingBody(BytesIO(content.encode()), len(content))}
    mocker.patch(
        "src.handlers.print_execution_logs_from_s3.S3Client",
        return_value=Mock(client=Mock(get_object=Mock(return_value=mock_stream))),
    )

    executions_manager.create_execution(execution)

    # mock send slack function
    mock = mocker.patch(
        "src.lib.cores.print_exec_logs_from_s3_core.forward_slack_messages_to_notification_service_via_sqs")

    handler(
        _generate_event(f"{execution.tenant_id}/{execution.jit_event_id}-{execution.execution_id}.log"),
        {}
    )

    # assert forward_slack_messages_to_notification_service_via_sqs was called
    assert mock.call_count == 1
    assert mock.call_args[0][0] == slack_message_mock


def test_handler_with_successful_execution(mocker, executions_manager):
    """
    Test that the handler forwards the slack message to the notification service
    """
    content = "You have been tested"

    mock_stream = {"Body": StreamingBody(BytesIO(content.encode()), len(content))}
    mocker.patch(
        "src.handlers.print_execution_logs_from_s3.S3Client",
        return_value=Mock(client=Mock(get_object=Mock(return_value=mock_stream))),
    )

    successful_execution = MOCK_EXECUTION
    successful_execution.status = ExecutionStatus.COMPLETED
    executions_manager.create_execution(successful_execution)

    # mock send slack function
    mock = mocker.patch(
        "src.lib.cores.print_exec_logs_from_s3_core.forward_slack_messages_to_notification_service_via_sqs")

    handler(
        _generate_event(f"{MOCK_EXECUTION.tenant_id}/{MOCK_EXECUTION.jit_event_id}-{MOCK_EXECUTION.execution_id}.log"),
        {}
    )

    # assert forward_slack_messages_to_notification_service_via_sqs was called
    assert mock.call_count == 0

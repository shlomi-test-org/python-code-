import boto3
import pytest
from moto import mock_s3

from src.lib.clients.execution_log import ExecutionLogManager
from src.lib.clients.execution_log import ExecutionLogNotFoundException
from src.lib.clients.execution_log import GetLogStreamResponse
from src.lib.constants import EXECUTION_LOGS_S3_BUCKET

TEST_TENANT_ID = 'test-tenant-id'
TEST_JIT_EVENT_ID = 'test-jit-event-id'
TEST_KB_DATA = b'A' * 1024


@pytest.fixture()
def manager(monkeypatch):
    # Remove the environment variable, so mock_dynamodb2 will take over
    monkeypatch.delenv('LOCALSTACK_HOSTNAME', raising=False)

    with mock_s3():
        s3 = boto3.client('s3', region_name='us-east-1')

        # Create mock objects
        for i in range(1, 15):
            try:
                s3.create_bucket(Bucket=EXECUTION_LOGS_S3_BUCKET)
            except Exception as e:
                print(e)
            s3.create_bucket(
                Bucket=EXECUTION_LOGS_S3_BUCKET,
            )
            s3.put_object(Bucket=EXECUTION_LOGS_S3_BUCKET,
                          Key=f'{TEST_TENANT_ID}/{TEST_JIT_EVENT_ID}-{i}.log',
                          Body=TEST_KB_DATA * i)

        yield ExecutionLogManager(
            tenant_id=TEST_TENANT_ID,
            jit_event_id=TEST_JIT_EVENT_ID,
            execution_id='1',
            bucket=EXECUTION_LOGS_S3_BUCKET,
        )


class TestExecutionLogManager:
    def test_s3_object_key_string(self, manager):
        assert manager.s3_object_key == f'{TEST_TENANT_ID}/{TEST_JIT_EVENT_ID}-1.log'

    def test_does_object_exist_true(self, manager):
        assert manager.does_object_exist() is True

    def test_does_object_exist_false(self, manager):
        old_s3_object_key = manager.s3_object_key

        manager.s3_object_key = 'not-exists-key'
        assert manager.does_object_exist() is False

        manager.s3_object_key = old_s3_object_key

    def test_get_log_stream(self, manager):
        log_stream_response: GetLogStreamResponse = manager.get_log_stream()
        assert log_stream_response.stream.read() == TEST_KB_DATA
        assert log_stream_response.content_length == 1024

    def test_get_log_presigned_url_read_object_exists(self, manager):
        assert manager.get_log_presigned_url_read() is not None

    def test_get_log_presigned_url_read_object_does_not_exist(self, manager, mocker):
        mocker.patch.object(manager, 'does_object_exist', return_value=False)
        with pytest.raises(ExecutionLogNotFoundException):
            manager.get_log_presigned_url_read()

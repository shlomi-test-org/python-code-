from unittest.mock import Mock

import pytest

from src.lib.clients.execution_log import ExecutionLogNotFoundException
from src.lib.cores.execution_log import get_execution_log_truncated_with_presigned_url_read
from src.lib.cores.execution_log import GetTruncatedLogWithPresignedResult

TEST_OBJECT_CONTENT = b"abcde" * 10
TEST_TRUNCATED_OBJECT_CONTENT = b"abcde" * 2
TEST_PRESIGNED_URL = "https://example.com"


class TestGetExecutionLogTrimmedWithPresignedUrlRead:
    def test_log_not_exists(self, mocker):
        # Patch to raise exception
        mocker.patch("src.lib.clients.execution_log.ExecutionLogManager.get_log_stream",
                     side_effect=ExecutionLogNotFoundException(""))

        with pytest.raises(ExecutionLogNotFoundException):
            get_execution_log_truncated_with_presigned_url_read(
                tenant_id="tenant_id",
                jit_event_id="jit_event_id",
                execution_id="execution_id",
                max_bytes=100,
            )

    def test_log_exists_max_bytes_is_larger_than_log_size(self, mocker):
        mocker.patch(
            "src.lib.clients.execution_log.ExecutionLogManager.get_log_stream",
            return_value=Mock(
                stream=Mock(
                    read=Mock(return_value=TEST_OBJECT_CONTENT)
                ),
                content_length=50
            )
        )
        mocker.patch(
            "src.lib.clients.execution_log.ExecutionLogManager.get_log_presigned_url_read",
            return_value=TEST_PRESIGNED_URL,
        )

        result: GetTruncatedLogWithPresignedResult = get_execution_log_truncated_with_presigned_url_read(
            tenant_id='tenant_id',
            jit_event_id='jit_event_id',
            execution_id='execution_id',
            max_bytes=100
        )

        assert result.content == TEST_OBJECT_CONTENT.decode()
        assert result.truncated is False
        assert result.presigned_url_read == TEST_PRESIGNED_URL

    def test_log_exists_max_bytes_is_smaller_than_log_size(self, mocker):
        mocker.patch(
            "src.lib.clients.execution_log.ExecutionLogManager.get_log_stream",
            return_value=Mock(
                stream=Mock(
                    # Mock read to return the first `amt` bytes
                    read=Mock(side_effect=lambda amt: TEST_OBJECT_CONTENT[:amt])
                ),
                content_length=50
            )
        )
        mocker.patch(
            "src.lib.clients.execution_log.ExecutionLogManager.get_log_presigned_url_read",
            return_value=TEST_PRESIGNED_URL
        )

        result: GetTruncatedLogWithPresignedResult = get_execution_log_truncated_with_presigned_url_read(
            tenant_id='tenant_id',
            jit_event_id='jit_event_id',
            execution_id='execution_id',
            max_bytes=10
        )

        assert result.content == TEST_TRUNCATED_OBJECT_CONTENT.decode()
        assert result.truncated is True
        assert result.presigned_url_read == TEST_PRESIGNED_URL

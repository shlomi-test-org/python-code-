from http import HTTPStatus

from src.handlers.get_execution_log import handler
from src.lib.clients.execution_log import ExecutionLogNotFoundException
from src.lib.cores.execution_log import GetTruncatedLogWithPresignedResult
from tests.component.fixtures import get_handler_event

MOCK_EVENT = get_handler_event(path_parameters={
    "jit_event_id": "jit_event_id",
    "execution_id": "execution_id",
})


class TestExecutionLogHandler:
    def test_with_valid_result(self, mocker):
        mocker = mocker.patch("src.handlers.get_execution_log.get_execution_log_truncated_with_presigned_url_read",
                              return_value=GetTruncatedLogWithPresignedResult(
                                  content="content",
                                  truncated=False,
                                  presigned_url_read="presigned_url_read",
                              ))
        response = handler(MOCK_EVENT, {})
        assert response['statusCode'] == HTTPStatus.OK

    def test_with_none_result(self, mocker):
        mocker = mocker.patch("src.handlers.get_execution_log.get_execution_log_truncated_with_presigned_url_read",
                              side_effect=ExecutionLogNotFoundException(s3_object_key="s3_object_key"))
        response = handler(MOCK_EVENT, {})
        assert response['statusCode'] == HTTPStatus.NOT_FOUND

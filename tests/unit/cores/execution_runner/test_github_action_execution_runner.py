from unittest.mock import patch
from uuid import uuid4

import pytest
from jit_utils.jit_clients.authentication_service.client import AuthenticationService
from test_utils.aws.mock_eventbridge import mock_eventbridge

from src.lib.constants import EXECUTION_EVENT_BUS_NAME
from src.lib.constants import FETCH_LOGS_EVENT_DETAIL_TYPE
from src.lib.constants import JIT_GITHUB_JOB_LOGS_BUCKET_NAME
from src.lib.cores.execution_runner import get_execution_runner, map_runner_to_runner_type
from src.lib.cores.execution_runner.ci_execution_runners import github_action_execution_runner
from src.lib.cores.execution_runner.ci_execution_runners.github_action_execution_runner import (
    GithubActionExecutionRunner,
)
from src.lib.cores.execution_runner.execution_runner import ExecutionRunnerDispatchError
from jit_utils.models.execution import Execution
from src.lib.models.execution_models import ExecutionStatus
from tests.mocks.execution_mocks import MOCK_EXECUTION_CODE_EVENT

MOCK_SUCCESS_TENANT_ID = "MOCK_SUCCESS_TENANT_ID"
MOCK_FAIL_TENANT_ID = "MOCK_FAIL_TENANT_ID"
MOCK_CALLBACK_TOKEN = "some-token"


class GithubServiceMock:
    def dispatch(self, tenant_id, event):
        if tenant_id == MOCK_SUCCESS_TENANT_ID:
            pass
        if tenant_id == MOCK_FAIL_TENANT_ID:
            raise Exception


class TestGithubActionExecutionRunner:
    def test_dispatch__dispatched_successfully(self, mocker):
        mocker.patch.object(AuthenticationService, "get_api_token", return_value=uuid4().hex)
        mocker.patch.object(github_action_execution_runner, "OldGithubService", GithubServiceMock)
        mocker.patch.object(GithubActionExecutionRunner, "store_executions_data_in_db")
        event: Execution = MOCK_EXECUTION_CODE_EVENT.copy()
        event.tenant_id = MOCK_SUCCESS_TENANT_ID
        runner_type = map_runner_to_runner_type(event)
        run_id = runner_type.dispatch(executions=[event], callback_token=MOCK_CALLBACK_TOKEN)
        assert run_id is None

    def test_dispatch__dispatch_failed(self, mocker):
        mocker.patch.object(AuthenticationService, "get_api_token", return_value=uuid4().hex)
        mocker.patch.object(github_action_execution_runner, "OldGithubService", GithubServiceMock)
        mocker.patch.object(GithubActionExecutionRunner, "store_executions_data_in_db")
        event: Execution = MOCK_EXECUTION_CODE_EVENT.copy()
        event.tenant_id = MOCK_FAIL_TENANT_ID
        runner_type = map_runner_to_runner_type(event)
        with pytest.raises(ExecutionRunnerDispatchError):
            runner_type.dispatch(executions=[event], callback_token=MOCK_CALLBACK_TOKEN)

    def test_fetch_logs(self, mocker):
        event: Execution = Execution(
            **MOCK_EXECUTION_CODE_EVENT.dict(exclude_none=True),
            run_id="500",
            status=ExecutionStatus.RUNNING,
        )
        # mocked_put_event = mocker.patch("src.lib.cores.execution_runner.github_action_execution_runner.EventsClient.put_event")  # noqa: E501
        logs_key = f"{event.tenant_id}/{event.jit_event_id}-{event.execution_id}.log"
        expected_log_link = f"https://s3.console.aws.amazon.com/s3/object/{JIT_GITHUB_JOB_LOGS_BUCKET_NAME}?prefix={logs_key}"  # noqa: E501
        runner: GithubActionExecutionRunner = get_execution_runner(event)

        with mock_eventbridge(bus_name=EXECUTION_EVENT_BUS_NAME) as get_sent_events:
            assert expected_log_link == runner.logs_url
            assert type(runner) is GithubActionExecutionRunner
            runner._send_fetch_logs_request_event()
            sent_events = get_sent_events()

            assert len(sent_events) == 1
            assert sent_events[0]['detail-type'] == FETCH_LOGS_EVENT_DETAIL_TYPE
            assert sent_events[0]['detail'] == {
                "tenant_id": event.tenant_id,
                "logs_key": logs_key,
                "run_id": event.run_id,
                "vendor": event.vendor,
            }

    @patch('src.lib.cores.execution_runner.ci_execution_runners.github_action_execution_runner.EventsClient.put_event')
    def test_terminate__success(self, mocked_put_event):
        event: Execution = Execution(
            **MOCK_EXECUTION_CODE_EVENT.dict(exclude_none=True),
            run_id="500",
            status=ExecutionStatus.RUNNING,
        )
        runner = get_execution_runner(event)
        runner.terminate()
        assert mocked_put_event.called

    def test_terminate__fail(self, mocker):
        event: Execution = Execution(
            **MOCK_EXECUTION_CODE_EVENT.dict(exclude_none=True),
            run_id="500",
            status=ExecutionStatus.RUNNING,
        )
        # We want to fail the termination because of missing data
        event.context.installation.owner = None
        runner = get_execution_runner(event)
        with pytest.raises(Exception):
            runner.terminate()

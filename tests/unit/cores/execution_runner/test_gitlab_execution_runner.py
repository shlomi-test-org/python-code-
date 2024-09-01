import responses

import pytest
from jit_utils.models.oauth.entities import VendorEnum

from src.lib.cores.execution_runner import map_runner_to_runner_type
from src.lib.cores.execution_runner.ci_execution_runners import GitlabExecutionRunner
from src.lib.cores.execution_runner.execution_runner import ExecutionRunnerDispatchError
from jit_utils.models.execution import Execution
from tests.component.mock_responses.mock_authentication_service import mock_get_internal_token_api
from tests.component.mock_responses.mock_gitlab_service import mock_gitlab_service_dispatch
from tests.mocks.execution_mocks import MOCK_EXECUTION_CODE_EVENT

MOCK_SUCCESS_TENANT_ID = "MOCK_SUCCESS_TENANT_ID"
MOCK_FAIL_TENANT_ID = "MOCK_FAIL_TENANT_ID"
MOCK_CALLBACK_TOKEN = "some-token"


class TestGitlabExecutionRunner:

    @responses.activate
    def test_dispatch__dispatched_successfully(self, executions_manager):
        event: Execution = MOCK_EXECUTION_CODE_EVENT.copy()
        event.tenant_id = MOCK_SUCCESS_TENANT_ID
        event.vendor = VendorEnum.GITLAB
        mock_get_internal_token_api()
        mock_gitlab_service_dispatch([event])

        runner_type = map_runner_to_runner_type(event)
        assert runner_type == GitlabExecutionRunner
        run_id = runner_type.dispatch(executions=[event], callback_token=MOCK_CALLBACK_TOKEN)
        assert run_id == "0"

    @responses.activate
    def test_dispatch__dispatch_failed(self, executions_manager):
        event: Execution = MOCK_EXECUTION_CODE_EVENT.copy()
        event.tenant_id = MOCK_FAIL_TENANT_ID
        event.vendor = VendorEnum.GITLAB
        mock_get_internal_token_api()
        mock_gitlab_service_dispatch(None)

        runner_type = map_runner_to_runner_type(event)
        assert runner_type == GitlabExecutionRunner
        with pytest.raises(ExecutionRunnerDispatchError):
            runner_type.dispatch(executions=[event], callback_token=MOCK_CALLBACK_TOKEN)

import datetime
from typing import Optional
from uuid import uuid4

import pytest
from jit_utils.jit_clients.asset_service.client import AssetService
from jit_utils.jit_clients.authentication_service.client import AuthenticationService
from jit_utils.models.execution_context import Runner
from jit_utils.models.controls import ControlType

from src.lib.cores.execution_runner.ci_execution_runners.github_action_execution_runner \
    import GithubActionExecutionRunner
import src.lib.cores.executions_core
from src.lib.constants import EXECUTION_DISPATCH_EXECUTION_STATUS_EVENT_DETAIL_TYPE
from src.lib.constants import CI_RUNNER_EXECUTION_TIMEOUT
from src.lib.constants import CI_RUNNER_DISPATCHED_TIMEOUT
from src.lib.constants import WATCHDOG_GRACE_PERIOD
from src.lib.cores.execution_runner.execution_runner import ExecutionRunner
from src.lib.cores.execution_runner.execution_runner import ExecutionRunnerDispatchError
from src.lib.cores.executions_core import complete_execution
from src.lib.cores.executions_core import update_control_status
from src.lib.clients.github_service import GithubService as OldGithubService
from src.lib.cores.utils.truncate import MAX_LINE_THRESHOLD
from src.lib.cores.utils.truncate import TRUNCATION_LINE
from jit_utils.models.execution import Execution
from src.lib.models.execution_models import ExecutionDispatchUpdateEvent
from src.lib.models.execution_models import ExecutionStatus
from src.lib.models.execution_models import UpdateRequest
from tests.mocks.asset_mocks import MOCK_ASSET
from tests.mocks.execution_mocks import generate_mock_executions
from tests.mocks.execution_mocks import MOCK_EXECUTION
from tests.mocks.execution_mocks import MOCK_EXECUTION_CODE_EVENT
from tests.mocks.execution_mocks import MOCK_EXECUTION_CODE_EVENT_ENRICHMENT
from tests.mocks.execution_mocks import MOCK_EXECUTION_ENRICHMENT
from tests.mocks.execution_mocks import MOCK_REGISTER_REQUEST
from tests.mocks.execution_mocks import MOCK_UPDATE_REQUEST
from tests.mocks.tenant_mocks import MOCK_TENANT_ID
from tests.unit.data.test_executions_manager import assert_db_item_length


@pytest.mark.parametrize('execution', [MOCK_EXECUTION,
                                       MOCK_EXECUTION_ENRICHMENT])
def test_complete_execution(mocker, execution):
    update_execution_manager = mocker.patch.object(src.lib.cores.executions_core.ExecutionsManager, 'update_execution')
    get_execution_by_jit_event_id_and_execution_id = mocker.patch.object(
        src.lib.cores.executions_core.ExecutionsManager,
        'get_execution_by_jit_event_id_and_execution_id',
        return_value=MOCK_EXECUTION)
    mocked_free_resource = mocker.patch.object(
        src.lib.cores.executions_core,
        'free_resource')

    send_to_event_bus = mocker.patch.object(src.lib.cores.executions_core, 'send_execution_event')

    complete_execution(MOCK_UPDATE_REQUEST, execution)

    assert update_execution_manager.called
    assert send_to_event_bus.called
    assert mocked_free_resource.called
    assert get_execution_by_jit_event_id_and_execution_id.called == (not execution)


def test_update_control_status(mocker):
    update_execution_manager = mocker.patch.object(
        src.lib.cores.executions_core.ExecutionsManager, "update_control_completed_data"
    )

    update_control_status(MOCK_UPDATE_REQUEST)

    assert update_execution_manager.called


def test_update_control_status_over_400k_stderr_and_error_body(executions_manager):
    """
    Test the update control status of an execution with a stderr and error body over 400kb
    """
    raw_string_over_400kb = ("aa" * 80 + "\n") * (400 * 1024 // 82)
    error_body = raw_string_over_400kb
    stderr = raw_string_over_400kb

    assert_db_item_length(executions_manager, 0)
    mock_execution = generate_mock_executions(1, MOCK_TENANT_ID, ExecutionStatus.RUNNING)[0]
    executions_manager.create_execution(mock_execution)
    items = executions_manager.table.scan()["Items"]
    assert len(items) == 1
    assert Execution(**items[0]) == mock_execution

    execution = update_control_status(
        UpdateRequest(
            tenant_id=mock_execution.tenant_id,
            jit_event_id=mock_execution.jit_event_id,
            execution_id=mock_execution.execution_id,
            status=ExecutionStatus.COMPLETED,
            has_findings=False,
            control_type=ControlType.DETECTION,
            error_body=error_body,
            job_output={"test1": ["test2"]},
            stderr=stderr,
        )
    )

    assert TRUNCATION_LINE in execution.stderr
    assert execution.stderr.count('\n') == MAX_LINE_THRESHOLD
    assert TRUNCATION_LINE in execution.error_body
    assert execution.error_body.count('\n') == MAX_LINE_THRESHOLD


def test_dispatch_execution__enrichment(mocker, monkeypatch):
    send_execution_event_mock = mocker.patch("src.lib.cores.executions_core.send_execution_event")
    mocker.patch.object(AuthenticationService, "get_api_token", return_value=uuid4().hex)
    mocker.patch.object(AssetService, "get_asset", return_value=MOCK_ASSET)
    mocker.patch.object(src.lib.cores.executions_core, "get_execution_runner", ExecutionRunnerMock)
    mocker.patch.object(GithubActionExecutionRunner, "store_executions_data_in_db")
    mocker.patch.object(OldGithubService, "dispatch")

    src.lib.cores.executions_core.dispatch_executions([MOCK_EXECUTION_CODE_EVENT_ENRICHMENT])

    assert send_execution_event_mock.call_count == 1
    assert send_execution_event_mock.call_args.args[1] == EXECUTION_DISPATCH_EXECUTION_STATUS_EVENT_DETAIL_TYPE


def test_dispatch_execution(mocker, monkeypatch):
    send_execution_event_mock = mocker.patch("src.lib.cores.executions_core.send_execution_event")
    mocker.patch.object(AuthenticationService, "get_api_token", return_value=uuid4().hex)
    mocker.patch.object(AssetService, "get_asset", return_value=MOCK_ASSET)
    mocker.patch.object(src.lib.cores.executions_core, "get_execution_runner", ExecutionRunnerMock)
    mocker.patch.object(GithubActionExecutionRunner, "store_executions_data_in_db")
    mocker.patch.object(OldGithubService, "dispatch")
    src.lib.cores.executions_core.dispatch_executions([MOCK_EXECUTION_CODE_EVENT])

    assert send_execution_event_mock.call_count == 1
    assert send_execution_event_mock.call_args.args[1] == EXECUTION_DISPATCH_EXECUTION_STATUS_EVENT_DETAIL_TYPE


def test_dispatch_execution__dispatch_failed(mocker, monkeypatch):
    mocker.patch.object(AuthenticationService, "get_api_token", return_value=uuid4().hex)
    mocker.patch.object(AssetService, "get_asset", return_value=MOCK_ASSET)
    failing_execution = MOCK_EXECUTION.copy()
    failing_execution.execution_id = ExecutionRunnerMock.fail_execution_id
    send_execution_event_mock = mocker.patch("src.lib.cores.executions_core.send_execution_event")
    mocker.patch.object(src.lib.cores.executions_core, "get_execution_runner", ExecutionRunnerMock)
    mocker.patch.object(GithubActionExecutionRunner, "store_executions_data_in_db")
    mocker.patch.object(OldGithubService, "dispatch")
    src.lib.cores.executions_core.dispatch_executions([failing_execution])

    assert send_execution_event_mock.call_count == 1


def test_dispatched_request_core(executions_manager):
    execution: Execution = MOCK_EXECUTION_CODE_EVENT.copy()
    execution.status = ExecutionStatus.DISPATCHING
    executions_manager.create_execution(execution)

    updated_execution = src.lib.cores.executions_core.dispatched_request_core(ExecutionDispatchUpdateEvent(
        tenant_id=execution.tenant_id,
        jit_event_id=execution.jit_event_id,
        execution_id=execution.execution_id,
    ))

    assert updated_execution.status == ExecutionStatus.DISPATCHED
    assert updated_execution.dispatched_at
    assert updated_execution.dispatched_at_ts
    assert updated_execution.execution_timeout
    now = datetime.datetime.utcnow()
    timeout = datetime.datetime.fromisoformat(updated_execution.execution_timeout)
    assert timeout < now + datetime.timedelta(seconds=CI_RUNNER_DISPATCHED_TIMEOUT)
    assert timeout > now + datetime.timedelta(seconds=CI_RUNNER_DISPATCHED_TIMEOUT - 10)


@pytest.mark.parametrize('status', [
    ExecutionStatus.DISPATCHED,
    ExecutionStatus.DISPATCHING])
def test_register_execution(mocker, executions_manager, status):
    send_execution_event_mock = mocker.patch("src.lib.cores.executions_core.send_execution_event")
    execution = MOCK_EXECUTION_CODE_EVENT.copy()
    execution.status = status

    register_request = MOCK_REGISTER_REQUEST.copy()
    register_request.tenant_id = execution.tenant_id
    register_request.jit_event_id = execution.jit_event_id
    register_request.execution_id = execution.execution_id
    execution.execution_timeout = "2022-10-30T21:23:12"
    register_request.status = ExecutionStatus.RUNNING
    executions_manager.create_execution(execution)

    updated_execution = src.lib.cores.executions_core.register_execution(register_request)

    assert updated_execution.status == ExecutionStatus.RUNNING
    assert send_execution_event_mock.call_count == 1
    now = datetime.datetime.utcnow()
    timeout = datetime.datetime.fromisoformat(updated_execution.execution_timeout)
    assert timeout < now + datetime.timedelta(seconds=CI_RUNNER_EXECUTION_TIMEOUT + WATCHDOG_GRACE_PERIOD)
    assert timeout > now + datetime.timedelta(seconds=CI_RUNNER_EXECUTION_TIMEOUT + WATCHDOG_GRACE_PERIOD - 10)


class ExecutionRunnerMock(ExecutionRunner):
    fail_execution_id = "fail_execution_id"
    mock_run_id = "mock_run_id"

    def __init__(self, execution: Execution):
        self._execution = execution

    def dispatch(self) -> Optional[str]:
        if self._execution.execution_id == self.fail_execution_id:
            raise ExecutionRunnerDispatchError
        return self.mock_run_id

    def terminate(self):
        pass

    @property
    def default_dispatched_state_timeout(self) -> int:
        return CI_RUNNER_DISPATCHED_TIMEOUT

    @property
    def default_running_state_timeout(self) -> int:
        return CI_RUNNER_EXECUTION_TIMEOUT

    @property
    def runner_type(self) -> Runner:
        return self._execution.context.job.runner.type

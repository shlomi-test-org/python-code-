from uuid import uuid4

import pytest
from jit_utils.jit_clients.authentication_service.client import AuthenticationService
from jit_utils.models.execution import ExecutionStatus
from jit_utils.models.oauth.entities import VendorEnum

from src.handlers.validate_dispatched_execution import handler
from src.lib.cores.execution_runner import map_runner_to_runner_type
from src.lib.exceptions import ExecutionNotExistException
from src.lib.exceptions import InvalidExecutionStatusException
from tests.factories import ExecutionDataFactory
from tests.factories import ExecutionFactory
from tests.mocks.execution_mocks import MOCK_ASSET_NAME
from tests.mocks.execution_mocks import MOCK_EXECUTION_CONTEXT_CODE_EXECUTION
from tests.mocks.execution_mocks import MOCK_EXECUTION_ID
from tests.mocks.execution_mocks import MOCK_JIT_EVENT_ID
from tests.mocks.tenant_mocks import MOCK_TENANT_ID

VALID_REQUEST = {
    "tenant_id": MOCK_TENANT_ID,
    "execution_id": MOCK_EXECUTION_ID,
    "jit_event_id": MOCK_JIT_EVENT_ID,
    "target_asset_name": MOCK_ASSET_NAME,
}


def _execute_handler(execution_mock, executions_manager, mocker, request):
    cls = map_runner_to_runner_type(execution_mock)
    execution_data_mock = ExecutionDataFactory.build(
        tenant_id=execution_mock.tenant_id,
        execution_id=execution_mock.execution_id,
        jit_event_id=execution_mock.jit_event_id,
        execution_data_json=cls.get_dispatch_execution_event(execution_mock, "encrypted").json(),
    )
    executions_manager.write_multiple_execution_data([execution_data_mock])
    executions_manager.create_execution(execution_mock)
    mocker.patch(
        "src.lib.cores.get_execution_data_core.ExecutionsManager",
        return_value=executions_manager,
    )
    return handler(request, None)


@pytest.mark.parametrize(
    "dispatch_status", [ExecutionStatus.DISPATCHED, ExecutionStatus.DISPATCHING]
)
def test_validate_execution_success(mocker, executions_manager, dispatch_status):
    mocker.patch.object(
        AuthenticationService, "get_api_token", return_value=uuid4().hex
    )

    execution_mock = ExecutionFactory.build(
        tenant_id=MOCK_TENANT_ID,
        execution_id=MOCK_EXECUTION_ID,
        jit_event_id=MOCK_JIT_EVENT_ID,
        status=dispatch_status,
        asset_name=MOCK_ASSET_NAME,
        context=MOCK_EXECUTION_CONTEXT_CODE_EXECUTION,
        vendor=VendorEnum.GITHUB,
    )
    result = _execute_handler(execution_mock, executions_manager, mocker, VALID_REQUEST)
    assert result is True


@pytest.mark.parametrize(
    "dispatch_status", [ExecutionStatus.DISPATCHED, ExecutionStatus.DISPATCHING]
)
def test_validate_without_asset_name_requested(
    mocker, executions_manager, dispatch_status
):
    mocker.patch.object(
        AuthenticationService, "get_api_token", return_value=uuid4().hex
    )

    execution_mock = ExecutionFactory.build(
        tenant_id=MOCK_TENANT_ID,
        execution_id=MOCK_EXECUTION_ID,
        jit_event_id=MOCK_JIT_EVENT_ID,
        status=dispatch_status,
        asset_name="STAM_ASSET",
        context=MOCK_EXECUTION_CONTEXT_CODE_EXECUTION,
        vendor=VendorEnum.GITHUB,
    )

    request_without_asset_name = VALID_REQUEST.copy()
    request_without_asset_name.pop("target_asset_name")
    result = _execute_handler(
        execution_mock, executions_manager, mocker, request_without_asset_name
    )
    assert result is True


@pytest.mark.parametrize(
    "dispatch_status", [ExecutionStatus.DISPATCHED, ExecutionStatus.DISPATCHING]
)
def test_invalid_asset_name_requested(mocker, executions_manager, dispatch_status):
    mocker.patch.object(
        AuthenticationService, "get_api_token", return_value=uuid4().hex
    )

    execution_mock = ExecutionFactory.build(
        tenant_id=MOCK_TENANT_ID,
        execution_id=MOCK_EXECUTION_ID,
        jit_event_id=MOCK_JIT_EVENT_ID,
        status=dispatch_status,
        asset_name="STAM_ASSET",
        context=MOCK_EXECUTION_CONTEXT_CODE_EXECUTION,
        vendor=VendorEnum.GITHUB,
    )

    with pytest.raises(InvalidExecutionStatusException):
        _execute_handler(execution_mock, executions_manager, mocker, VALID_REQUEST)


@pytest.mark.parametrize(
    "invalid_status",
    [
        status
        for status in ExecutionStatus
        if status not in [ExecutionStatus.DISPATCHING, ExecutionStatus.DISPATCHED]
    ],
)
def test_invalid_execution_status(mocker, executions_manager, invalid_status):

    mocker.patch.object(
        AuthenticationService, "get_api_token", return_value=uuid4().hex
    )
    execution_mock = ExecutionFactory.build(
        tenant_id=MOCK_TENANT_ID,
        execution_id=MOCK_EXECUTION_ID,
        jit_event_id=MOCK_JIT_EVENT_ID,
        status=invalid_status,
        context=MOCK_EXECUTION_CONTEXT_CODE_EXECUTION,
        vendor=VendorEnum.GITHUB,
    )

    with pytest.raises(InvalidExecutionStatusException):
        _execute_handler(execution_mock, executions_manager, mocker, VALID_REQUEST)


@pytest.mark.parametrize(
    "tenant_id, execution_id, jit_event_id, is_exception_expected",
    [
        (
            "INVALID_TENANT_ID",
            MOCK_EXECUTION_ID,
            MOCK_JIT_EVENT_ID,
            True,
        ),  # Invalid tenant_id
        (
            MOCK_TENANT_ID,
            "INVALID_EXECUTION_ID",
            MOCK_JIT_EVENT_ID,
            True,
        ),  # Invalid execution_id
        (
            MOCK_TENANT_ID,
            MOCK_EXECUTION_ID,
            "INVALID_JIT_EVENT_ID",
            True,
        ),  # Invalid jit_event_id
    ],
)
def test_execution_data_validity(
    mocker,
    executions_manager,
    tenant_id,
    execution_id,
    jit_event_id,
    is_exception_expected,
):
    mocker.patch.object(
        AuthenticationService, "get_api_token", return_value=uuid4().hex
    )

    execution_mock = ExecutionFactory.build(
        tenant_id=tenant_id,
        execution_id=execution_id,
        jit_event_id=jit_event_id,
        status=ExecutionStatus.DISPATCHED,  # Use a valid status here
        context=MOCK_EXECUTION_CONTEXT_CODE_EXECUTION,
        vendor=VendorEnum.GITHUB,
    )

    with pytest.raises(ExecutionNotExistException):
        _execute_handler(execution_mock, executions_manager, mocker, VALID_REQUEST)

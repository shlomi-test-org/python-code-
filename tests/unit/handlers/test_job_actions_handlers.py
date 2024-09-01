import json
from http import HTTPStatus

import pytest
from freezegun import freeze_time
from jit_utils.models.execution_context import Runner

import src.handlers.update_execution
from src.handlers.update_execution import register_handler
from jit_utils.models.execution import Execution

from tests.component.fixtures import get_handler_event
from tests.mocks.execution_mocks import generate_mock_executions
from tests.mocks.execution_mocks import MOCK_EXECUTION
from tests.mocks.execution_mocks import MOCK_TENANT_ID
from tests.mocks.execution_mocks import MOCK_UPDATE_REQUEST


@pytest.mark.parametrize('mock_execution', [
    generate_mock_executions(1, MOCK_TENANT_ID)[0],
    generate_mock_executions(1, MOCK_TENANT_ID, job_runner=Runner.JIT)[0]
])
def test_register_handler(monkeypatch, mock_execution):
    mock_http_event = get_handler_event(tenant_id=MOCK_TENANT_ID, body=mock_execution.dict())
    monkeypatch.setattr(src.handlers.update_execution, "register_execution", lambda execution: mock_execution)
    response = register_handler(mock_http_event, {})
    assert response["statusCode"] == HTTPStatus.OK
    assert Execution(**json.loads(response["body"])) == mock_execution


@freeze_time("2022-12-12T12:12:12.123456")
def test_register_handler__microseconds_is_always_present(monkeypatch):
    mock_execution = generate_mock_executions(1, MOCK_TENANT_ID)[0]
    mock_http_event = get_handler_event(tenant_id=MOCK_TENANT_ID, body=mock_execution.dict())
    monkeypatch.setattr(src.handlers.update_execution, "register_execution", lambda execution: execution)
    response = register_handler(mock_http_event, {})
    response_body = json.loads(response["body"])
    assert response_body["registered_at"] == "2022-12-12T12:12:12.123456"


def test_update_control_status_handler(monkeypatch):
    mock_http_event = get_handler_event(tenant_id=MOCK_TENANT_ID, body=MOCK_UPDATE_REQUEST.dict())
    monkeypatch.setattr(src.handlers.update_execution, "update_control_status", lambda execution: MOCK_EXECUTION)
    response = src.handlers.update_execution.update_control_status_handler(mock_http_event, {})
    assert response["statusCode"] == HTTPStatus.OK
    assert Execution(**json.loads(response["body"])) == MOCK_EXECUTION


def test_update_control_status_handler__job_output(monkeypatch):
    """
    Test that the job output is updated when entrypoint calls completed route
    """
    mock_update_request = MOCK_UPDATE_REQUEST.copy(update={"job_output": {"test1": ["test2"]}})
    mock_execution_with_job_output = MOCK_EXECUTION.copy(update={"job_output": {"test1": ["test2"]}})
    mock_http_event = get_handler_event(tenant_id=MOCK_TENANT_ID, body=mock_update_request.dict())
    monkeypatch.setattr(src.handlers.update_execution, "update_control_status",
                        lambda execution: mock_execution_with_job_output)
    response = src.handlers.update_execution.update_control_status_handler(mock_http_event, {})
    assert response["statusCode"] == HTTPStatus.OK
    assert Execution(**json.loads(response["body"])) == mock_execution_with_job_output

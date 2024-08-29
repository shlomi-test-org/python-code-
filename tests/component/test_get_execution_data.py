import json
from http import HTTPStatus
from uuid import uuid4

import boto3
import pytest
import responses

from moto import mock_events
from moto import mock_ssm
from moto import mock_sts

from jit_utils.jit_clients.authentication_service.client import AuthenticationService
from jit_utils.models.execution import DispatchExecutionEvent, ExecutionStatus
from jit_utils.models.execution_context import AuthType, CI_RUNNERS
from jit_utils.models.oauth.entities import VendorEnum

from src.handlers.get_execution_data import handler

from src.lib.cores.execution_runner import map_runner_to_runner_type
from tests.component.fixtures import get_handler_event
from tests.component.mock_responses.mock_github_service import mock_get_github_status_api
from tests.factories import ExecutionDataFactory
from tests.factories import ExecutionFactory
from tests.mocks.execution_mocks import CONTEXT_WITH_AUTH_AND_SECRETS
from tests.mocks.execution_mocks import MOCK_EXECUTION_CONTEXT_CODE_EXECUTION
from tests.mocks.execution_mocks import MOCK_EXECUTION_ID
from tests.mocks.execution_mocks import MOCK_JIT_EVENT_ID
from tests.mocks.tenant_mocks import MOCK_TENANT_ID

VALID_REQUEST = get_handler_event(
    tenant_id=MOCK_TENANT_ID,
    path_parameters={"execution_id": MOCK_EXECUTION_ID},
    query_string_parameters={"jit_event_id": MOCK_JIT_EVENT_ID}
)


@pytest.fixture
def mock_ssm_fixture():
    with mock_ssm():
        yield


@pytest.fixture
def mock_sts_fixture():
    with mock_sts():
        yield


@pytest.fixture
def mock_event_bridge_fixture():
    with mock_events():
        yield


GET_EXECUTION_DATA_PARAMS = [
    {
        "mock_execution_context": MOCK_EXECUTION_CONTEXT_CODE_EXECUTION,
        "expected_secrets": {},
        "has_auth_config": False,
    },
    {
        "mock_execution_context": CONTEXT_WITH_AUTH_AND_SECRETS,
        "expected_secrets": {
            "AWS_ACCESS_DUMMY": "secret",
            "AWS_ACCESS_DUMMY2": "secret",
            "Dummy_sec": "secret",
            "Dummy_sec2": "secret",
            "secret1": "secret",
        },
        "has_auth_config": True,
    },
]

GET_EXECUTION_DATA_PARAMS__BAD_REQUEST_ERROR_CASES = [
    {
        "request": {
            "requestContext": {"authorizer": {"tenant_id": MOCK_TENANT_ID, "frontegg_token_type": "userToken"}},
            "pathParameters": {"execution_id": MOCK_EXECUTION_ID},
            "queryStringParameters": {"jit_event_id": MOCK_JIT_EVENT_ID},
        },
        "execution_mock": ExecutionFactory.build(
            tenant_id=MOCK_TENANT_ID,
            execution_id=MOCK_EXECUTION_ID,
            jit_event_id=MOCK_JIT_EVENT_ID,
            status=ExecutionStatus.DISPATCHED,
            context=MOCK_EXECUTION_CONTEXT_CODE_EXECUTION,
        ),
        "expected_status_code": HTTPStatus.UNAUTHORIZED,
        "expected_response_body": {"message": "Invalid token type"},
    },
    {
        "request": {
            "requestContext": {"authorizer": {"tenant_id": MOCK_TENANT_ID, "frontegg_token_type": "tenantApiToken"}},
            "pathParameters": {"execution_id": MOCK_EXECUTION_ID},
            "queryStringParameters": {"jit_event_id": MOCK_JIT_EVENT_ID},
        },
        "execution_mock": ExecutionFactory.build(
            tenant_id=MOCK_TENANT_ID,
            execution_id=MOCK_EXECUTION_ID,
            jit_event_id=MOCK_JIT_EVENT_ID,
            status=ExecutionStatus.COMPLETED,
            context=MOCK_EXECUTION_CONTEXT_CODE_EXECUTION,
        ),
        "expected_status_code": HTTPStatus.BAD_REQUEST,
        "expected_response_body": {
            "message": (
                f"Execution {MOCK_EXECUTION_ID} is in status "
                f"{ExecutionStatus.COMPLETED} and not dispatching/dispatched"
            )
        },
    },
    {
        "request": {
            "requestContext": {"authorizer": {"tenant_id": MOCK_TENANT_ID, "frontegg_token_type": "tenantApiToken"}},
            "pathParameters": {},
            "queryStringParameters": {},
        },
        "execution_mock": ExecutionFactory.build(
            tenant_id=MOCK_TENANT_ID,
            execution_id=MOCK_EXECUTION_ID,
            jit_event_id=MOCK_JIT_EVENT_ID,
            status=ExecutionStatus.COMPLETED,
            context=MOCK_EXECUTION_CONTEXT_CODE_EXECUTION,
        ),
        "expected_status_code": HTTPStatus.BAD_REQUEST,
        "expected_response_body": {
            "message": "Received invalid request, request should contain valid jit_event_id and execution_id"
        },
    },
    {
        "request": {
            "requestContext": {"authorizer": {"tenant_id": "tenant_id", "frontegg_token_type": "tenantApiToken"}},
            "pathParameters": {"execution_id": "execution_id"},
            "queryStringParameters": {"jit_event_id": "jit_event_id"},
        },
        "execution_mock": ExecutionFactory.build(
            tenant_id=MOCK_TENANT_ID,
            execution_id=MOCK_EXECUTION_ID,
            jit_event_id=MOCK_JIT_EVENT_ID,
            status=ExecutionStatus.DISPATCHED,
            context=MOCK_EXECUTION_CONTEXT_CODE_EXECUTION,
        ),
        "expected_status_code": HTTPStatus.NOT_FOUND,
        "expected_response_body": {
            "message": "Execution not exist in the DB. tenant_id='tenant_id' "
                       "jit_event_id='jit_event_id' execution_id='execution_id'"
        },
    }
]


def _execute_handler(execution_mock, executions_manager, mocker, request):
    mocker.patch("src.lib.aws_common.update_asset_status")
    mocker.patch("src.lib.cores.prepare_data_for_execution_core.get_secret_value", return_value="secret")
    mocker.patch.object(AuthenticationService, "get_api_token", return_value=uuid4().hex)

    cls = map_runner_to_runner_type(execution_mock)
    execution_data_mock = ExecutionDataFactory.build(
        tenant_id=execution_mock.tenant_id,
        execution_id=execution_mock.execution_id,
        jit_event_id=execution_mock.jit_event_id,
        execution_data_json=cls.get_dispatch_execution_event(execution_mock, "encrypted").json(),
        retrieved_at=None,
    )
    executions_manager.write_multiple_execution_data([execution_data_mock])
    executions_manager.create_execution(execution_mock)
    mocker.patch("src.lib.cores.get_execution_data_core.ExecutionsManager", return_value=executions_manager)
    response = handler(request, None)
    status_code, response_body = response["statusCode"], json.loads(response["body"])
    return response_body, status_code


@pytest.mark.parametrize("get_execution_data_params", GET_EXECUTION_DATA_PARAMS)
def test_get_execution_data(
        mocker, executions_manager, get_execution_data_params, mock_ssm_fixture, mock_sts_fixture,
        mock_event_bridge_fixture
):
    mock_execution_context, expected_secrets, has_auth_config = get_execution_data_params.values()
    execution_mock = ExecutionFactory.build(
        tenant_id=MOCK_TENANT_ID,
        execution_id=MOCK_EXECUTION_ID,
        jit_event_id=MOCK_JIT_EVENT_ID,
        status=ExecutionStatus.DISPATCHED,
        context=mock_execution_context,
    )
    if mock_execution_context.job.runner.type in CI_RUNNERS:
        execution_mock.vendor = VendorEnum.GITHUB
    response_body, status_code = _execute_handler(execution_mock, executions_manager, mocker, VALID_REQUEST)
    dispatch_execution_event = DispatchExecutionEvent(**json.loads(response_body["data"]))
    assert status_code == HTTPStatus.OK
    assert dispatch_execution_event.execution_data.execution_id == execution_mock.execution_id
    assert (
            dispatch_execution_event.context.json(exclude_none=True, exclude={"auth"}) ==
            execution_mock.context.json(exclude_none=True, exclude={"auth"})
    )
    assert dispatch_execution_event.secrets == expected_secrets
    assert bool(dispatch_execution_event.context.auth) is has_auth_config

    # Call the handler again with the same params
    response = handler(VALID_REQUEST, None)
    status_code, response_body = response["statusCode"], json.loads(response["body"])
    assert status_code == HTTPStatus.GONE, f"Expected status code {HTTPStatus.GONE} but got {status_code}"
    assert response_body == {}, f"Expected empty response body but got {response_body}"


def test_get_execution_data__setup_auth_aws_iam_role_error(mocker, executions_manager, mock_event_bridge_fixture):
    class MockStsClient:
        def assume_role(self, *args, **kwargs):
            raise

    mock_client = MockStsClient()
    original_client = boto3.client

    def get_client_mock(*args, **kwargs):
        if args[0] == "sts":
            return mock_client
        else:
            return original_client(*args, **kwargs)

    mocker.patch("boto3.client", side_effect=get_client_mock)
    mock_execution_context = CONTEXT_WITH_AUTH_AND_SECRETS
    execution_mock = ExecutionFactory.build(
        tenant_id=MOCK_TENANT_ID,
        execution_id=MOCK_EXECUTION_ID,
        jit_event_id=MOCK_JIT_EVENT_ID,
        status=ExecutionStatus.DISPATCHED,
        context=mock_execution_context,
    )
    response_body, status_code = _execute_handler(execution_mock, executions_manager, mocker, VALID_REQUEST)
    assert status_code == HTTPStatus.FAILED_DEPENDENCY
    assert response_body["message"] == "Error while assuming role"


@responses.activate
def test_get_execution_data__setup_auth_scm_token_with_github_error(mocker, executions_manager):
    mock_execution_context = CONTEXT_WITH_AUTH_AND_SECRETS.copy()
    mock_execution_context.job.runner.setup.auth_type = AuthType.SCM_TOKEN
    mock_get_github_status_api(
        mock_execution_context.installation.app_id, mock_execution_context.installation.installation_id, None
    )
    execution_mock = ExecutionFactory.build(
        tenant_id=MOCK_TENANT_ID,
        execution_id=MOCK_EXECUTION_ID,
        jit_event_id=MOCK_JIT_EVENT_ID,
        status=ExecutionStatus.DISPATCHED,
        context=mock_execution_context,
    )
    response_body, status_code = _execute_handler(execution_mock, executions_manager, mocker, VALID_REQUEST)
    assert status_code == HTTPStatus.FAILED_DEPENDENCY
    assert "Failed to get access token for" in response_body["message"]

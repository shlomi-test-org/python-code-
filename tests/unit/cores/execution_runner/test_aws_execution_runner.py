from typing import Dict
from unittest.mock import patch
from uuid import uuid4

import boto3
import pytest
import responses
from jit_utils.aws_clients.kms import KmsClient
from jit_utils.jit_clients.authentication_service.client import AuthenticationService
from jit_utils.models.execution_context import Runner
from moto import mock_events
from moto import mock_ssm
from moto import mock_sts

from src.lib.cores.execution_runner import get_execution_runner, map_runner_to_runner_type
from src.lib.cores.execution_runner.execution_runner import ExecutionRunner
from src.lib.cores.execution_runner.cloud_execution_runners import AwsExecutionRunner
from src.lib.cores.execution_runner.cloud_execution_runners.cloud_execution_runner import CloudExecutionRunner
from src.lib.cores.prepare_data_for_execution_core import add_secrets_values
from jit_utils.models.execution import Execution
from src.lib.models.execution_models import ExecutionStatus
from tests.mocks.execution_mocks import MOCK_EXECUTION_FARGATE_ZAP_ACCOUNT_EVENT
from tests.mocks.execution_mocks import MOCK_EXECUTION_FARGATE_ZAP_ACCOUNT_EVENT_CONTAINS_SECRETS
from tests.mocks.execution_mocks import MOCK_EXECUTION_FARGATE_ZAP_ACCOUNT_EVENT_CONTAINS_SECRETS_AND_ASSUME_ROLE
from tests.mocks.execution_mocks import MOCK_EXECUTION_ID
from tests.mocks.execution_mocks import MOCK_JIT_EVENT_ID
from tests.mocks.tenant_mocks import MOCK_TENANT_ID

MOCK_RUN_ID = "MOCK_RUN_ID"


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


class KmsClientMock:
    def encrypt(self, key_id: str, secret: str) -> str:
        return "encrypted"

    def encrypt_dict(self, key_id: str, dictionary: Dict[str, str]) -> Dict[str, str]:
        return {key: "encrypted" for key in dictionary.keys()}


@pytest.fixture
def init_mock_ssm(mock_ssm_fixture):
    ssm = boto3.client("ssm", region_name="us-east-1")
    ssm.put_parameter(
        Name=f"/data/{MOCK_TENANT_ID}/AWS_ACCESS_DUMMY",
        Value="AWS_DUMMY_VALUE",
        Type="SecureString",
    )
    ssm.put_parameter(
        Name=f"/data/{MOCK_TENANT_ID}/AWS_ACCESS_DUMMY2",
        Value="AWS_DUMMY_VALUE2",
        Type="SecureString",
    )
    ssm.put_parameter(
        Name=f"/data/{MOCK_TENANT_ID}/secret1",
        Value="value1",
        Type="SecureString",
    )
    ssm.put_parameter(
        Name=f"/data/{MOCK_TENANT_ID}/Dummy_sec",
        Value="Dummy_value",
        Type="SecureString",
    )
    ssm.put_parameter(
        Name=f"/data/{MOCK_TENANT_ID}/Dummy_sec2",
        Value="Dummy_value2",
        Type="SecureString",
    )


class TestCloudExecutionRunner:
    @patch("src.lib.cores.execution_runner.cloud_execution_runners.aws_execution_runner.BatchClient.terminate")
    def test_terminate__success(self, mocked_terminate):
        mock_execution = Execution(
            **MOCK_EXECUTION_FARGATE_ZAP_ACCOUNT_EVENT.dict(exclude_none=True),
            run_id="123",
            status=ExecutionStatus.RUNNING,
        )
        runner = get_execution_runner(mock_execution)
        runner.terminate()
        assert mocked_terminate.call_count == 1
        assert mocked_terminate.call_args[0][0] == mock_execution.run_id

    @patch("src.lib.cores.execution_runner.cloud_execution_runners.aws_execution_runner.BatchClient.terminate")
    def test_terminate__failure(self, mocked_terminate, mocker):
        mocked_terminate.side_effect = Exception
        mock_execution = Execution(
            **MOCK_EXECUTION_FARGATE_ZAP_ACCOUNT_EVENT.dict(exclude_none=True),
            status=ExecutionStatus.DISPATCHED,
        )
        runner = get_execution_runner(mock_execution)
        with pytest.raises(Exception):
            runner.terminate()
        assert mocked_terminate.call_count == 1

    @responses.activate
    @pytest.mark.parametrize("test_details", [
        {"execution_model_mock": MOCK_EXECUTION_FARGATE_ZAP_ACCOUNT_EVENT_CONTAINS_SECRETS,
         "expected_result": {"AWS_ACCESS_DUMMY": "AWS_DUMMY_VALUE",
                             "AWS_ACCESS_DUMMY2": "AWS_DUMMY_VALUE2",
                             "Dummy_sec": "Dummy_value",
                             "Dummy_sec2": "Dummy_value2",
                             "secret1": "value1"}}
    ])
    @pytest.mark.usefixtures("mock_ssm_fixture", "init_mock_ssm", "prepare_env_vars")
    def test_get_dispatch_execution_event_with_secrets(self, mocker, test_details):
        mocker.patch.object(AuthenticationService, "get_api_token", return_value=uuid4().hex)
        mocker.patch.object(ExecutionRunner, "store_executions_data_in_db", return_value="")
        execution_model_mock = test_details["execution_model_mock"]
        expected_result = test_details["expected_result"]
        runner = get_execution_runner(execution_model_mock)
        callback_token = ExecutionRunner.store_executions_data_in_db([execution_model_mock])
        cls = map_runner_to_runner_type(execution_model_mock)
        dispatch_event = cls.get_dispatch_execution_event(execution_model_mock, callback_token)
        add_secrets_values(dispatch_event)
        assert isinstance(runner, CloudExecutionRunner)
        assert dispatch_event.secrets == expected_result
        assert runner.runner_type == Runner.JIT

    @responses.activate
    def test_dispatch(self, mocker, mock_ssm_fixture, init_mock_ssm):
        client = boto3.client("batch", region_name="us-east-1")
        original_client = boto3.client

        class MockBatchClient:
            @property
            def exceptions(self):
                return client.exceptions

            def submit_job(self, *args, **kwargs):
                expected_environment = [
                    {"name": "TENANT_ID", "value": MOCK_TENANT_ID},
                    {"name": "JIT_EVENT_ID", "value": MOCK_JIT_EVENT_ID},
                    {"name": "EXECUTION_ID", "value": MOCK_EXECUTION_ID},
                    {"name": "KMS_KEY_ID", "value": ""},
                ]
                expected_container_overrides = {
                    "environment": expected_environment,
                    "command": [
                        '--jit-token-encrypted', "encrypted", '--base-url', 'https://api.jit-dev.io', '--event-id',
                        'dd7cb9e9-dca6-4012-9401-63a842ee77e9', '--execution-id', '8429eb01-2ecb-43fc-933f-4e20480f5306'
                    ]
                }
                assert kwargs["jobDefinition"] == "some-job-definition__latest"
                assert kwargs["containerOverrides"] == expected_container_overrides
                return {"data": "success", "jobId": "jobId"}

        def get_client_mock(*args, **kwargs):
            if args[0] == "batch":
                return MockBatchClient()
            else:
                return original_client(*args, **kwargs)

        mocker.patch("boto3.client", side_effect=get_client_mock)
        mocker.patch.object(AuthenticationService, "get_api_token", return_value=uuid4().hex)
        mocker.patch.object(ExecutionRunner, "store_executions_data_in_db", return_value="")
        mocker.patch("src.lib.cores.prepare_data_for_execution_core.get_secret_value", return_value="secret")
        mocker.patch.object(KmsClient, "encrypt_dict", return_value=KmsClientMock().encrypt_dict)
        mocker.patch.object(KmsClient, "encrypt", KmsClientMock().encrypt)
        execution_model_mock = MOCK_EXECUTION_FARGATE_ZAP_ACCOUNT_EVENT_CONTAINS_SECRETS.copy()
        runner_type = map_runner_to_runner_type(execution_model_mock)
        run_id = runner_type.dispatch(executions=[execution_model_mock], callback_token="some-token")
        assert run_id == "jobId"

    @pytest.mark.usefixtures("mock_sts_fixture", "mock_ssm_fixture", "prepare_env_vars", "mock_event_bridge_fixture")
    def test_assume_role_with_credential_parameters(self, mocker):
        mocker.patch.object(AuthenticationService, "get_api_token", return_value=uuid4().hex)
        mocker.patch.object(ExecutionRunner, "store_executions_data_in_db", return_value="")
        mocker.patch("src.lib.aws_common.update_asset_status")

        execution_model_mock = MOCK_EXECUTION_FARGATE_ZAP_ACCOUNT_EVENT_CONTAINS_SECRETS_AND_ASSUME_ROLE

        runner = get_execution_runner(execution_model_mock)
        assert isinstance(runner, AwsExecutionRunner)

        callback_token = ExecutionRunner.store_executions_data_in_db([execution_model_mock])
        cls = map_runner_to_runner_type(execution_model_mock)
        dispatch_event = cls.get_dispatch_execution_event(execution_model_mock, callback_token)
        add_secrets_values(dispatch_event)
        aws_config = dispatch_event.context.auth.config
        assert "aws_access_key_id" in aws_config
        assert "aws_secret_access_key" in aws_config
        assert "aws_session_token" in aws_config
        assert "region_name" in aws_config
        assert isinstance(runner, AwsExecutionRunner)

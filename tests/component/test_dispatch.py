import base64
from typing import List
import uuid
from argparse import Namespace

import boto3
import pytest
import responses
from google.cloud.batch_v1 import Job
from google.cloud.kms_v1 import EncryptResponse
from jit_utils.models.execution import ExecutionStatus
from jit_utils.models.oauth.entities import VendorEnum
from moto import mock_batch, mock_ssm
from moto import mock_ec2
from moto import mock_iam
from test_utils.aws.idempotency import mock_idempotent_decorator
from test_utils.aws.mock_eventbridge import mock_eventbridge
from test_utils.aws.moto_wrappers import mock_kms_fixt  # noqa: F401

from src.handlers import dispatch_execution
from src.lib.constants import TENANT_ID_ENV_VAR
from src.lib.constants import EXECUTION_DEPROVISIONED_EXECUTION_EVENT_DETAIL_TYPE
from src.lib.constants import JIT_EVENT_ID_ENV_VAR
from src.lib.constants import EXECUTION_ID_ENV_VAR
from src.lib.constants import GCP_KMS_KEY_NAME_ENV_VAR
from src.lib.constants import EXECUTION_DISPATCH_EXECUTION_STATUS_EVENT_DETAIL_TYPE
from src.lib.constants import EXECUTION_EVENT_BUS_NAME
from src.lib.cores.execution_runner.cloud_execution_runners.gcp_execution_runner import JOB_ID_MAX_LENGTH
from src.lib.gcp_common import _create_job_creation_request
from jit_utils.models.execution import Execution
from src.lib.models.execution_models import MultipleExecutionsIdentifiers, ExecutionDispatchUpdateEvent, UpdateRequest
from tests.component.common import create_job_definition
from tests.component.mock_responses.mock_asset_service import mock_get_asset_by_id
from tests.component.mock_responses.mock_authentication_service import mock_get_internal_token_api
from tests.component.mock_responses.mock_github_service import mock_github_service_dispatch
from tests.component.mock_responses.mock_gitlab_service import mock_gitlab_service_dispatch
from tests.conftest import create_batch_queue
from tests.factories import ExecutionFactory
from tests.mocks.execution_mocks import MOCK_EXECUTION_CONTEXT_CODE_EXECUTION, MOCK_EXECUTION_ID
from tests.mocks.execution_mocks import MOCK_EXECUTION_CONTEXT_JIT_RUNNER
from tests.mocks.tenant_mocks import MOCK_TENANT_ID


@pytest.fixture()
def mock_batch_client():
    with mock_iam(), mock_ec2(), mock_batch():
        create_batch_queue()
        create_job_definition("prowler__latest")


@pytest.fixture
def mock_ssm_client():
    with mock_ssm():
        ssm = boto3.client("ssm", region_name="us-east-1")
        ssm.put_parameter(
            Name="/local/infra/gcp-batch/dispatch-gcp-credentials",
            Value="{}",
            Type="SecureString",
        )


@pytest.mark.parametrize(
    "execution_context", [MOCK_EXECUTION_CONTEXT_CODE_EXECUTION, MOCK_EXECUTION_CONTEXT_JIT_RUNNER]
)
@responses.activate
def test_handler__happy_flow(mocker, execution_context, executions_manager, mock_kms_fixt, mock_batch_client):  # noqa
    vendor = VendorEnum.GITHUB if execution_context == MOCK_EXECUTION_CONTEXT_CODE_EXECUTION else VendorEnum.AWS
    asset_id = "asset_id"
    mock_get_asset_by_id(asset_id=asset_id)
    mock_get_internal_token_api()
    mock_github_service_dispatch()
    mock_idempotent_decorator(
        mocker=mocker,
        module_to_reload=dispatch_execution,
        decorator_name="idempotent",
    )
    key_metadata = mock_kms_fixt.create_key(Description="Test key")
    mocker.patch(
        "src.lib.cores.execution_runner.cloud_execution_runners.aws_execution_runner.ECS_TASK_KMS_ARN",
        key_metadata["KeyMetadata"]["KeyId"],
    )

    # Call the handler
    with mock_eventbridge(bus_name=EXECUTION_EVENT_BUS_NAME) as get_sent_events:
        executions = []
        for _ in range(10):
            execution = ExecutionFactory().build(
                tenant_id=MOCK_TENANT_ID,
                context=execution_context,
                control_name="Run Prowler",
                asset_id=asset_id,
                vendor=vendor,
                jit_event_id="123456"
            )
            execution.context.job.steps[0].uses = "jit.registry.io/prowler:latest"
            executions_manager.create_execution(execution)
            executions.append(execution)

        execution_identifiers = MultipleExecutionsIdentifiers.group_by_jit_event_id(executions)[0]
        dispatch_execution.handler({"detail": execution_identifiers.dict()}, None)
        sent_events: List[ExecutionDispatchUpdateEvent] = get_sent_events()

    assert len(sent_events) == 10

    # assert all executions that were passed to the handler were dispatched
    for execution in executions:
        assert any(
            event["detail"]["execution_id"] == execution.execution_id
            for event in sent_events
        )

    # Assert values:
    assert sent_events[0]["detail-type"] == EXECUTION_DISPATCH_EXECUTION_STATUS_EVENT_DETAIL_TYPE
    for event in sent_events:
        full_event = ExecutionDispatchUpdateEvent(**event["detail"])
        # Find the execution that matches the current event
        matching_execution = next(
            (execution for execution in executions if execution.execution_id == full_event.execution_id),
            None
        )
        if matching_execution is None:
            raise ValueError(f"No execution found with id {full_event.execution_id}")

        expected_event = ExecutionDispatchUpdateEvent(
            tenant_id=MOCK_TENANT_ID,
            jit_event_id=matching_execution.jit_event_id,
            execution_id=matching_execution.execution_id,
            run_id=full_event.run_id,  # run_id is given after the operation so can't know what it would be
        )
        assert full_event == expected_event

        if execution_context == MOCK_EXECUTION_CONTEXT_CODE_EXECUTION:
            # github actions provider don't provide run_id on dispatch
            assert full_event.run_id is None
        else:
            # other provider returns run_id
            assert full_event.run_id is not None

        # Get all items from the mock table
        sample_execution_id = executions[0].execution_id
        execution_items = executions_manager.table.scan()["Items"]
        sample_executions = [
            record for record in execution_items
            if record["execution_id"] == sample_execution_id
        ]

        assert len(sample_executions) == 2  # execution and the execution data entry

        # Sort the items so the execution data entry is last
        sample_executions.sort(key=lambda item: item["SK"])
        execution_data_entry = sample_executions[1]

        assert execution_data_entry["SK"] == (
            f"EXECUTION#{sample_execution_id.lower()}#ENTITY#execution_data"
        )


@responses.activate
@pytest.mark.parametrize("is_active, is_covered", [(False, False), (True, False), (False, True)])
def test_handler__asset_not_found(mocker, executions_manager, mock_batch_client, is_active,
                                  is_covered):  # noqa
    asset_id = "asset_id"
    mock_get_asset_by_id(asset_id=asset_id, is_active=is_active, is_covered=is_covered)
    mock_get_internal_token_api()
    mock_github_service_dispatch()
    mock_idempotent_decorator(
        mocker=mocker,
        module_to_reload=dispatch_execution,
        decorator_name="idempotent",
    )

    # Call the handler
    with mock_eventbridge(bus_name=EXECUTION_EVENT_BUS_NAME) as get_sent_events:
        execution = ExecutionFactory().build(
            tenant_id=MOCK_TENANT_ID,
            context=MOCK_EXECUTION_CONTEXT_CODE_EXECUTION,
            task_token=None,
            control_name="Run Prowler",
            asset_id=asset_id,
        )

        execution.context.job.steps[0].uses = "jit.registry.io/prowler:latest"
        executions_manager.create_execution(execution)
        execution_identifiers = MultipleExecutionsIdentifiers.group_by_jit_event_id([execution])[0]
        dispatch_execution.handler({"detail": execution_identifiers.dict()}, None)
        sent_events = get_sent_events()

    # Assert values:
    assert len(sent_events) == 1
    assert sent_events[0]["detail-type"] == EXECUTION_DEPROVISIONED_EXECUTION_EVENT_DETAIL_TYPE
    assert sent_events[0]["detail"] == {
        'error_body': 'Asset not found', 'execution_id': execution.execution_id,
        'jit_event_id': execution.jit_event_id, 'status': 'failed',
        'status_details': {'message': 'Asset not found'},
        'tenant_id': execution.tenant_id,
        'errors': [],
    }
    called_urls = [call.request.url for call in responses.calls]
    assert 'http://github-service/dispatch' not in called_urls


@responses.activate
@pytest.mark.parametrize(
    "test_configurations, success",
    [
        [
            # High specs ECR requirements image - should success
            {
                "ecr_image": "registry.jit.io/prowler:latest",
                "expected_image_uri": "us-central1-docker.pkg.dev/jit-test-project/prowler/prowler:latest",
                "expected_high_specs": True,
                "control_name": "Run Prowler",
                "expected_job_name": f"run-prowler-{MOCK_EXECUTION_ID}"
            },
            True,
        ],
        [
            # Bad ECR image (no tag) - should fail
            {
                "ecr_image": "registry.jit.io/prowler",
                "expected_error": "Illegal image ecr path registry.jit.io/prowler, no tag",
                "control_name": "Run Prowler",
            },
            False,
        ],
        [
            # High specs ECR requirements image - should success
            {
                "ecr_image": "aaaa/aaaa/aaaa/aaa/aaaa/kics:not-hardened-main",
                "expected_image_uri": "us-central1-docker.pkg.dev/jit-test-project/kics/kics:not-hardened-main",
                "expected_high_specs": False,
                "control_name": "Run Prowler",
                "expected_job_name": f"run-prowler-{MOCK_EXECUTION_ID}"
            },
            True,
        ],
        [
            # Bad ECR image (no host) - should fail
            {
                "ecr_image": "prowler:latest",
                "expected_error": "Illegal image ecr path prowler:latest, no ECR ARN",
                "control_name": "Run Prowler",
            },
            False,
        ],
        [
            # Long job name - should success after shortening
            {
                "ecr_image": "aaaa/aaaa/aaaa/aaa/aaaa/kics:not-hardened-main",
                "expected_image_uri": "us-central1-docker.pkg.dev/jit-test-project/kics/kics:not-hardened-main",
                "expected_high_specs": False,
                "control_name": "this-Is-a-Very_VERY-long control Name nananananananana",
                "expected_job_name": f"trol-name-nananananananana-{MOCK_EXECUTION_ID}"
            },
            True,
        ],
    ]
)
def test_handler_jit_gcp_runner(mocker, executions_manager, mock_ssm_client, test_configurations, success):
    """
    Test for the dispatch-execution handler with JIT GCP runner.

    This test uses parameterization to test different scenarios including successful and failing cases based on
    the Elastic Container Registry (ECR) image configurations. It mocks GCP SDK functionalities and a feature flag.

    The test covers the following scenarios:
    1. A valid ECR image with high specs requirements (like prowler/zap), expecting a successful dispatch.
    2. An invalid ECR image without a tag, expecting a failure.
    3. A valid ECR image with no high specs requirements (all other controls), expecting a successful dispatch.
    4. An invalid ECR image without a host, expecting a failure.

    The test asserts the behavior of the job creation process based on the provided image configurations and
    checks the number of events dispatched as well as their types, depending on the success or failure of the test case.
    """
    # MOCK GCP SDK (no special mocking library)
    asset_id = "asset_id"
    mock_get_asset_by_id(asset_id=asset_id)
    mocker.patch("google.oauth2.service_account.Credentials.from_service_account_info", return_value={"creds": "creds"})
    mocker.patch(
        "google.cloud.kms_v1.KeyManagementServiceClient.encrypt", return_value=EncryptResponse(ciphertext=b"encrypted")
    )

    def mock_create_job(create_job_request: Namespace) -> Job:
        if len(create_job_request.job_id) > JOB_ID_MAX_LENGTH:
            raise
        return Job(name="run_id")

    create_job_mock = mocker.patch("google.cloud.batch_v1.BatchServiceClient.create_job", side_effect=mock_create_job)
    # MOCK FEATURE FLAG
    mocker.patch("src.lib.cores.execution_runner.cloud_execution_runners.evaluate_feature_flag", return_value=True)
    mock_idempotent_decorator(mocker=mocker, module_to_reload=dispatch_execution, decorator_name="idempotent")
    mock_get_internal_token_api()

    execution: Execution = ExecutionFactory().build(
        tenant_id=MOCK_TENANT_ID,
        context=MOCK_EXECUTION_CONTEXT_JIT_RUNNER,
        task_token=None,
        execution_id=MOCK_EXECUTION_ID,
        asset_id=asset_id,
    )
    execution.context.job.steps[0].uses = test_configurations["ecr_image"]
    execution.control_name = test_configurations["control_name"]

    executions_manager.create_execution(execution)
    execution_identifiers = MultipleExecutionsIdentifiers.group_by_jit_event_id([execution])[0]

    with mock_eventbridge(bus_name=EXECUTION_EVENT_BUS_NAME) as get_sent_events:
        dispatch_execution.handler({"detail": execution_identifiers.dict()}, None)
        sent_events = get_sent_events()

        if success:
            expected_job_creation_request = _create_job_creation_request(
                image_uri=test_configurations["expected_image_uri"],
                job_name=test_configurations["expected_job_name"],
                env={
                    TENANT_ID_ENV_VAR: execution.tenant_id,
                    JIT_EVENT_ID_ENV_VAR: execution.jit_event_id,
                    EXECUTION_ID_ENV_VAR: execution.execution_id,
                    GCP_KMS_KEY_NAME_ENV_VAR: "projects/jit-test-project/locations/us-central1/keyRings/"
                                              "controls-gcp-runner-key-ring/cryptoKeys/controls-gcp-runner-crypto-key",
                    # noqa
                },
                command=[
                    "--jit-token-encrypted", base64.b64encode(b"encrypted").decode('utf-8'),
                    "--base-url", "https://api.jit-dev.io",
                    "--event-id", execution.jit_event_id,
                    "--execution-id", execution.execution_id,
                ],
                high_specs=test_configurations["expected_high_specs"],
                max_run_time=7500,
            )
            assert create_job_mock.call_args[0][0] == expected_job_creation_request
            assert len(sent_events) == 1
            assert sent_events[0]["detail-type"] == EXECUTION_DISPATCH_EXECUTION_STATUS_EVENT_DETAIL_TYPE
            full_event = ExecutionDispatchUpdateEvent(**sent_events[0]["detail"])
            expected_event = ExecutionDispatchUpdateEvent(
                tenant_id=MOCK_TENANT_ID,
                jit_event_id=execution.jit_event_id,
                execution_id=execution.execution_id,
                run_id=full_event.run_id,  # run_id is given after the operation so can't know what it would be
            )
            assert full_event == expected_event
        else:
            assert create_job_mock.call_count == 0
            assert len(sent_events) == 1
            assert sent_events[0]["detail-type"] == EXECUTION_DEPROVISIONED_EXECUTION_EVENT_DETAIL_TYPE
            full_event = UpdateRequest(**sent_events[0]["detail"])
            expected_event = UpdateRequest(
                tenant_id=MOCK_TENANT_ID,
                jit_event_id=execution.jit_event_id,
                execution_id=execution.execution_id,
                status=ExecutionStatus.FAILED,
                status_details={"message": test_configurations["expected_error"]},
                error_body=test_configurations["expected_error"],
            )
            assert full_event == expected_event


@responses.activate
def test_handler_gitlab_execution_runner(mocker, executions_manager):
    mock_idempotent_decorator(mocker=mocker, module_to_reload=dispatch_execution, decorator_name="idempotent")
    asset_id = str(uuid.uuid4())
    mock_get_asset_by_id(asset_id=asset_id)
    execution: Execution = ExecutionFactory().build(
        tenant_id=MOCK_TENANT_ID,
        context=MOCK_EXECUTION_CONTEXT_CODE_EXECUTION,
        task_token=None,
        execution_id=MOCK_EXECUTION_ID,
        asset_id=asset_id,
        vendor=VendorEnum.GITLAB,
    )
    executions_manager.create_execution(execution)
    execution_identifiers = MultipleExecutionsIdentifiers.group_by_jit_event_id([execution])[0]
    mock_get_internal_token_api()
    mock_gitlab_service_dispatch([execution])

    with mock_eventbridge(bus_name=EXECUTION_EVENT_BUS_NAME) as sent_messages:
        dispatch_execution.handler({"detail": execution_identifiers.dict()}, None)
        sent_events = sent_messages()
        assert len(sent_events) == 1
        assert sent_events[0]["detail-type"] == EXECUTION_DISPATCH_EXECUTION_STATUS_EVENT_DETAIL_TYPE
        full_event = ExecutionDispatchUpdateEvent(**sent_events[0]["detail"])
        expected_event = ExecutionDispatchUpdateEvent(
            tenant_id=MOCK_TENANT_ID,
            jit_event_id=execution.jit_event_id,
            execution_id=execution.execution_id,
            run_id=0,
        )
        assert full_event == expected_event

        assert len(executions_manager.table.scan()["Items"]) == 2
        execution_id_db = executions_manager.table.scan()["Items"][0]
        assert execution_id_db["execution_id"] == execution.execution_id
        execution_data_entry = executions_manager.table.scan()["Items"][1]
        assert execution_data_entry["execution_id"] == execution.execution_id
        assert execution_data_entry["SK"] == (
            f"EXECUTION#{execution.execution_id.lower()}#ENTITY#execution_data"
        )

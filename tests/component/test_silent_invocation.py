import uuid
from http import HTTPStatus
from typing import Dict, Tuple

import pytest
import responses
from test_utils.aws import idempotency
from moto import mock_batch, mock_ec2, mock_iam, mock_s3, mock_sts

from src.handlers import silent_invocation
from src.lib.models.execution_models import SilentInvocationRequest

from tests.conftest import create_batch_queue
from tests.component.common import create_job_definition
from tests.component.mock_responses.mock_asset_service import mock_get_all_assets_api
from tests.component.mock_responses.mock_authentication_service import mock_get_internal_token_api
from tests.component.mock_responses.mock_plan_service import mock_get_integration_file_for_tenant_api
from tests.component.mock_responses.mock_tenant_service import mock_get_installations_by_vendor_api


@pytest.fixture()
def mock_batch_client():
    with mock_iam(), mock_ec2(), mock_batch():
        create_batch_queue()
        create_job_definition("prowler__latest")
        yield


@pytest.fixture
def mock_sts_fixture():
    with mock_sts():
        yield


@responses.activate
@mock_s3
@pytest.mark.usefixtures('mock_sts_fixture')
def test_handler__dry_run(mocker, mock_batch_client):
    tenant_id = str(uuid.uuid4())

    mock_get_internal_token_api()
    mock_get_all_assets_api(tenant_id=tenant_id)
    mock_get_integration_file_for_tenant_api()
    mock_get_installations_by_vendor_api(tenant_id=tenant_id, vendor='aws')

    idempotency.mock_idempotent_decorator(
        mocker=mocker,
        module_to_reload=silent_invocation,
        decorator_name='idempotent',
    )

    silent_invocation_request = SilentInvocationRequest(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        control_name="prowler",
        job_definition="prowler__latest",
        is_dry_run=True,
    )

    from src.handlers.silent_invocation import handler
    response = handler(silent_invocation_request.dict(), None)

    assert response == (HTTPStatus.OK, {'jobs': []})


@responses.activate
@mock_s3
@pytest.mark.usefixtures('mock_sts_fixture')
def test_handler__non_dry_run(mocker, mock_batch_client):
    tenant_id = str(uuid.uuid4())

    mock_get_internal_token_api()
    mock_get_all_assets_api(tenant_id=tenant_id)
    mock_get_integration_file_for_tenant_api()
    mock_get_installations_by_vendor_api(tenant_id=tenant_id, vendor='aws')

    idempotency.mock_idempotent_decorator(
        mocker=mocker,
        module_to_reload=silent_invocation,
        decorator_name='idempotent',
    )

    silent_invocation_request = SilentInvocationRequest(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        control_name="prowler",
        job_definition="prowler__latest",
        is_dry_run=False,
    )

    response: Tuple[int, Dict] = silent_invocation.handler(silent_invocation_request.dict(), None)

    assert response[0] == HTTPStatus.OK
    assert len(response[1]['jobs']) == 1
    assert "job_id" in response[1]['jobs'][0]
    assert "job_name" in response[1]['jobs'][0]

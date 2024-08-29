from contextvars import Context
from typing import Dict
from uuid import uuid4

import pytest
from jit_utils.aws_clients.s3 import S3Client
from test_utils.lambdas.delete_tenant_data import get_matching_tenant_data
from test_utils.lambdas.delete_tenant_data import TenantDataResponse

from src.handlers.delete_tenant_data import handler
from src.lib.constants import S3_EXECUTION_OUTPUTS_BUCKET_NAME
from src.lib.data.executions_manager import ExecutionsManager
from src.lib.data.resources_manager import ResourcesManager
from tests.mocks.execution_mocks import MOCK_EXECUTION_CODE_EVENT
from tests.mocks.resources_mocks import generate_mock_resources

_S3_CLIENT = None
_EXECUTIONS_MANAGER = None
_RESOURCES_MANAGER = None


def _get_s3_client() -> S3Client:
    global _S3_CLIENT
    if _S3_CLIENT is None:
        _S3_CLIENT = S3Client()
    return _S3_CLIENT


def _get_executions_manager() -> ExecutionsManager:
    global _EXECUTIONS_MANAGER
    if _EXECUTIONS_MANAGER is None:
        _EXECUTIONS_MANAGER = ExecutionsManager()
    return _EXECUTIONS_MANAGER


def _get_resources_manager() -> ResourcesManager:
    global _RESOURCES_MANAGER
    if _RESOURCES_MANAGER is None:
        _RESOURCES_MANAGER = ResourcesManager()
    return _RESOURCES_MANAGER


def _create_mock_tenant_delete_event(tenant_id: str) -> Dict:
    return {
        'detail': {
            'tenant_id': tenant_id
        }
    }


def _create_mock_tenant_s3_file(tenant_id: str) -> None:
    key_name = str(uuid4())
    content = str(uuid4())

    key = f'{tenant_id}/{key_name}'

    _get_s3_client().put_object(bucket_name=S3_EXECUTION_OUTPUTS_BUCKET_NAME, key=key, body=content)


def _create_execution_for_tenant(tenant_id: str) -> None:
    e = MOCK_EXECUTION_CODE_EVENT.copy()
    e.tenant_id = tenant_id
    e.jit_event_id = str(uuid4())
    e.execution_id = str(uuid4())
    _get_executions_manager().create_execution(e)


def _create_resource_for_tenant(tenant_id: str) -> None:
    r = generate_mock_resources(tenant_id)[0]
    _get_resources_manager().create_resource(r)


def _asset_matching_data(should_match: bool, tenant_data: TenantDataResponse) -> None:
    for data_type in tenant_data.values():
        if should_match:
            assert len(data_type['matching']) > 0
        else:
            assert len(data_type['matching']) == 0
        assert len(data_type['not_matching']) > 0


@pytest.mark.parametrize('should_delete', [True, False])
def test_delete_tenant_data_handler(should_delete, mocked_tables, mocked_s3_executions_outputs_bucket):
    """
    Test that delete_tenant_data deletes all tenant data from S3 and DynamoDB

    Setup:
        - Create 10 random tenant items
        - Create 10 tenant items

    Test:
        - Call delete_tenant_data with a random tenant id

    Assert:
        - 10 random tenant items are still in S3 and DynamoDB
        - 10 tenant items are still in S3 and DynamoDB if should_delete is False
    """

    amount = 10

    tenant_id = str(uuid4())
    random_tenant_id = str(uuid4())

    for _ in range(amount):
        _create_execution_for_tenant(tenant_id)
        _create_execution_for_tenant(random_tenant_id)

        _create_resource_for_tenant(tenant_id)
        _create_resource_for_tenant(random_tenant_id)

        _create_mock_tenant_s3_file(tenant_id)
        _create_mock_tenant_s3_file(random_tenant_id)

    matching_data = get_matching_tenant_data(
        tenant_id,
        [mocked_tables['executions'], mocked_tables['resources']],
        [S3_EXECUTION_OUTPUTS_BUCKET_NAME],
    )
    _asset_matching_data(True, matching_data)

    handler(_create_mock_tenant_delete_event(tenant_id=tenant_id if should_delete else str(uuid4())), Context())

    matching_data = get_matching_tenant_data(
        tenant_id,
        [mocked_tables['resources']],
        [S3_EXECUTION_OUTPUTS_BUCKET_NAME],
    )

    _asset_matching_data(not should_delete, matching_data)

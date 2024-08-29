from uuid import uuid4

import src.lib.cores.create_resources_for_tenant_core
from src.lib.cores.create_resources_for_tenant_core import create_resource_for_tenant
from src.lib.cores.create_resources_for_tenant_core import create_resource_object
from jit_utils.models.execution import ResourceType


def test_create_resource_for_tenant(resources_manager, mocker):
    """
    Test create resources for new tenant
    """
    mock_tenant_id = str(uuid4())
    expected_resources_to_create = [
        create_resource_object(mock_tenant_id, resource_type) for resource_type in ResourceType.values()
    ]

    expected_create_resources_queries = [
        resources_manager.generate_create_resource_query(resource) for resource in expected_resources_to_create
    ]
    mocked_execute_transaction = mocker.patch.object(src.lib.cores.create_resources_for_tenant_core.ResourcesManager,
                                                     'execute_transaction')
    create_resource_for_tenant(mock_tenant_id)
    mocked_execute_transaction.assert_called_once_with(expected_create_resources_queries)

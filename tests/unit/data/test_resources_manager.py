from datetime import datetime
from datetime import timedelta
from uuid import uuid4

import pytest

from src.lib.models.resource_models import Resource
from tests.mocks.resources_mocks import generate_mock_resource_in_use
from tests.mocks.resources_mocks import generate_mock_resources


def assert_db_item_length(resources_manager, expected_length: int):
    items = resources_manager.table.scan()["Items"]
    assert len(items) == expected_length


@pytest.fixture(scope="function")
def mock_resources(resources_manager):
    """
    Fixture that creates a mock resources ofr tenant and returns it
    """
    mock_resources_items = generate_mock_resources(str(uuid4()))
    for mock_resource in mock_resources_items:
        resources_manager.create_resource(mock_resource)

    return mock_resources_items


def test_create_execution(resources_manager):
    """
    Test the creation of an execution
    """
    assert_db_item_length(resources_manager, 0)
    mock_tenant_id = str(uuid4())
    mock_resource = generate_mock_resources(mock_tenant_id)[0]
    resources_manager.create_resource(mock_resource)
    items = resources_manager.table.scan()["Items"]
    assert len(items) == 1
    assert Resource(**items[0]) == mock_resource


def test_increase_resource_in_use__success(resources_manager):
    """
    Test the increase of the resource in use
    """

    # We need to make sure that we have free resources, so the migration will be successful
    mock_tenant_id = str(uuid4())
    mock_resource = generate_mock_resources(mock_tenant_id)[0]
    mock_resource.resources_in_use = 0
    mock_resource.max_resources_in_use = 10
    resources_manager.create_resource(mock_resource)
    assert_db_item_length(resources_manager, 1)
    mock_resource_in_use = generate_mock_resource_in_use(mock_resource.tenant_id, mock_resource.resource_type, 1)[0]

    resources_manager.increase_resource_in_use(mock_resource, mock_resource_in_use)
    items = resources_manager.table.scan()["Items"]
    assert len(items) == len([mock_resource, mock_resource_in_use])
    resource_record = [Resource(**item) for item in items if "RESOURCE_TYPE" in item["SK"]][0]
    assert resource_record.resources_in_use == 1


def test_increase_resource_in_use__failure(resources_manager):
    """
    Test the increase of the resource in use
    It should fail because all the resources are in use
    """

    # We need to make sure that we have free resources, so the migration will be successful
    mock_tenant_id = str(uuid4())
    mock_resource = generate_mock_resources(mock_tenant_id)[0]
    mock_resource.resources_in_use = 10
    mock_resource.max_resources_in_use = 10
    resources_manager.create_resource(mock_resource)
    assert_db_item_length(resources_manager, 1)
    mock_resource_in_use = generate_mock_resource_in_use(mock_resource.tenant_id, mock_resource.resource_type, 1)[0]

    with pytest.raises(Exception):
        resources_manager.increase_resource_in_use(mock_resource, mock_resource_in_use)
    items = resources_manager.table.scan()["Items"]
    assert len(items) == 1
    assert Resource(**items[0]) == mock_resource


def test_decrease_resource_in_use__success(resources_manager):
    """
    Test the decrease of the resource in use
    """

    # We need to make sure that we have free resources, so the migration will be successful
    mock_tenant_id = str(uuid4())
    mock_resource = generate_mock_resources(mock_tenant_id)[0]
    mock_resource.resources_in_use = 1
    mock_resource.max_resources_in_use = 10
    resources_manager.create_resource(mock_resource)
    assert_db_item_length(resources_manager, 1)
    mock_resource_in_use = generate_mock_resource_in_use(mock_resource.tenant_id, mock_resource.resource_type, 1)[0]
    create_resource_in_use_query = resources_manager.generate_create_resource_in_use_query(mock_resource_in_use)
    resources_manager.execute_transaction([create_resource_in_use_query])
    assert_db_item_length(resources_manager, 2)

    resources_manager.decrease_resource_in_use(mock_resource, mock_resource_in_use)
    items = resources_manager.table.scan()["Items"]
    assert len(items) == len([mock_resource])
    # The operation had to decrease the amount of resources in use by 1
    mock_resource.resources_in_use = mock_resource.resources_in_use - 1
    assert Resource(**items[0]) == mock_resource


def test_decrease_resource_in_use__failure(resources_manager):
    """
    Test the decrease of the resource in use
    It should fail because the resource in use does not exist
    """

    # We need to make sure that we have free resources, so the migration will be successful
    mock_tenant_id = str(uuid4())
    mock_resource = generate_mock_resources(mock_tenant_id)[0]
    mock_resource.resources_in_use = 1
    mock_resource.max_resources_in_use = 10
    resources_manager.create_resource(mock_resource)
    mock_resource_in_use = generate_mock_resource_in_use(mock_resource.tenant_id, mock_resource.resource_type, 1)[0]
    assert_db_item_length(resources_manager, 1)

    with pytest.raises(Exception):
        resources_manager.decrease_resource_in_use(mock_resource, mock_resource_in_use)
    items = resources_manager.table.scan()["Items"]
    assert Resource(**items[0]) == mock_resource


def test_get_resources_in_use_exceeded_time_limitation(resources_manager):
    """
    Test the get resources in use exceeded time limitation
    """

    # We need to make sure that we have free resources, so the migration will be successful
    mock_tenant_id = str(uuid4())
    mock_resource = generate_mock_resources(mock_tenant_id)[0]
    resources_to_generate = 10
    mock_resource.resources_in_use = resources_to_generate
    mock_resource.max_resources_in_use = resources_to_generate
    resources_manager.create_resource(mock_resource)
    assert_db_item_length(resources_manager, 1)

    mock_resources_in_use = generate_mock_resource_in_use(mock_resource.tenant_id, mock_resource.resource_type,
                                                          resources_to_generate)
    create_resource_in_use_query = []
    for mock_resource_in_use in mock_resources_in_use:
        mock_resource_in_use.created_at = (datetime.utcnow() - timedelta(hours=2)).isoformat()
        create_resource_in_use_query.append(
            resources_manager.generate_create_resource_in_use_query(mock_resource_in_use))

    resources_manager.execute_transaction(create_resource_in_use_query)
    assert_db_item_length(resources_manager, resources_to_generate + 1)

    time_limitation = (datetime.utcnow() - timedelta(hours=1)).isoformat()
    items, start_key = resources_manager.get_resources_in_use_exceeded_time_limitation(time_limitation)
    assert len(items) == resources_to_generate


def test_get_resources_in_use_exceeded_time_limitation__no_resources_exceeded(resources_manager):
    """
    Test the get resources in use exceeded time limitation
    """

    # We need to make sure that we have free resources, so the migration will be successful
    mock_tenant_id = str(uuid4())
    mock_resource = generate_mock_resources(mock_tenant_id)[0]
    resources_to_generate = 10
    mock_resource.resources_in_use = resources_to_generate
    mock_resource.max_resources_in_use = resources_to_generate
    resources_manager.create_resource(mock_resource)
    assert_db_item_length(resources_manager, 1)

    mock_resources_in_use = generate_mock_resource_in_use(mock_resource.tenant_id, mock_resource.resource_type,
                                                          resources_to_generate)
    create_resource_in_use_query = []
    for mock_resource_in_use in mock_resources_in_use:
        create_resource_in_use_query.append(
            resources_manager.generate_create_resource_in_use_query(mock_resource_in_use))

    resources_manager.execute_transaction(create_resource_in_use_query)
    assert_db_item_length(resources_manager, resources_to_generate + 1)

    time_limitation = (datetime.utcnow() - timedelta(hours=1)).isoformat()
    items, start_key = resources_manager.get_resources_in_use_exceeded_time_limitation(time_limitation)
    assert len(items) == 0

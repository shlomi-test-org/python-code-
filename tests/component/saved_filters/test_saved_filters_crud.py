import json
import uuid

from jit_utils.utils.permissions import Read, Write

from src.handlers.saved_filters import create_saved_filter, edit_saved_filter, get_saved_filters, delete_filter
from tests.component.utils.get_handler_event import get_handler_event
from tests.fixtures import get_saved_filter_sample


def test_create_and_update_saved_filter(mocked_tables):
    """
    Test create saved filter
    Setup:
        1) Mock dynamoDb findings table
    Test:
        1) Call the create_saved_filter
        2) Call the edit_saved_filter
    Assert:
        1) Verify that the saved filter was created
        2) Verify that the saved filter was updated
    """
    # Assign
    tenant_id = str(uuid.uuid4())
    saved_filter_sample = get_saved_filter_sample(tenant_id)[0]
    finding_table, _ = mocked_tables
    event = get_handler_event(
        tenant_id=tenant_id,
        permissions=[Write.FINDINGS],
        body=saved_filter_sample
    )
    # Act 1 - create saved filter
    response = create_saved_filter(event, {})

    # Assert
    assert response['statusCode'] == 200
    assert finding_table.scan()['Count'] == 1
    assert finding_table.scan()['Items'][0]['name'] == saved_filter_sample['name']
    assert not finding_table.scan()['Items'][0]['is_default']

    resulted_saved_filter = json.loads(response['body'])

    # Act 2 - update saved filter
    updated_saved_filter = resulted_saved_filter.copy()
    updated_saved_filter['is_default'] = True
    saved_filter_sample['id'] = resulted_saved_filter['id']

    event = get_handler_event(
        tenant_id=tenant_id,
        permissions=[Write.FINDINGS],
        body=updated_saved_filter
    )
    response = edit_saved_filter(event, {})

    # Assert
    assert response['statusCode'] == 200
    assert finding_table.scan()['Count'] == 1
    assert finding_table.scan()['Items'][0]['name'] == saved_filter_sample['name']
    assert finding_table.scan()['Items'][0]['is_default']


def test_update_is_default_for_saved_filters(mocked_tables):
    """
    Test updating the 'is_default' attribute for saved filters
    Setup:
        1) Mock dynamoDb findings table
    Test:
        1) Insert a saved filter
        2) Update the 'is_default' attribute of the saved filter to True
        3) Insert a new saved filter with a different name and set its 'is_default' attribute to True
    Assert:
        1) Verify that there are two saved filters in total
        2) Verify that the new saved filter has 'is_default' set to True
        3) Verify that the original saved filter has 'is_default' set to False
    """
    # Assign
    tenant_id = str(uuid.uuid4())
    saved_filter_sample = get_saved_filter_sample(tenant_id)[0]
    finding_table, _ = mocked_tables
    event = get_handler_event(
        tenant_id=tenant_id,
        permissions=[Write.FINDINGS],
        body=saved_filter_sample
    )

    # Act 1 - Insert a saved filter
    response = create_saved_filter(event, {})
    assert response['statusCode'] == 200
    assert finding_table.scan()['Count'] == 1
    assert not finding_table.scan()['Items'][0]['is_default']

    # Act 2 - Update the 'is_default' attribute of the saved filter to True
    resulted_saved_filter = json.loads(response['body'])
    updated_saved_filter = resulted_saved_filter.copy()
    updated_saved_filter['is_default'] = True
    event = get_handler_event(
        tenant_id=tenant_id,
        permissions=[Write.FINDINGS],
        body=updated_saved_filter
    )
    response = edit_saved_filter(event, {})
    assert response['statusCode'] == 200

    # Act 3 - Insert a new saved filter with a different name
    new_saved_filter = saved_filter_sample.copy()
    new_saved_filter['name'] = 'new_name'
    event = get_handler_event(
        tenant_id=tenant_id,
        permissions=[Write.FINDINGS],
        body=new_saved_filter,
    )
    response = create_saved_filter(event, {})
    new_resulted_filter = json.loads(response['body'])
    new_resulted_filter['is_default'] = True
    event = get_handler_event(
        tenant_id=tenant_id,
        permissions=[Write.FINDINGS],
        body=new_resulted_filter,
    )
    response = edit_saved_filter(event, {})
    assert response['statusCode'] == 200

    # Assert
    all_filters = finding_table.scan()['Items']
    assert len(all_filters) == 2
    for saved_filter in all_filters:
        if saved_filter['name'] == 'new_name':
            assert saved_filter['is_default'] is True
        else:
            assert saved_filter['is_default'] is False


def test_insert_and_get_saved_filters(mocked_tables):
    """
    Component Test for inserting and retrieving saved filters
    Setup:
        1) Mock dynamoDb findings table
    Test:
        1) Insert multiple saved filters
        2) Retrieve the saved filters using get_saved_filters
    Assert:
        1) Verify that the retrieved saved filters match the inserted ones
    """
    # Assign
    tenant_id = str(uuid.uuid4())
    saved_filter_samples = get_saved_filter_sample(tenant_id)
    finding_table, _ = mocked_tables

    # Act 1 - Insert multiple saved filters
    for saved_filter_sample in saved_filter_samples:
        event = get_handler_event(
            tenant_id=tenant_id,
            permissions=[Write.FINDINGS],
            body=saved_filter_sample
        )
        response = create_saved_filter(event, {})
        assert response['statusCode'] == 200

    # Act 2 - Retrieve the saved filters using get_saved_filters
    event = get_handler_event(
        tenant_id=tenant_id,
        permissions=[Read.FINDINGS],
    )
    response = get_saved_filters(event, {})
    retrieved_filters = json.loads(response['body'])

    # Assert
    assert len(retrieved_filters) == len(saved_filter_samples)
    for saved_filter in saved_filter_samples:
        assert any(filter_item['name'] == saved_filter['name'] for filter_item in retrieved_filters)


def test_delete_saved_filter(mocked_tables):
    """
    Component Test for deleting a saved filter
    Setup:
        1) Mock dynamoDb findings table
    Test:
        1) Insert a saved filter
        2) Retrieve the saved filter to ensure it exists
        3) Delete the saved filter using delete_saved_filter
        4) Attempt to retrieve the deleted saved filter
    Assert:
        1) Verify that the saved filter was successfully inserted
        2) Verify that the saved filter was successfully deleted and cannot be retrieved
    """
    # Assign
    tenant_id = str(uuid.uuid4())
    saved_filter_sample = get_saved_filter_sample(tenant_id)[0]
    finding_table, _ = mocked_tables

    # Act 1 - Insert a saved filter
    event = get_handler_event(
        tenant_id=tenant_id,
        permissions=[Write.FINDINGS],
        body=saved_filter_sample
    )
    response = create_saved_filter(event, {})
    assert response['statusCode'] == 200
    saved_filter_id = json.loads(response['body'])['id']

    # Act 2 - Retrieve the saved filter to ensure it exists
    event = get_handler_event(
        tenant_id=tenant_id,
        permissions=[Read.FINDINGS],
    )
    response = get_saved_filters(event, {})
    assert response['statusCode'] == 200
    retrieved_filters = json.loads(response['body'])
    assert len(retrieved_filters) == 1
    assert retrieved_filters[0]['id'] == saved_filter_id

    # Act 3 - Delete the saved filter using delete_saved_filter
    event = get_handler_event(
        tenant_id=tenant_id,
        permissions=[Write.FINDINGS],
        path_parameters={"saved_filter_id": saved_filter_id}
    )
    response = delete_filter(event, {})
    assert response['statusCode'] == 200

    # Act 4 - Attempt to retrieve the deleted saved filter
    event = get_handler_event(
        tenant_id=tenant_id,
        permissions=[Read.FINDINGS],
    )
    response = get_saved_filters(event, {})

    # Assert
    assert response['statusCode'] == 200
    retrieved_filters = json.loads(response['body'])
    assert len(retrieved_filters) == 0

import json
from http import HTTPStatus

import responses
from jit_utils.models.ignore_rule.entities import IgnoreRuleType
from jit_utils.utils.permissions import Write

from src.handlers.ignore_rules.delete_ignore_rule import handler
from tests.component.utils.get_handler_event import get_handler_event
from tests.component.utils.mock_get_ssm_param import mock_get_ssm_param
from tests.component.utils.mock_mongo_data_api import MongoDataApiMock
from tests.fixtures import build_ignore_rule_dict
from test_utils.aws.mock_eventbridge import mock_eventbridge


@responses.activate
def test_delete_ignore_rule_v2_handler(mocked_tables, mocker, env_variables):
    """
    Test the 'delete_ignore_rule_v2' handler.

    Setup:
    1. Insert one ignore rule into the database.

    Test:
    Call the 'delete_ignore_rule_v2' handler.

    Assert:
    1. The response status code should be 201.
    2. 'ignore-rule-deleted' event should be sent to the EventBridge.
    3. The ignore rule record should be deleted from the database.
    """
    tenant_id = '19881e72-6d3b-49df-b79f-298ad89b8056'
    fingerprint = 'fingerprint'
    ignore_rule_id = "e6390f00-19ac-4a6e-9f4a-c0616cb94528"
    now_string = "2022-01-14T00:00:00"
    path_params = {"id": ignore_rule_id}
    event = get_handler_event(path_parameters=path_params, tenant_id=tenant_id, token='token',
                              permissions=[Write.IGNORE_RULES])

    # Mock the get_api_url_from_ssm function
    mocked_base_path = mock_get_ssm_param(mocker)
    # Initialize the mocked data api class and mock the find request
    mocked_data_api = MongoDataApiMock(mocked_base_path)

    # Setup: 1. insert one ignore rule to ignore rules DB
    ignore_rule = build_ignore_rule_dict(ignore_rule_id=ignore_rule_id, tenant_id=tenant_id, created_at=now_string,
                                         fingerprint=fingerprint)
    mocked_data_api.db.ignore_rules.insert_one(ignore_rule)

    # Setup: 3. Mock create 'ignore-rules' event bus
    with mock_eventbridge(bus_name='ignore-rules') as get_sent_events:
        # Test: 1. Call 'create_ignore_rule' handler
        result = handler(event, {})

        # Assert: 1. response status code == 201
        assert result['statusCode'] == HTTPStatus.NO_CONTENT

        # # Assert: 2. 'ignore-rule-deleted' Event sent to eventbridge.
        sent_messages = get_sent_events()
        assert len(sent_messages) == 1
        assert sent_messages[0]['source'] == 'finding-service'
        assert sent_messages[0]['detail-type'] == 'ignore-rule-deleted'
        del ignore_rule['_id']
        assert sent_messages[0]['detail'] == ignore_rule

        deleted_ignore_rule = mocked_data_api.db.ignore_rules.find_one({'_id': ignore_rule_id})
        # Assert: 3. Ignore rule record was deleted from the DB.
        assert deleted_ignore_rule is None


@responses.activate
def test_delete_ignore_rule_v2_handler__ignore_rule_does_not_exist(mocked_tables, mocker, env_variables):
    """
    Test the 'delete_ignore_rule_v2' handler.

    Setup:
    1. Mock the get_api_url_from_ssm function.
    2. Mock the create 'ignore-rules' event bus.

    Test:
    Call the 'delete_ignore_rule_v2' handler.

    Assert:
    1. The response status code should be 404.
    2. No 'ignore-rule-deleted' event should be sent to the EventBridge.
    """
    tenant_id = '19881e72-6d3b-49df-b79f-298ad89b8056'
    ignore_rule_id = "e6390f00-19ac-4a6e-9f4a-c0616cb94528"
    path_params = {"id": ignore_rule_id}
    event = get_handler_event(path_parameters=path_params, tenant_id=tenant_id, token='token',
                              permissions=[Write.IGNORE_RULES])

    # Mock the get_api_url_from_ssm function
    mocked_base_path = mock_get_ssm_param(mocker)

    # Initialize the mocked data api class and mock the find request
    MongoDataApiMock(mocked_base_path)

    # Setup: 3. Mock create 'ignore-rules' event bus
    with mock_eventbridge(bus_name='ignore-rules') as get_sent_events:
        # Test: 1. Call 'delete' handler
        result = handler(event, {})

        # Assert: 1. response status code == 201
        assert result['statusCode'] == HTTPStatus.NOT_FOUND
        assert json.loads(result['body']) == {"error": "INVALID_INPUT",
                                              "message": "Ignore rule with id:"
                                                         " e6390f00-19ac-4a6e-9f4a-c0616cb94528 not found"}

        # # Assert: 2. 'ignore-rule-deleted' Event sent to eventbridge.
        sent_messages = get_sent_events()
        assert len(sent_messages) == 0


@responses.activate
def test_delete_exclude_type_ignore_rule_via_api_handler(mocked_tables, mocker, env_variables):
    """
    Test the 'delete_ignore_rule_v2' handler to ensure it doesn't allow deletion of EXCLUDE type ignore rules via API.

    Setup:
    1. Insert one EXCLUDE type ignore rule into the database.

    Test:
    Call the 'delete_ignore_rule_v2' handler with an EXCLUDE type ignore rule.

    Assert:
    1. The response status code should be 400.
    2. No 'ignore-rule-deleted' event should be sent to the EventBridge.
    3. The ignore rule record should not be deleted from the database.

    """
    tenant_id = '19881e72-6d3b-49df-b79f-298ad89b8056'
    ignore_rule_id = "e6390f00-19ac-4a6e-9f4a-c0616cb94528"
    now_string = "2022-01-14T00:00:00"
    path_params = {"id": ignore_rule_id}
    event = get_handler_event(path_parameters=path_params, tenant_id=tenant_id,
                              token='token',
                              permissions=[Write.IGNORE_RULES])

    # Mock the get_api_url_from_ssm function
    mocked_base_path = mock_get_ssm_param(mocker)
    # Initialize the mocked data api class
    mocked_data_api = MongoDataApiMock(mocked_base_path)

    # Setup: Insert one EXCLUDE type ignore rule into the database
    ignore_rule = build_ignore_rule_dict(ignore_rule_id=ignore_rule_id, tenant_id=tenant_id,
                                         created_at=now_string, type=IgnoreRuleType.EXCLUDE)
    mocked_data_api.db.ignore_rules.insert_one(ignore_rule)

    response = handler(event, {})

    assert response['statusCode'] == HTTPStatus.BAD_REQUEST
    assert json.loads(response['body']) == {"error": "INVALID_INPUT",
                                            "message": "Deleting an ignore rule of type EXCLUDE is not allowed via API"}

    # Verify that the ignore rule still exists in the database
    existing_ignore_rule = mocked_data_api.db.ignore_rules.find_one({'_id': ignore_rule_id})
    assert existing_ignore_rule is not None

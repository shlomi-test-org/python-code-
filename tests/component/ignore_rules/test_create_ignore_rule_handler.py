import uuid
from http import HTTPStatus

import responses
from freezegun import freeze_time
from jit_utils.models.ignore_rule.entities import IgnoreRule
from jit_utils.utils.permissions import Write
from test_utils.aws.mock_eventbridge import mock_eventbridge

from src.handlers.ignore_rules.create_ignore_rule import handler
from tests.component.ignore_rules.utils import get_create_fingerprint_ignore_rule_payload
from tests.component.utils.get_handler_event import get_handler_event
from tests.component.utils.mock_get_ssm_param import mock_get_ssm_param
from tests.component.utils.mock_mongo_data_api import MongoDataApiMock


@freeze_time("2022-01-14")
@responses.activate
def test_create_ignore_rule_handler__not_ignored_finding(mocked_tables, mocker, env_variables):
    """
    Test the 'create_ignore_rule' handler.

    Setup:
    1. Mock the get_api_url_from_ssm function.
    2. Mock the create 'ignore-rules' event bus.

    Test:
    Call the 'create_ignore_rule' handler.

    Assert:
    1. The response status code should be 201.
    2. An ignore rule record should be created in the database.
    3. A 'ignore-rule-created' event should be sent to the EventBridge.
    """
    tenant_id = '19881e72-6d3b-49df-b79f-298ad89b8056'
    fingerprint = 'fingerprint'
    asset_id = '19881e72-1234-49df-b79f-298ad89b8056'
    control_name = 'control_name'
    email = 'email@email.com'
    user_id = 'user_id'
    ignore_rule = get_create_fingerprint_ignore_rule_payload(asset_id=asset_id,
                                                             fingerprint=fingerprint,
                                                             control_name=control_name)
    event = get_handler_event(body=ignore_rule, tenant_id=tenant_id, token='token',
                              permissions=[Write.IGNORE_RULES], email=email, user_id=user_id)

    # Mock the get_api_url_from_ssm function
    mocked_base_path = mock_get_ssm_param(mocker)

    # Initialize the mocked data api class and mock the find request
    mocked_data_api = MongoDataApiMock(mocked_base_path)

    # Setup: 3. Mock create 'findings' event bus
    with mock_eventbridge(bus_name='ignore-rules') as get_sent_events:
        # Test: 1. Call 'create_ignore_rule' handler
        result = handler(event, {})

        # Assert: 1. response status code == 201
        assert result['statusCode'] == HTTPStatus.CREATED

        # Assert: 2. Ignore rule record has created in DB.
        created_ignore_rule = mocked_data_api.db.ignore_rules.find_one({})
        now_string = "2022-01-14T00:00:00"
        ignore_rule_id = created_ignore_rule['id']
        expected_ignore_rule_in_db = {
            **ignore_rule,
            'id': ignore_rule_id,
            '_id': ignore_rule_id,
            'tenant_id': tenant_id,
            'created_at': now_string,
            'modified_at': now_string,
            'fields': [{'name': 'fingerprint',
                        'operator': 'equal',
                        'value': fingerprint},
                       {'name': 'control_name',
                        'operator': 'equal',
                        'value': control_name},
                       {'name': 'asset_id',
                        'operator': 'equal',
                        'value': asset_id}],
            'user_email': email,
            'user_id': user_id
        }

        assert created_ignore_rule == expected_ignore_rule_in_db

        sent_messages = get_sent_events()
        assert len(sent_messages) == 1
        # Assert: 3. 'ignore-rule-created' Event sent to eventbridge.
        assert sent_messages[0]['source'] == 'finding-service'
        assert sent_messages[0]['detail-type'] == 'ignore-rule-created'
        assert sent_messages[0]['detail'] == IgnoreRule(**expected_ignore_rule_in_db).dict()


@freeze_time("2022-01-14")
@responses.activate
def test_create_ignore_rule_handler__not_ignored_finding_no_user_info(mocked_tables, mocker, env_variables):
    """
    Test the 'create_ignore_rule' handler with no email or user ID. The ignore should still succeed
    but have no user info.

    Setup:
    1. Mock the get_api_url_from_ssm function.
    2. Mock the create 'ignore-rules' event bus.

    Test:
    Call the 'create_ignore_rule' handler.

    Assert:
    1. The response status code should be 201.
    2. An ignore rule record should be created in the database.
    3. A 'ignore-rule-created' event should be sent to the EventBridge.
    4. The ignore rule should have None for user_email and user_id.
    """
    tenant_id = '19881e72-6d3b-49df-b79f-298ad89b8056'
    fingerprint = 'fingerprint'
    asset_id = '19881e72-1234-49df-b79f-298ad89b8056'
    control_name = 'control_name'
    ignore_rule = get_create_fingerprint_ignore_rule_payload(asset_id=asset_id,
                                                             fingerprint=fingerprint,
                                                             control_name=control_name)
    event = get_handler_event(body=ignore_rule, tenant_id=tenant_id, token='token',
                              permissions=[Write.IGNORE_RULES])
    mocked_base_path = mock_get_ssm_param(mocker)
    mocked_data_api = MongoDataApiMock(mocked_base_path)

    with mock_eventbridge(bus_name='ignore-rules') as get_sent_events:
        # Test: 1. Call 'create_ignore_rule' handler
        result = handler(event, {})

        # Assert: 1. response status code == 201
        assert result['statusCode'] == HTTPStatus.CREATED

        # Assert: 2. Ignore rule record has created in DB.
        created_ignore_rule = mocked_data_api.db.ignore_rules.find_one({})
        now_string = "2022-01-14T00:00:00"
        ignore_rule_id = created_ignore_rule['id']
        expected_ignore_rule_in_db = {
            **ignore_rule,
            'id': ignore_rule_id,
            '_id': ignore_rule_id,
            'tenant_id': tenant_id,
            'created_at': now_string,
            'modified_at': now_string,
            'fields': [{'name': 'fingerprint',
                        'operator': 'equal',
                        'value': fingerprint},
                       {'name': 'control_name',
                        'operator': 'equal',
                        'value': control_name},
                       {'name': 'asset_id',
                        'operator': 'equal',
                        'value': asset_id}],
            'user_email': None,
            'user_id': None
        }

        assert created_ignore_rule == expected_ignore_rule_in_db

        sent_messages = get_sent_events()
        assert len(sent_messages) == 1
        # Assert: 3. 'ignore-rule-created' Event sent to eventbridge.
        assert sent_messages[0]['source'] == 'finding-service'
        assert sent_messages[0]['detail-type'] == 'ignore-rule-created'
        assert sent_messages[0]['detail'] == IgnoreRule(**expected_ignore_rule_in_db).dict()


@freeze_time("2022-01-14")
@responses.activate
def test_create_ignore_rule_to_ignored_finding(mocked_tables, mocker, env_variables):
    """
    Test the 'create_ignore_rule' handler, the finding should stay ignored and an error should be returned.

    Setup:
    1. Insert one ignore rule into the database.

    Test:
    Call the 'create_ignore_rule' handler.

    Assert:
    1. The response status code should be 400.
    """
    tenant_id = '19881e72-6d3b-49df-b79f-298ad89b8056'
    fingerprint = 'fingerprint'
    asset_id = '19881e72-1234-49df-b79f-298ad89b8056'

    ignore_rule = get_create_fingerprint_ignore_rule_payload(asset_id=asset_id,
                                                             fingerprint=fingerprint)
    now_string = "2022-01-14T00:00:00"
    ignore_rule_id = str(uuid.uuid4())
    existing_ignore_rule = {
        **ignore_rule,
        'id': ignore_rule_id,
        '_id': ignore_rule_id,
        'tenant_id': tenant_id,
        'created_at': now_string,
    }

    event = get_handler_event(body=ignore_rule, tenant_id=tenant_id, token='token',
                              permissions=[Write.IGNORE_RULES])

    # Mock the get_api_url_from_ssm function.
    mocked_base_path = mock_get_ssm_param(mocker)

    # Initialize the mocked data api class and mock the find request
    mocked_data_api = MongoDataApiMock(mocked_base_path)

    # Setup: 1. Insert ignore rule into the database.
    mocked_data_api.db.ignore_rules.insert_one(existing_ignore_rule)

    # Test: 1. Call 'create_ignore_rule' handler
    result = handler(event, {})

    # Assert: 1. response status code == 409
    assert result['statusCode'] == HTTPStatus.CONFLICT


@responses.activate
def test_create_ignore_rule_no_related_finding(mocked_tables, mocker, env_variables):
    """
     Test the 'create_ignore_rule' handler wihtout related finding, the ignore rule should be created.

     Setup:
     1. Mock data api

     Test:
     Call the 'create_ignore_rule' handler.

     Assert:
     1. The response status code should be 201.
     2. Ignore rule should be created.

     """
    tenant_id = '19881e72-6d3b-49df-b79f-298ad89b8056'
    fingerprint = 'fingerprint'
    asset_id = '19881e72-1234-49df-b79f-298ad89b8056'

    ignore_rule = get_create_fingerprint_ignore_rule_payload(asset_id=asset_id,
                                                             fingerprint=fingerprint)
    with mock_eventbridge(bus_name='ignore-rules') as get_sent_events:
        event = get_handler_event(body=ignore_rule, tenant_id=tenant_id, token='token',
                                  permissions=[Write.IGNORE_RULES])
        # Mock the get_api_url_from_ssm function.
        mocked_base_path = mock_get_ssm_param(mocker)

        # Initialize the mocked data api class and mock the find request
        data_api = MongoDataApiMock(mocked_base_path)

        # Test: 1. Call 'create_ignore_rule' handler
        result = handler(event, {})

        # Assert: 1. response status code == 201
        assert result['statusCode'] == HTTPStatus.CREATED

        assert data_api.db.findings.find_one() is None

        sent_messages = get_sent_events()
        assert len(sent_messages) == 1


@freeze_time("2022-01-14")
@responses.activate
def test_create_ignore_rule_handler__invalid_token_type(mocked_tables, mocker, env_variables):
    """
    Test the 'create_ignore_rule' handler with an invalid token type.

    Setup:
    1. Mock the get_api_url_from_ssm function.
    2. Mock the create 'ignore-rules' event bus.

    Test:
    Call the 'create_ignore_rule' handler with an invalid token type.

    Assert:
    1. The response status code should be 400 (BadRequest).
    2. ValidationError should be thrown due to the invalid token type.
    """
    tenant_id = '19881e72-6d3b-49df-b79f-298ad89b8056'
    fingerprint = 'fingerprint'
    asset_id = '19881e72-1234-49df-b79f-298ad89b8056'
    control_name = 'control_name'
    email = 'email@email.com'
    user_id = 'user_id'
    user_name = 'user'
    ignore_rule = get_create_fingerprint_ignore_rule_payload(asset_id=asset_id,
                                                             fingerprint=fingerprint,
                                                             control_name=control_name,
                                                             user_name=user_name)
    event = get_handler_event(body=ignore_rule, tenant_id=tenant_id, token='token',
                              permissions=[Write.IGNORE_RULES], email=email, user_id=user_id)
    event['requestContext']['authorizer']['frontegg_token_type'] = 'userToken'
    mocked_base_path = mock_get_ssm_param(mocker)
    MongoDataApiMock(mocked_base_path)

    with mock_eventbridge(bus_name='ignore-rules'):
        result = handler(event, {})
        assert result['statusCode'] == HTTPStatus.BAD_REQUEST


@freeze_time("2022-01-14")
@responses.activate
def test_create_ignore_rule_to_ignored_finding_with_different_type(mocked_tables, mocker, env_variables):
    """
    Test the 'create_ignore_rule' handler with different type

    Setup:
    1. Insert one ignore rule into the database.

    Test:
    Call the 'create_ignore_rule' handler.

    Assert:
    1. The response status code should be 200.
    """
    tenant_id = '19881e72-6d3b-49df-b79f-298ad89b8056'
    fingerprint = 'fingerprint'
    asset_id = '19881e72-1234-49df-b79f-298ad89b8056'

    ignore_rule = get_create_fingerprint_ignore_rule_payload(asset_id=asset_id,
                                                             type='exclude',
                                                             fingerprint=fingerprint)
    now_string = "2022-01-14T00:00:00"
    ignore_rule_id = str(uuid.uuid4())
    existing_ignore_rule = {
        **ignore_rule,
        'id': ignore_rule_id,
        '_id': ignore_rule_id,
        'tenant_id': tenant_id,
        'created_at': now_string,
        'type': 'ignore'
    }

    event = get_handler_event(body=ignore_rule, tenant_id=tenant_id, token='token',
                              permissions=[Write.IGNORE_RULES])

    # Mock the get_api_url_from_ssm function.
    mocked_base_path = mock_get_ssm_param(mocker)

    # Initialize the mocked data api class and mock the find request
    mocked_data_api = MongoDataApiMock(mocked_base_path)

    # Setup: 1. Insert ignore rule into the database.
    mocked_data_api.db.ignore_rules.insert_one(existing_ignore_rule)

    with mock_eventbridge(bus_name='ignore-rules') as get_sent_events:
        # Test: 1. Call 'create_ignore_rule' handler
        result = handler(event, {})

        # Assert: 1. response status code == 201
        assert result['statusCode'] == HTTPStatus.CREATED

        sent_messages = get_sent_events()
        assert len(sent_messages) == 1
        # Assert: 3. 'ignore-rule-created' Event sent to eventbridge.
        assert sent_messages[0]['source'] == 'finding-service'
        assert sent_messages[0]['detail-type'] == 'ignore-rule-created'

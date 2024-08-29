import uuid
from datetime import datetime
from http import HTTPStatus

import pytest
import responses
from jit_utils.models.asset.constants import ASSET_ACTIVATED, ASSET_COVERED, ASSET_NOT_COVERED, ASSET_INACTIVE
from jit_utils.models.ignore_rule.entities import FieldToBeIgnoredBy, IgnoreRule, IgnoreRuleType, IgnoreRequestSource
from freezegun import freeze_time

from src.handlers.ignore_rules.handle_asset_change_event import handler
from tests.component.utils.get_handler_event import get_handler_event
from tests.component.utils.mock_mongo_driver import mock_mongo_driver
from tests.fixtures import build_ignore_rule_dict
from test_utils.aws.mock_eventbridge import mock_eventbridge


@freeze_time("2022-01-14")
@responses.activate
@pytest.mark.parametrize('event_type', [ASSET_COVERED, ASSET_ACTIVATED])
def test_asset_change_event_handler_ignore_rule_exists(mocked_tables, mocker, env_variables, event_type):
    """
    Test the 'asset_change_event_handler' handler for asset activated and asset covert events.

    Setup:
    1. Insert one ignore rule of type 'exclude' with asset_id into the database.

    Test:
    Call the 'asset_change_event_handler' handler.
    with the asset id of the ignore rule.

    Assert:
    1. The response status code should be 201.
    2. 'ignore-rule-deleted' event should be sent to the EventBridge.
    3. The ignore rule record should be deleted from the database.
    """
    mongo_client = mock_mongo_driver(mocker)
    tenant_id, ignore_rule_id, asset_id = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    now_string = datetime.utcnow().isoformat()
    # Setup: 1. insert one ignore rule to ignore rules DB
    fields = [
        FieldToBeIgnoredBy(
            name="asset_id",
            value=asset_id
        ).dict()
    ]

    exclude_ignore_rule = build_ignore_rule_dict(ignore_rule_id=ignore_rule_id,
                                                 tenant_id=tenant_id,
                                                 created_at=now_string,
                                                 type='exclude',
                                                 fields=fields)
    fingerprint_ignore_rule = build_ignore_rule_dict(ignore_rule_id=str(uuid.uuid4()),
                                                     tenant_id=tenant_id,
                                                     created_at=now_string,
                                                     asset_id=asset_id,

                                                     )
    mongo_client.ignore_rules.insert_one(exclude_ignore_rule)
    mongo_client.ignore_rules.insert_one(fingerprint_ignore_rule)
    # mocked event
    event = get_handler_event(body={"tenant_id": tenant_id, "asset_id": asset_id},
                              event_type=event_type,
                              tenant_id=tenant_id)
    # Setup: 3. Mock create 'ignore-rules' event bus
    with mock_eventbridge(bus_name='ignore-rules') as get_sent_events:
        # Test: 1. Call 'create_ignore_rule' handler
        result = handler(event, {})

        # Assert: 1. response status code == 201
        assert result['statusCode'] == HTTPStatus.OK

        # # Assert: 2. 'ignore-rule-deleted' Event sent to eventbridge.
        sent_messages = get_sent_events()
        assert len(sent_messages) == 1
        assert sent_messages[0]['source'] == 'finding-service'
        assert sent_messages[0]['detail-type'] == 'ignore-rule-deleted'
        del exclude_ignore_rule['_id']
        assert sent_messages[0]['detail'] == exclude_ignore_rule

        deleted_ignore_rule = mongo_client.ignore_rules.find_one({'_id': ignore_rule_id})
        # Assert: 3. Ignore rule record was deleted from the DB.
        assert deleted_ignore_rule is None


@freeze_time("2022-01-14")
@responses.activate
@pytest.mark.parametrize('event_type', [ASSET_COVERED, ASSET_ACTIVATED])
def test_asset_change_event_handler_no_ignore_rule_found(mocked_tables, mocker, env_variables, event_type):
    """
    Test the 'asset_change_event_handler' for asset activated and asset covered events when no ignore rule is found.

    Setup:
    1. Ensure no ignore rule with the specified asset_id exists in the database.

    Test:
    Call the 'asset_change_event_handler' handler with an asset id that does not have a corresponding ignore rule.

    Assert:
    1. No 'ignore-rule-deleted' event should be sent to the EventBridge.
    2. The handler logs an info message about no ignore rule found.
    """
    mongo_client = mock_mongo_driver(mocker)
    tenant_id, asset_id = str(uuid.uuid4()), str(uuid.uuid4())

    # Ensure no ignore rule exists for the provided asset_id
    assert mongo_client.ignore_rules.find_one({"fields.value": asset_id}) is None

    # Mocked event
    event = get_handler_event(body={"tenant_id": tenant_id, "asset_id": asset_id},
                              event_type=event_type,
                              tenant_id=tenant_id)

    # Setup: Mock create 'ignore-rules' event bus and logger
    with mock_eventbridge(bus_name='ignore-rules') as get_sent_events:
        # Test: Call 'asset_change_event_handler' handler
        handler(event, {})

        # Assert: No 'ignore-rule-deleted' event sent to EventBridge
        sent_messages = get_sent_events()
        assert len(sent_messages) == 0


@freeze_time("2022-01-14")
@responses.activate
@pytest.mark.parametrize('event_type', [ASSET_NOT_COVERED, ASSET_INACTIVE])
def test_asset_change_event_handler_create_ignore_rule_for_asset_inactive(mocked_tables, mocker, env_variables,
                                                                          event_type):
    """
    Test the 'asset_change_event_handler' handler for asset not covered and asset inactive events.
    Test:
    Call the 'asset_change_event_handler' handler.
    with the asset_not_covered or asset_inactive event.

    Assert:
    1. The response status code should be 201.
    2. Ignore rule record should be inserted into the database with the correct fields.
    3. 'ignore-rule-created' event should be sent to the EventBridge.
    """
    mongo_client = mock_mongo_driver(mocker)
    tenant_id, asset_id = str(uuid.uuid4()), str(uuid.uuid4())

    # mocked event
    event = get_handler_event(body={"tenant_id": tenant_id, "asset_id": asset_id},
                              event_type=event_type,
                              tenant_id=tenant_id)
    # Setup: 3. Mock create 'ignore-rules' event bus
    with mock_eventbridge(bus_name='ignore-rules') as get_sent_events:
        # Test: 1. Call 'create_ignore_rule' handler
        result = handler(event, {})

        # Assert: 1. response status code == 200
        assert result['statusCode'] == HTTPStatus.OK

        created_ignore_rule = mongo_client.ignore_rules.find_one()
        ignore_rule: IgnoreRule = IgnoreRule(**created_ignore_rule)

        # Assert: 2. Ignore rule record was created in the DB.
        assert ignore_rule.tenant_id == tenant_id
        assert ignore_rule.fields[0].name == 'asset_id'
        assert ignore_rule.fields[0].value == asset_id
        assert ignore_rule.type == IgnoreRuleType.EXCLUDE
        assert ignore_rule.source == IgnoreRequestSource.EXCLUDE_ASSET

        # Assert: 3. 'ignore-rule-deleted' Event sent to eventbridge.
        sent_messages = get_sent_events()
        assert len(sent_messages) == 1
        assert sent_messages[0]['source'] == 'finding-service'
        assert sent_messages[0]['detail-type'] == 'ignore-rule-created'
        assert sent_messages[0]['detail'] == ignore_rule.dict()


@freeze_time("2022-01-14")
@responses.activate
@pytest.mark.parametrize('event_type', [ASSET_NOT_COVERED, ASSET_INACTIVE])
def test_asset_change_event_handler_create_ignore_rule_for_asset_inactive__ignore_already_exists(mocked_tables, mocker,
                                                                                                 env_variables,
                                                                                                 event_type):
    """
    Test the 'asset_change_event_handler' handler for asset not covered and asset inactive events,
    when the asset is already uncovered, shouldn't raise exception
    Test:
    Call the 'asset_change_event_handler' handler.
    with the asset_not_covered or asset_inactive event.

    Assert:
    'ignore-rule-created' event shouldn't be sent to the EventBridge.
    """
    mongo_client = mock_mongo_driver(mocker)
    tenant_id, ignore_rule_id, asset_id = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    now_string = datetime.utcnow().isoformat()
    # Setup: 1. insert one ignore rule to ignore rules DB
    fields = [
        FieldToBeIgnoredBy(
            name="asset_id",
            value=asset_id
        ).dict()
    ]
    exclude_ignore_rule = build_ignore_rule_dict(ignore_rule_id=ignore_rule_id,
                                                 tenant_id=tenant_id,
                                                 created_at=now_string,
                                                 type='exclude',
                                                 fields=fields)
    mongo_client.ignore_rules.insert_one(exclude_ignore_rule)
    # mocked event
    event = get_handler_event(body={"tenant_id": tenant_id, "asset_id": asset_id},
                              event_type=event_type,
                              tenant_id=tenant_id)
    # Setup: 3. Mock create 'ignore-rules' event bus
    with mock_eventbridge(bus_name='ignore-rules') as get_sent_events:
        # Test: 1. Should not raise an exception
        handler(event, {})

    sent_messages = get_sent_events()
    assert len(sent_messages) == 0

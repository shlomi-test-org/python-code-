import json
import uuid
from typing import List, Dict

import responses
from aws_lambda_typing.events import SQSEvent
from freezegun import freeze_time
from jit_utils.models.ignore_rule.entities import IgnoreRuleType, IgnoreRequestSource, OperatorTypes
from jit_utils.models.plan.entities import PlanItemActiveStatusChangedEvent
from moto import mock_sqs
from test_utils.aws.mock_sqs import create_mock_queue_and_get_sent_events

from src.handlers.ignore_rules.handle_changed_plan_item import handler, queue_plan_item_changed_event
from src.lib.constants import PLAN_ITEMS, PLAN_ITEM_CHANGED_FIFO_QUEUE
from src.lib.ignore_rules.utils import IgnoreRuleNotificationType
from tests.component.utils.mock_mongo_driver import mock_mongo_driver
from test_utils.aws.mock_eventbridge import mock_eventbridge


def create_event(tenant_id: str, plan_slug: str, slugs_statuses: Dict[bool, List[str]]) -> SQSEvent:
    event = {"Records": []}
    for is_active, plan_item_slugs in slugs_statuses.items():
        for plan_item_slug in plan_item_slugs:
            event["Records"].append(
                {
                    "body": json.dumps(
                        {
                            "timestamp": "2022-01-14 14:04:47.741886",
                            "tenant_id": tenant_id,
                            "plan_slug": plan_slug,
                            "plan_item_slug": plan_item_slug,
                            "is_active": is_active,
                        }
                    ),
                }
            )
    return event


def create_multitenant_event(tenant_ids: List[str], plan_slug: str, plan_item_slug: str, is_active: bool) -> SQSEvent:
    event = {"Records": []}
    for tenant_id in tenant_ids:
        event["Records"].append(
            {
                "body": json.dumps(
                    {
                        "timestamp": "2022-01-14 14:04:47.741886",
                        "tenant_id": tenant_id,
                        "plan_slug": plan_slug,
                        "plan_item_slug": plan_item_slug,
                        "is_active": is_active,
                    }
                ),
            }
        )
    return event


def assert_ignore_rule_record_in_db(mongo_client, tenant_id: str, plan_item_slugs: List[str]):
    created_ignore_rule = mongo_client.ignore_rules.find_one({"tenant_id": tenant_id})

    assert created_ignore_rule["tenant_id"] == tenant_id
    assert created_ignore_rule["type"] == IgnoreRuleType.EXCLUDE
    assert created_ignore_rule["source"] == IgnoreRequestSource.API
    assert created_ignore_rule["fields"][0]["name"] == PLAN_ITEMS
    assert created_ignore_rule["fields"][0]["value"] == plan_item_slugs
    assert created_ignore_rule["fields"][0]["operator"] == OperatorTypes.CONTAINED


def assert_ignore_rule_event_sent(
        sent_messages: List[dict], ignore_rule_event: IgnoreRuleNotificationType, plan_item_slugs: List[str]
):
    assert len(sent_messages) == 1
    assert sent_messages[0]['source'] == 'finding-service'
    assert sent_messages[0]['detail-type'] == ignore_rule_event
    assert sent_messages[0]['detail']['fields'][0]['value'] == plan_item_slugs


@freeze_time("2022-01-14")
@responses.activate
def test_plan_item_change_event_handler_create_ignore_rule_inactive(mocker):
    """
    Test the handler for a plan item change event with inactive status.

    Setup:
    1. No ignore rule exists for the plan item in the database.

    Test:
    Call the handler with a plan item change event where the plan item is inactive.
    Call the handler again with another plan item is inactive

    Assert:
    1. An ignore rule record should be created in the database with the correct fields.
    2. An 'ignore-rule-created' event should be sent to the EventBridge.
    3. The same ignore rule record should be updated to include also the second plan item.
    4. An 'ignore-rule-updated' event should be sent to the EventBridge.
    """
    mongo_client = mock_mongo_driver(mocker)
    plan_item_slug_1 = "plan_item_slug_1"
    plan_item_slug_2 = "plan_item_slug_2"
    tenant_id, plan_slug, = str(uuid.uuid4()), str(uuid.uuid4())

    # Setup: Mock create 'ignore-rules' event bus and logger
    with mock_eventbridge(bus_name='ignore-rules') as get_sent_events:
        handler(create_event(tenant_id, plan_slug, {False: [plan_item_slug_1]}), {})

        assert_ignore_rule_record_in_db(mongo_client, tenant_id, [plan_item_slug_1])
        assert_ignore_rule_event_sent(
            get_sent_events(), IgnoreRuleNotificationType.IgnoreRuleUpdated, [plan_item_slug_1]
        )

        handler(create_event(tenant_id, plan_slug, {False: [plan_item_slug_2]}), {})

        assert_ignore_rule_record_in_db(mongo_client, tenant_id, [plan_item_slug_1, plan_item_slug_2])
        assert_ignore_rule_event_sent(
            get_sent_events(),
            IgnoreRuleNotificationType.IgnoreRuleUpdated,
            [plan_item_slug_1, plan_item_slug_2],
        )


@freeze_time("2022-01-14")
@responses.activate
def test_plan_item_change_event_handler_ignore_rule_exists(mocker):
    """
    Test the handler for a plan item change event with inactive status when an ignore rule already exists.

    Setup:
    1. An ignore rule exists for the plan item in the database.

    Test:
    Call the handler with a plan item change event where the plan item is inactive.

    Assert:
    1. No new ignore rule record should be created in the database.
    2. No 'ignore-rule-created' event should be sent to the EventBridge.
    """
    mongo_client = mock_mongo_driver(mocker)
    tenant_id, plan_slug, plan_item_slug = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())

    # Setup: Insert an existing ignore rule for the plan item
    existing_ignore_rule = {
        "id": str(uuid.uuid4()),
        "created_at": "2022-01-14 14:04:47.741886",
        "tenant_id": tenant_id,
        "type": IgnoreRuleType.EXCLUDE,
        "source": IgnoreRequestSource.API,
        "comment": "test comment",
        "fields": [{"name": PLAN_ITEMS, "value": [plan_item_slug], "operator": OperatorTypes.CONTAINED}]
    }
    mongo_client.ignore_rules.insert_one(existing_ignore_rule)

    event = create_event(tenant_id, plan_slug, {False: [plan_item_slug]})

    with mock_eventbridge(bus_name='ignore-rules') as get_sent_events:
        handler(event, {})
        ignore_rules = list(mongo_client.ignore_rules.find({"tenant_id": tenant_id, "fields.value": plan_item_slug}))
        # Assert that no new ignore rule record is created
        assert len(ignore_rules) == 1

        # Assert no 'ignore-rule-created' event sent to EventBridge.
        sent_messages = get_sent_events()
        assert len(sent_messages) == 0


@freeze_time("2022-01-14")
@responses.activate
def test_plan_item_change_event_handler_delete_ignore_rule_active(mocker):
    """
    Test the handler for a plan item change event with active status when an ignore rule exists.

    Setup:
    1. An ignore rule exists for the plan item in the database.

    Test:
    Call the handler with a plan item change event where the plan item is active.

    Assert:
    1. The ignore rule record should be updated tp remove the plan item slug from its value.
    2. An 'ignore-rule-updated' event should be sent to the EventBridge.
    """
    mongo_client = mock_mongo_driver(mocker)
    tenant_id, plan_slug, plan_item_slug = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    ignore_rule_id = str(uuid.uuid4())
    # Setup: Insert an existing ignore rule for the plan item
    existing_ignore_rule = {
        "_id": ignore_rule_id,
        "id": ignore_rule_id,
        "created_at": "2022-01-14 14:04:47.741886",
        "tenant_id": tenant_id,
        "type": IgnoreRuleType.EXCLUDE,
        "source": IgnoreRequestSource.API,
        "comment": "test comment",
        "fields": [{"name": PLAN_ITEMS, "value": [plan_item_slug], "operator": OperatorTypes.CONTAINED}]
    }
    mongo_client.ignore_rules.insert_one(existing_ignore_rule)

    event = create_event(tenant_id, plan_slug, {True: [plan_item_slug]})

    with mock_eventbridge(bus_name='ignore-rules') as get_sent_events:
        handler(event, {})

        # Assert the ignore rule record is deleted from the DB.
        ignore_rule = mongo_client.ignore_rules.find_one({"tenant_id": tenant_id, "fields.name": PLAN_ITEMS})
        assert ignore_rule["fields"][0]["value"] == []

        # Assert 'ignore-rule-updated' event sent to EventBridge.
        sent_messages = get_sent_events()
        assert len(sent_messages) == 1
        assert sent_messages[0]['source'] == 'finding-service'
        assert sent_messages[0]['detail-type'] == IgnoreRuleNotificationType.IgnoreRuleUpdated
        assert sent_messages[0]['detail']['fields'][0]['value'] == []


@freeze_time("2022-01-14")
@responses.activate
def test_plan_item_change_event_handler_no_ignore_rule_on_active(mocker):
    """
    Test the handler for a plan item change event with active status when no ignore rule exists.

    Setup:
    1. Ensure no ignore rule exists for the plan item in the database.

    Test:
    Call the handler with a plan item change event where the plan item is active.

    Assert:
    1. No ignore rule record should be deleted from the database.
    2. No 'ignore-rule-deleted' event should be sent to the EventBridge.
    3. No error should occur.
    """
    mongo_client = mock_mongo_driver(mocker)
    tenant_id, plan_slug, plan_item_slug = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())

    # Ensure no ignore rule exists for the provided plan_item_slug
    assert mongo_client.ignore_rules.find_one({"fields.value": plan_item_slug}) is None

    event = create_event(tenant_id, plan_slug, {True: [plan_item_slug]})

    with mock_eventbridge(bus_name='ignore-rules') as get_sent_events:
        handler(event, {})

        # Assert no ignore rule is deleted from the DB.
        non_existent_ignore_rule = mongo_client.ignore_rules.find_one(
            {"tenant_id": tenant_id, "fields.value": plan_item_slug})
        assert non_existent_ignore_rule is None

        # Assert no 'ignore-rule-deleted' event sent to EventBridge.
        sent_messages = get_sent_events()
        assert len(sent_messages) == 0


@freeze_time("2022-01-14")
@responses.activate
def test_plan_item_change_event_handler_rule_not_exist_multiple_events_in_single_invoke(mocker):
    """
    Test the handler for a plan item change event that contain 2 deactivation + 2 activations.

    Setup:
    1. No ignore rule exists for the plan item in the database.

    Test:
    Call the handler with SQS event that contains several plan item change events.

    Assert:
    1. the ignore rule for plan items in the DB is updated with the deactivated plan items
    2. event sent for creation
    """
    mongo_client = mock_mongo_driver(mocker)
    tenant_id, plan_slug = str(uuid.uuid4()), str(uuid.uuid4())
    plan_item_1 = "plan_item_1"
    plan_item_2 = "plan_item_2"
    plan_item_3 = "plan_item_3"
    plan_item_4 = "plan_item_4"

    event = create_event(
        tenant_id,
        plan_slug,
        {False: [plan_item_1, plan_item_2, plan_item_3], True: [plan_item_3, plan_item_4]},
    )

    with mock_eventbridge(bus_name='ignore-rules') as get_sent_events:
        handler(event, {})

        assert_ignore_rule_record_in_db(mongo_client, tenant_id, [plan_item_1, plan_item_2])
        sent_messages = get_sent_events()
        assert len(sent_messages) == 1
        assert_ignore_rule_event_sent(
            [sent_messages[0]],
            IgnoreRuleNotificationType.IgnoreRuleUpdated,
            [plan_item_1, plan_item_2]
        )


@freeze_time("2022-01-14")
@responses.activate
def test_plan_item_change_event_handler_rule_exist_multiple_events_in_single_invoke(mocker):
    """
    Test the handler for a plan item change event that contain 2 deactivation + 2 activations.
    There is current ignore rule for one of the activated plan items

    Setup:
    1. No ignore rule exists for the plan item in the database.

    Test:
    Call the handler with SQS event that contains several plan item change events.

    Assert:
    1. the ignore rule for plan items in the DB is updated with the deactivated plan items
    2. event sent for update
    """
    mongo_client = mock_mongo_driver(mocker)
    tenant_id, plan_slug = str(uuid.uuid4()), str(uuid.uuid4())
    plan_item_1 = "plan_item_1"
    plan_item_2 = "plan_item_2"
    plan_item_3 = "plan_item_3"
    plan_item_4 = "plan_item_4"

    ignore_rule_id = str(uuid.uuid4())
    # Setup: Insert an existing ignore rule for the plan item
    existing_ignore_rule = {
        "_id": ignore_rule_id,
        "id": ignore_rule_id,
        "created_at": "2022-01-14 14:04:47.741886",
        "tenant_id": tenant_id,
        "type": IgnoreRuleType.EXCLUDE,
        "source": IgnoreRequestSource.API,
        "comment": "test comment",
        "fields": [{"name": PLAN_ITEMS, "value": [plan_item_4], "operator": OperatorTypes.CONTAINED}]
    }
    mongo_client.ignore_rules.insert_one(existing_ignore_rule)

    event = create_event(
        tenant_id,
        plan_slug,
        {False: [plan_item_1, plan_item_2, plan_item_3], True: [plan_item_3, plan_item_4]},
    )

    with mock_eventbridge(bus_name='ignore-rules') as get_sent_events:
        handler(event, {})

        assert_ignore_rule_record_in_db(mongo_client, tenant_id, [plan_item_1, plan_item_2])
        assert_ignore_rule_event_sent(
            get_sent_events(),
            IgnoreRuleNotificationType.IgnoreRuleUpdated, [plan_item_1, plan_item_2]
        )


@freeze_time("2022-01-14")
@responses.activate
def test_plan_item_change_event_handler_event_from_multiple_tenants(mocker):
    """
    Test the handler for a plan item change event that contain events from 2 tenants.

    Setup:
    1. No ignore rule exists for the plan item in the database.

    Test:
    Call the handler with SQS event that contains several plan item change events - 1 for each tenant.

    Assert:
    1. the ignore rule for plan items in the DB is created for each tenant with the deactivated plan items
    2. event sent for update
    """
    mongo_client = mock_mongo_driver(mocker)
    tenant_id_1, tenant_id_2, plan_slug, plan_item_slug = (
        str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    )

    event = create_multitenant_event([tenant_id_1, tenant_id_2], plan_slug, plan_item_slug, False)

    with mock_eventbridge(bus_name='ignore-rules') as get_sent_events:
        handler(event, {})

        assert_ignore_rule_record_in_db(mongo_client, tenant_id_1, [plan_item_slug])
        assert_ignore_rule_record_in_db(mongo_client, tenant_id_2, [plan_item_slug])

        sent_messages = get_sent_events()
        assert_ignore_rule_event_sent(
            [sent_messages[0]],
            IgnoreRuleNotificationType.IgnoreRuleUpdated, [plan_item_slug]
        )
        assert_ignore_rule_event_sent(
            [sent_messages[1]],
            IgnoreRuleNotificationType.IgnoreRuleUpdated, [plan_item_slug]
        )


@mock_sqs
@responses.activate
def test_queue_plan_item_changed_event_handler():
    """
    Test the handler for a plan item change event from event bridge.

    Test:
    Call the handle with an eventbridge event of PlanItemUpdated

    Assert:
    SQS message got sent with MessageGroupId of the tenant_id
    """
    tenant_id, plan_slug, plan_item_slug = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    get_messages = create_mock_queue_and_get_sent_events(
        PLAN_ITEM_CHANGED_FIFO_QUEUE, {"FifoQueue": "true"}
    )
    plan_item_change_event = PlanItemActiveStatusChangedEvent(
        timestamp="2023-01-14 14:04:47.741886",
        tenant_id=tenant_id,
        plan_slug=plan_slug,
        plan_item_slug=plan_item_slug,
        is_active=False,
    )

    queue_plan_item_changed_event({"id": str(uuid.uuid4()), "detail": plan_item_change_event.dict()}, {})

    assert get_messages() == [
        PlanItemActiveStatusChangedEvent(
            timestamp="2023-01-14 14:04:47.741886",
            tenant_id=tenant_id,
            plan_slug=plan_slug,
            plan_item_slug=plan_item_slug,
            is_active=False,
        ).dict()
    ]

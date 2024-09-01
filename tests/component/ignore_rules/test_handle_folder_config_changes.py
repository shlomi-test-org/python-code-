import json
from freezegun import freeze_time
import responses
from tests.component.utils.get_mocked_asset import DEFAULT_ASSET_ID
from tests.component.utils.mock_mongo_driver import mock_mongo_driver
from src.lib.constants import IGNORE_RULES_BUS_NAME
from tests.component.utils.mock_get_ssm_param import mock_get_ssm_param
from tests.component.utils.mock_clients.mock_asset import mock_get_all_assets
from tests.component.utils.mock_clients.mock_authentication import mock_get_internal_token_api
from test_utils.aws.mock_eventbridge import mock_eventbridge
from tests.fixtures import build_ignore_rule_dict
from src.handlers.ignore_rules.handle_folder_config_change import handler


@freeze_time("2022-01-14")
@responses.activate
def test_handle_folder_config_change_with_unrelated_rule_in_db(mocker, mocked_tables, create_firehose_mock):
    """
    Test the handler for folder config change with 4 excludes when there is an unrelated ignore rule in the DB.

    Setup:
    1. An unrelated ignore rule exists in the database.

    Test:
    Call the handler with a folder config change message containing 4 excludes.

    Assert:
    1. Four new ignore rule records related to the folder config should be created in the database.
    """
    mongo_client = mock_mongo_driver(mocker)
    ignore_rules_collection = mongo_client.ignore_rules
    tenant_id = '9df0c0ae-b497-40ba-bc78-d486aaa083d0'
    unrelated_ignore_rule = build_ignore_rule_dict(
        ignore_rule_id="unrelated-rule-id",
        tenant_id=tenant_id,
        created_at="2022-01-14T00:00:00Z",
        type="exclude",
        fields=[{"name": "asset_id", "value": "some-value", "operator": "equal"}]
    )
    ignore_rules_collection.insert_one(unrelated_ignore_rule)

    message_dict = {
        "tenant_id": tenant_id,
        "repo_name": "test1",
        "repo_owner": "JonathanJitRockets",
        "is_centralized_repo": False,
        "folders_config": {
            "folders": [
                {
                    "path": "/ignored-folder",
                    "exclude": ["/exclude1*", "/exclude2*", "/exclude3*", "/exclude4*"],
                    "name": "ignored-folder"
                }
            ]
        }
    }

    item = json.dumps(message_dict)
    mock_get_internal_token_api()
    mock_get_all_assets(tenant_id=tenant_id)
    event = {
        "Records": [
            {"body": item}
        ]
    }

    mock_get_ssm_param(mocker)
    with mock_eventbridge(IGNORE_RULES_BUS_NAME) as get_sent_events:
        handler(event, {})

    created_ignore_rules = list(ignore_rules_collection.find({"tenant_id": message_dict['tenant_id']}))

    assert len(created_ignore_rules) == 5, "Expected 5 ignore rules in total, including the unrelated one"

    for rule in created_ignore_rules:
        if rule["id"] == unrelated_ignore_rule["id"]:
            continue
        assert rule["type"].value == "exclude", "New rule type should be exclude"
        assert rule["source"].value == "exclude_folder", "New rule source should be EXCLUDE_FOLDER"

    events = get_sent_events()
    assert len(events) == 4, "Expected 4 ignore rule created events to be sent"
    created_ignore_rule_ids = [event["detail"]["id"] for event in events]
    for event in events:
        assert event["detail"]["id"] in created_ignore_rule_ids, "Event detail should contain the ignore rule id"
        assert event["detail-type"] == "ignore-rule-created", "Event detail type should be ignore-rule-created"


@freeze_time("2022-01-14")
def test_handle_folder_config_change_with_existing_rules_removal(mocker, mocked_tables, create_firehose_mock):
    """
    Test the handler for folder config change when the folders config in the message does
    not match all existing ignore rules in the database.

    Setup:
        1. Four existing ignore rules are present in the database, each corresponding to a
           different 'exclude' pattern.
        2. A folder config change message is prepared, containing only 3 of the 4 exclude patterns
           previously established in the ignore rules, effectively leaving one of the existing
           ignore rules unmatched by the new folder config.

    Test:
        Invoke the handler with the folder config change message that includes configurations
        for only 3 out of the 4 existing ignore rules.

    Assert:
        1. The ignore rule that does not match any pattern specified in the new folders config
           (the unmatched ignore rule) should be deleted from the database.
        2. A single 'ignore-rule-deleted' event should be sent, specifically for the deleted
           ignore rule, indicating the removal of the unmatched rule from the database.
    """
    mongo_client = mock_mongo_driver(mocker)
    ignore_rules_collection = mongo_client.ignore_rules
    tenant_id = '9df0c0ae-b497-40ba-bc78-d486aaa083d0'

    # Existing ignore rules, with 4 entries
    existing_ignore_rules = [
        build_ignore_rule_dict(
            ignore_rule_id=f"rule-{i}",
            tenant_id=tenant_id,
            source="exclude_folder",
            created_at="2022-01-14T00:00:00Z",
            type="exclude",
            fields=[{"name": "filename", "value": f"ignored-folder/exclude{i}*", "operator": "regex"},
                    {"name": "asset_id", "value": DEFAULT_ASSET_ID, "operator": "equal"}]
        ) for i in range(1, 5)  # Generates 4 rules
    ]

    # Insert existing ignore rules
    for rule in existing_ignore_rules:
        ignore_rules_collection.insert_one(rule)

    # Folders config message with only 3 of the existing rules
    message_dict = {
        "tenant_id": tenant_id,
        "repo_name": "test1",
        "repo_owner": "JonathanJitRockets",
        "is_centralized_repo": False,
        "folders_config": {
            "folders": [
                {
                    "path": "/ignored-folder",
                    "exclude": ["/exclude1*", "/exclude2*", "/exclude3*"],
                    "name": "ignored-folder"
                }
            ]
        }
    }

    item = json.dumps(message_dict)
    event = {
        "Records": [
            {"body": item}
        ]
    }
    mock_get_internal_token_api()
    mock_get_all_assets(tenant_id=tenant_id)
    mock_get_ssm_param(mocker)
    with mock_eventbridge(IGNORE_RULES_BUS_NAME) as get_sent_events:
        handler(event, {})

    # Assert that the database now contains only the 3 ignore rules that match the config
    updated_ignore_rules = list(ignore_rules_collection.find({"tenant_id": message_dict['tenant_id']}))
    assert len(updated_ignore_rules) == 3, "Expected 3 ignore rules in total after processing"

    # Assert that the 'ignore-rule-deleted' event is sent for the unmatched rule
    events = get_sent_events()
    assert len(events) == 1, "Expected 1 'ignore-rule-deleted' event to be sent"
    assert events[0]["detail-type"] == "ignore-rule-deleted", "Event detail type should be 'ignore-rule-deleted'"
    assert events[0]["detail"]["id"] == "rule-4", "The deleted rule ID should be 'rule-4'"


@freeze_time("2022-01-14")
def test_handle_folder_config_change_with_rules_created_and_deleted(mocker, mocked_tables, create_firehose_mock):
    """
    Test the handler for folder config change where the new folders config results in both
    the creation of new ignore rules for newly specified exclude patterns and the deletion
    of existing ignore rules that are not included in the new config.

    Setup:
        1. Three existing ignore rules are present in the database, corresponding to different
           'exclude' patterns.
        2. A folder config change message is prepared, containing two new exclude patterns not
           previously covered by existing rules and omitting one pattern that was covered by
           an existing rule.

    Test:
        Invoke the handler with the folder config change message that includes two new exclude
        patterns and excludes one of the previously included patterns.

    Assert:
        1. Two new ignore rule records should be created for the new exclude patterns.
        2. The existing ignore rule that does not match any pattern specified in the new folders
           config should be deleted from the database.
        3. An 'ignore-rule-deleted' event should be sent for the deleted rule, and
           'ignore-rule-created' events should be sent for each of the newly created rules.
    """
    mongo_client = mock_mongo_driver(mocker)
    ignore_rules_collection = mongo_client.ignore_rules
    tenant_id = '9df0c0ae-b497-40ba-bc78-d486aaa083d0'

    # Existing ignore rules, with 3 entries
    existing_ignore_rules = [
        build_ignore_rule_dict(
            ignore_rule_id=f"rule-{i}",
            tenant_id=tenant_id,
            source="exclude_folder",
            created_at="2022-01-14T00:00:00Z",
            type="exclude",
            fields=[{"name": "filename", "value": f"ignored-folder/exclude{i}*", "operator": "regex"},
                    {"name": "asset_id", "value": DEFAULT_ASSET_ID, "operator": "equal"}]
        ) for i in range(1, 4)  # Generates 3 rules
    ]

    # Insert existing ignore rules
    for rule in existing_ignore_rules:
        ignore_rules_collection.insert_one(rule)

    # Folders config message with 2 new excludes and omitting one existing
    message_dict = {
        "tenant_id": tenant_id,
        "repo_name": "test1",
        "repo_owner": "JonathanJitRockets",
        "is_centralized_repo": False,
        "folders_config": {
            "folders": [
                {
                    "path": "/ignored-folder",
                    # exclude1* is omitted, newExclude1* and newExclude2* are new
                    "exclude": ["/exclude2*", "/exclude3*", "/newExclude1*", "/newExclude2*"],
                    "name": "ignored-folder"
                }
            ]
        }
    }

    item = json.dumps(message_dict)
    event = {
        "Records": [
            {"body": item}
        ]
    }

    mock_get_internal_token_api()
    mock_get_all_assets(tenant_id=tenant_id)
    mock_get_ssm_param(mocker)
    with mock_eventbridge(IGNORE_RULES_BUS_NAME) as get_sent_events:
        handler(event, {})

    # Assert the correct number of ignore rules present after processing
    updated_ignore_rules = list(ignore_rules_collection.find({"tenant_id": message_dict['tenant_id']}))
    assert len(updated_ignore_rules) == 4, "Expected 4 ignore rules in total after" \
                                           "processing, (Orig - 3, 1 removed and 2 added)"

    # Check the events for correct types and IDs
    events = get_sent_events()
    assert len(events) == 3, "Expected 3 events to be sent, 2 creations and 1 deletion"
    event_types = [event["detail-type"] for event in events]
    assert event_types.count("ignore-rule-created") == 2, "Expected 2 'ignore-rule-created' events"
    assert event_types.count("ignore-rule-deleted") == 1, "Expected 1 'ignore-rule-deleted' event"


@freeze_time("2022-01-14")
def test_handle_folder_config_change_with_no_changes(mocker, mocked_tables, create_firehose_mock):
    """
    Test the handler for folder config change when the folders config in the message exactly matches
    all existing ignore rules in the database, containing 100 exclude patterns.

    Setup:
        1. One hundred existing ignore rules are present in the database, each corresponding to a
           unique 'exclude' pattern already specified in the folders config.
        2. A folder config change message is prepared, containing all 100 exclude patterns that
           match the existing ignore rules, introducing no new excludes and omitting none.

    Test:
        Invoke the handler with the folder config change message that perfectly matches the
        existing ignore rules setup.

    Assert:
        1. No changes should be made to the ignore rules in the database (no creations or deletions).
        2. No events should be sent, indicating no operational changes required.
    """
    mongo_client = mock_mongo_driver(mocker)
    ignore_rules_collection = mongo_client.ignore_rules
    tenant_id = '9df0c0ae-b497-40ba-bc78-d486aaa083d0'

    # Generate and insert 100 existing ignore rules
    existing_ignore_rules = [
        build_ignore_rule_dict(
            ignore_rule_id=f"rule-{i}",
            tenant_id=tenant_id,
            source="exclude_folder",
            created_at="2022-01-14T00:00:00Z",
            type="exclude",
            fields=[{"name": "filename", "value": f"exclude{i}*", "operator": "regex"},
                    {"name": "asset_id", "value": DEFAULT_ASSET_ID, "operator": "equal"}]
        ) for i in range(1, 101)  # Generates 100 rules
    ]

    for rule in existing_ignore_rules:
        ignore_rules_collection.insert_one(rule)

    # Folders config message exactly matching existing rules
    message_dict = {
        "tenant_id": tenant_id,
        "repo_name": "test1",
        "repo_owner": "JonathanJitRockets",
        "is_centralized_repo": False,
        "folders_config": {
            "folders": [
                {
                    "path": "/ignored-folder",
                    "exclude": [f"exclude{i}*" for i in range(1, 101)],
                    "name": "ignored-folder"
                }
            ]
        }
    }

    item = json.dumps(message_dict)
    event = {
        "Records": [
            {"body": item}
        ]
    }

    mock_get_internal_token_api()
    mock_get_all_assets(tenant_id=tenant_id)
    mock_get_ssm_param(mocker)
    with mock_eventbridge(IGNORE_RULES_BUS_NAME) as get_sent_events:
        handler(event, {})

    updated_ignore_rules = list(ignore_rules_collection.find({"tenant_id": message_dict['tenant_id']}))
    assert len(updated_ignore_rules) == 100, "Expected no changes to the ignore rules in the database"

    events = get_sent_events()
    assert len(events) == 0, "Expected no events to be sent due to no changes"


@freeze_time("2022-01-14")
def test_handle_folder_config_change_with_mixed_slash_prefixes(mocker, mocked_tables, create_firehose_mock):
    """
    Test the handler for folder config change where the folders config includes paths and exclude
    patterns with mixed usage of leading slashes, ensuring consistent handling regardless of the slash presence.

    Setup:
        1. An existing ignore rule is present in the database that matches an exclude pattern specified
           in the folder config without a leading slash.
        2. A folder config change message is prepared, containing a new exclude pattern with a leading
           slash and omitting the exclude pattern that matched the existing rule, effectively requiring
           the deletion of the existing rule and creation of a new rule.

    Test:
        Invoke the handler with the folder config change message that includes a new exclude pattern
        with a leading slash and excludes the pattern matched by the existing rule.

    Assert:
        1. The existing ignore rule that does not match the new pattern specified in the folders config
           should be deleted from the database.
        2. A new ignore rule should be created for the new exclude pattern specified with a leading slash.
        3. An 'ignore-rule-deleted' event should be sent for the deleted rule, and an 'ignore-rule-created'
           event should be sent for the newly created rule.
    """
    mongo_client = mock_mongo_driver(mocker)
    ignore_rules_collection = mongo_client.ignore_rules
    tenant_id = '9df0c0ae-b497-40ba-bc78-d486aaa083d0'

    # Existing ignore rule that matches an exclude pattern without a leading slash
    existing_ignore_rule = build_ignore_rule_dict(
        ignore_rule_id="existing-rule",
        tenant_id=tenant_id,
        source="exclude_folder",
        created_at="2022-01-14T00:00:00Z",
        type="exclude",
        fields=[{"name": "filename", "value": "ignored-folder/excludeOld*", "operator": "regex"},
                {"name": "asset_id", "value": DEFAULT_ASSET_ID, "operator": "equal"}]
    )

    # Insert the existing ignore rule
    ignore_rules_collection.insert_one(existing_ignore_rule)

    # Folders config message with a new exclude pattern with a leading slash, omitting the existing pattern
    message_dict = {
        "tenant_id": tenant_id,
        "repo_name": "test1",
        "repo_owner": "Owner1",
        "is_centralized_repo": False,
        "folders_config": {
            "folders": [
                {
                    "path": "ignored-folder",  # Without leading slash
                    "exclude": ["/excludeNew*"],  # With leading slash
                    "name": "ignored-folder"
                }
            ]
        }
    }

    item = json.dumps(message_dict)
    event = {
        "Records": [
            {"body": item}
        ]
    }

    mock_get_internal_token_api()
    mock_get_all_assets(tenant_id=tenant_id)
    mock_get_ssm_param(mocker)
    with mock_eventbridge(IGNORE_RULES_BUS_NAME) as get_sent_events:
        handler(event, {})

    # Assert the correct update to ignore rules in the database
    updated_ignore_rules = list(ignore_rules_collection.find({"tenant_id": message_dict['tenant_id']}))
    assert len(updated_ignore_rules) == 1, "Expected 1 ignore rule in total after processing"

    new_rule = updated_ignore_rules[0]
    assert new_rule["fields"][1]["value"] == "ignored-folder/excludeNew*"

    # Check the events for correct types and IDs
    events = get_sent_events()
    assert len(events) == 2, "Expected 2 events to be sent, 1 creation and 1 deletion"
    event_types = [event["detail-type"] for event in events]
    assert event_types.count("ignore-rule-created") == 1, "Expected 1 'ignore-rule-created' event"
    assert event_types.count("ignore-rule-deleted") == 1, "Expected 1 'ignore-rule-deleted' event"

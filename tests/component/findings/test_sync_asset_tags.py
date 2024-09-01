from src.handlers.findings.sync_asset_tags import handler
from tests.component.utils.mock_mongo_driver import mock_mongo_driver
from tests.fixtures import build_finding_dict
from jit_utils.models.tags.entities import Tag
from src.lib.data.mongo.constants import SPECS_KEY, SPECS_VALUE
from test_utils.aws.mock_eventbridge import mock_eventbridge


def test_sync_asset_tags__add_tags_on_findings(mocker, mocked_tables):
    """
    This test verifies that the handler updates and adds to the corresponding findings the updated tags
    Only a single event should be sent on the finding that was updated
    Setup:
        1) Mock mongo driver
        2) Insert findings to the mocked collection

    Test:
        1) Call the handler once

    Assert:
        1) The findings were updated accordingly
        2) The findings-updated event was sent with a single finding
    """
    # Assign
    # Mock mongo driver
    findings_collection = mock_mongo_driver(mocker).findings

    tenant_id = "19881e72-6d3b-49df-b79f-298ad89b8056"
    asset_id = "b5874d6e-5adb-4df8-be8c-8b5efb9450fe"
    removed_tags = []
    added_tags = [
        Tag(name="team", value="birds"),
    ]
    expected_specs = [{SPECS_KEY: added_tags[0].name, SPECS_VALUE: added_tags[0].value}]
    finding = build_finding_dict(tenant_id=tenant_id, asset_id=asset_id, tags=[], with_specs=True)
    finding_with_tags = build_finding_dict(tenant_id=tenant_id, asset_id=asset_id, tags=added_tags, with_specs=True)
    # Insert some mock data
    findings_collection.insert_many([finding, finding_with_tags])
    findings_before_update = findings_collection.find()
    modified_at_before_update = findings_before_update[0]["modified_at"]
    assert findings_before_update[0]["tags"] == []

    # Act
    event = {
        "detail": {
            "tenant_id": tenant_id,
            "asset_id": asset_id,
            "removed_tags": removed_tags,
            "added_tags": added_tags
        }
    }

    with mock_eventbridge(bus_name='findings') as get_sent_events:
        handler(event, {})
    sent_events = get_sent_events()

    findings_after_update = findings_collection.find()
    modified_at_after_update = findings_after_update[0]["modified_at"]

    # Assert
    assert findings_after_update[0]["tags"] == added_tags
    assert findings_after_update[0]["specs"] == finding["specs"] + expected_specs
    assert modified_at_after_update > modified_at_before_update
    assert len(sent_events) == 1
    assert sent_events[0]['detail-type'] == 'findings-updated'
    assert len(sent_events[0]['detail']['findings']) == 1


def test_sync_asset_tags__remove_tags_from_findings(mocker, mocked_tables):
    """
    This test verifies that the handler updates and adds to the corresponding findings the updated tags
    Setup:
        1) Mock mongo driver
        2) Insert findings to the mocked collection with 2 tags
        3) Insert finding with not matching tag to the one that should be removed

    Test:
        1) Call the handler once

    Assert:
        1) Only the finding with tags was updated - a single finding was sent in the event
        2) The finding was updated accordingly - was left with a single tag
    """
    # Assign
    # Mock mongo driver
    findings_collection = mock_mongo_driver(mocker).findings

    tenant_id = "19881e72-6d3b-49df-b79f-298ad89b8056"
    asset_id = "b5874d6e-5adb-4df8-be8c-8b5efb9450fe"
    tags = [Tag(name="team", value="birds")]
    removed_tags = [tag.dict() for tag in tags]
    # Insert some mock data
    finding = build_finding_dict(tenant_id=tenant_id, asset_id=asset_id,
                                 tags=tags + [Tag(name="team", value="rocket")],
                                 with_specs=True)
    finding_with_no_tags = build_finding_dict(tenant_id=tenant_id, asset_id=asset_id,
                                              tags=[Tag(name="team", value="jets")], with_specs=True)
    findings_collection.insert_many([finding, finding_with_no_tags])
    findings_before_update = findings_collection.find()
    modified_at_before_update = findings_before_update[0]["modified_at"]

    # Act
    event = {
        "detail": {
            "tenant_id": tenant_id,
            "asset_id": asset_id,
            "removed_tags": removed_tags,
            "added_tags": []
        }
    }
    with mock_eventbridge(bus_name='findings') as get_sent_events:
        handler(event, {})
    sent_events = get_sent_events()
    findings_after_update = findings_collection.find()
    modified_at_after_update = findings_after_update[0]["modified_at"]
    finding["specs"].remove({SPECS_KEY: tags[0].name, SPECS_VALUE: tags[0].value})
    # Assert
    assert findings_after_update[0]["tags"] == [Tag(name="team", value="rocket")]
    assert findings_after_update[0]["specs"] == finding["specs"]
    assert modified_at_after_update > modified_at_before_update
    assert len(sent_events) == 1
    assert sent_events[0]['detail-type'] == 'findings-updated'
    assert len(sent_events[0]['detail']['findings']) == 1


def test_sync_asset_tags__remove_and_add_tags_from_findings(mocker, mocked_tables):
    """
    This test verifies that the handler updates and adds to the corresponding findings the updated tags
    Setup:
        1) Mock mongo driver
        2) Insert findings to the mocked collection

    Test:
        1) Call the handler once

    Assert:
        1) The findings were updated accordingly
    """
    # Assign
    # Mock mongo driver
    findings_collection = mock_mongo_driver(mocker).findings

    tenant_id = "19881e72-6d3b-49df-b79f-298ad89b8056"
    asset_id = "b5874d6e-5adb-4df8-be8c-8b5efb9450fe"
    tag_birds = Tag(name="team", value="birds")
    tag_rocket = Tag(name="team", value="rocket")
    rocket_spec = {SPECS_KEY: tag_rocket.name, SPECS_VALUE: tag_rocket.value}
    tag_bandit = Tag(name="team", value="bandit")
    bandit_spec = {SPECS_KEY: tag_bandit.name, SPECS_VALUE: tag_bandit.value}
    finding1 = build_finding_dict(tenant_id=tenant_id, asset_id=asset_id, tags=[tag_rocket], with_specs=True)
    finding2 = build_finding_dict(tenant_id=tenant_id, asset_id=asset_id, tags=[tag_bandit], with_specs=True)
    finding3 = build_finding_dict(tenant_id=tenant_id, asset_id=asset_id, tags=[], with_specs=True)
    finding4 = build_finding_dict(tenant_id=tenant_id, asset_id="some-asset-id", tags=[tag_birds], with_specs=True)

    removed_tags = [tag_birds]
    added_tags = [tag_rocket, tag_bandit]
    # Insert some mock data
    findings_collection.insert_many([finding1, finding2, finding3, finding4])
    findings_before_update = list(findings_collection.find())
    assert len(findings_before_update) == 4

    # Act
    event = {
        "detail": {
            "tenant_id": tenant_id,
            "asset_id": asset_id,
            "removed_tags": [tag.dict() for tag in removed_tags],
            "added_tags": [tag.dict() for tag in added_tags]
        }
    }
    with mock_eventbridge(bus_name='findings') as get_sent_events:
        handler(event, {})
    sent_events = get_sent_events()

    findings_after_update = list(findings_collection.find())
    finding1_after = [finding for finding in findings_after_update if finding["id"] == finding1["id"]]
    finding2_after = [finding for finding in findings_after_update if finding["id"] == finding2["id"]]
    finding3_after = [finding for finding in findings_after_update if finding["id"] == finding3["id"]]
    finding4_after = [finding for finding in findings_after_update if finding["id"] == finding4["id"]]
    expected_specs_1 = finding1["specs"] + [bandit_spec]
    expected_specs_2 = finding2["specs"] + [rocket_spec]
    expected_specs_3 = finding3["specs"] + [rocket_spec, bandit_spec]

    # Assert
    assert finding1_after[0]["tags"] == [tag_rocket.dict(), tag_bandit.dict()]
    assert finding2_after[0]["tags"] == [tag_bandit.dict(), tag_rocket.dict()]
    assert finding3_after[0]["tags"] == [tag_rocket.dict(), tag_bandit.dict()]
    assert finding4_after[0]["tags"] == [tag_birds.dict()]
    assert finding1_after[0]["specs"] == expected_specs_1
    assert finding2_after[0]["specs"] == expected_specs_2
    assert finding3_after[0]["specs"] == expected_specs_3
    assert finding4_after[0]["specs"] == finding4["specs"]
    assert len(sent_events) == 1
    assert sent_events[0]['detail-type'] == 'findings-updated'

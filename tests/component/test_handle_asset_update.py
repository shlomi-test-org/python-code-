from src.handlers.handle_asset_update import handler
from tests.component.utils.get_mocked_asset import get_mocked_asset
from tests.component.utils.mock_mongo_driver import mock_mongo_driver
from tests.fixtures import build_finding_dict


def test_handle_asset_update(mocker):
    """
    The test should create mongo mock, build 5 findings with the same asset_id and put them in the mock.
    Then it should call handle_assets_update with the same asset_id and check that the findings were updated.
    The test should also check that the findings were updated only once.
    """
    # Mock mongo driver
    mongo_client = mock_mongo_driver(mocker)
    findings_collection = mongo_client.findings

    tenant_id = "88881e72-6d3b-49df-b79f-298ad89b8056"
    asset_id = "c5994d6e-5adb-4df8-be8c-8b5efb9450fe"
    findings = [
        build_finding_dict(tenant_id=tenant_id, asset_id=asset_id, with_specs=True)
        for _ in range(5)
    ]
    # Insert some mock data
    findings_collection.insert_many(findings)
    findings_before_update = findings_collection.find()

    priority_score_to_update = 20

    for finding in findings_before_update:
        assert finding["asset_priority_score"] == 0
        assert finding["tags"] == []

    asset = get_mocked_asset(
        asset_id=asset_id, tenant_id=tenant_id, priority_score=priority_score_to_update,
        tags=[{"name": "team", "value": "team1"}]
    )
    # Act
    event = {"detail": {"tenant_id": tenant_id, "assets": [asset]}}

    handler(event, {})

    findings_after_update = findings_collection.find()

    # Assert
    for finding in findings_after_update:
        assert finding["asset_priority_score"] == priority_score_to_update
        assert finding["tags"] == []

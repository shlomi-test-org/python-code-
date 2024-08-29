import json

import pytest
from src.handlers.findings.update_findings import update_multiple_findings
from tests.component.utils.mock_mongo_driver import mock_mongo_driver
from tests.fixtures import build_finding_dict


def test_update_multiple_findings(mocker):
    """
    The test should create mongo mock, build 5 findings and put them in the mock.
    Then it should call update multiple findingsand check that the findings were updated.
    The test should also check that the findings were updated only once.
    """
    # Mock mongo driver
    mongo_client = mock_mongo_driver(mocker)
    findings_collection = mongo_client.findings

    tenant_id = "88881e72-6d3b-49df-b79f-298ad89b8056"
    findings = [
        build_finding_dict(tenant_id=tenant_id, with_specs=True) for _ in range(5)
    ]
    # Insert some mock data
    findings_collection.insert_many(findings)
    findings_before_update = findings_collection.find()
    for finding in findings_before_update:
        assert finding["asset_priority_score"] == 0

    risk_score = 20

    event = {
        "Records": [
            {
                "body": json.dumps(
                    {
                        "tenant_id": tenant_id,
                        "findings_patch": [
                            {
                                "id": finding["_id"],
                                "asset_priority_score": risk_score,
                            }
                            for finding in findings
                        ],
                    }
                ),
            }
        ]
    }
    update_multiple_findings(event, {})

    findings_after_update = findings_collection.find()

    for finding in findings_after_update:
        assert finding["asset_priority_score"] == risk_score


def test_update_multiple_findings__invalid_body():
    event = {
        "Records": [{"tenant_id": "tenant_id", "body": json.dumps({"findings": []})}],
    }
    with pytest.raises(ValueError) as e:
        update_multiple_findings(event, {})
    assert str(e.value) == "Tenant ID not found in message"


def test_update_multiple_findings__not_finding_model():
    event = {
        "Records": [
            {
                "body": json.dumps(
                    {
                        "tenant_id": "tenant_id",
                        "findings_patch": [
                            {
                                "id": "id",
                                "not_a_finding_field": "value",
                            }
                            for _ in range(10)
                        ],
                    }
                )
            }
        ]
    }
    with pytest.raises(ValueError) as e:
        update_multiple_findings(event, {})
    assert str(e.value) == "Invalid finding: {'id': 'id', 'not_a_finding_field': 'value'},\
 should have the keys of the Finding model."

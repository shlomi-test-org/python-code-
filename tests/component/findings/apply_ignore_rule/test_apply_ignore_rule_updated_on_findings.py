from uuid import uuid4

from jit_utils.models.findings.entities import Resolution
from moto import mock_sqs

from src.handlers.findings.apply_ignore_rule_on_findings import apply_ignore_rule_updated_on_findings
from src.lib.constants import IGNORE_RULE_UPSERTED_SIDE_EFFECTS_QUEUE_NAME
from src.lib.models.events import IgnoreRuleUpsertedSideEffectsOnFindings
from tests.component.ignore_rules.utils import build_plan_items_ignore_rule_dict
from tests.component.utils.assert_queue_content import assert_queue_content
from tests.component.utils.mock_mongo_driver import mock_mongo_driver
from tests.component.utils.mock_sqs_queue import mock_sqs_queue
from tests.fixtures import build_finding_dict


def _assert_finding_in_db(mocked_findings_collection, ignore_rule: dict, finding: dict):
    finding_in_db = mocked_findings_collection.find_one({"id": finding["id"]})
    finding_in_db.pop("modified_at")
    expected_finding = {
        **finding, "resolution": Resolution.INACTIVE.value, "ignored": True, "ignore_rules_ids": [ignore_rule["id"]]
    }
    expected_finding["specs"][0]["v"] = True
    expected_finding["specs"][2]["v"] = Resolution.INACTIVE.value
    expected_finding.pop("modified_at")
    assert finding_in_db == expected_finding


@mock_sqs
def test_apply_ignore_rule_on_findings_with_plan_items(mocked_tables, mocker, env_variables):
    """
    Test the "apply_ignore_rule_updated_on_findings" handler.
    Ignore rule of type "exclude" with plan_items applied on open findings.
    Only the finding with a plan_items that are sub-set of the value should be ignored.

    Setup:
    1. Insert one ignore rule of type "exclude" by plan_items into the database.
    2. Insert findings: 3 of them should be ignored.

    Test:
    Call the "apply_ignore_rule_updated_on_findings" handler.

    Assert:
    1. The finding with the relevant plan_items should be updated to ignored=True.
    2. The findings should be with resolution=INACTIVE.
    2. The finding without a matching filename should remain unaffected.
    """
    tenant_id = str(uuid4())

    ignore_rule = build_plan_items_ignore_rule_dict(tenant_id, ["p1", "p2"])

    mocked_event = {
        "detail": {
            "tenant_id": tenant_id,
            **ignore_rule
        },
    }

    mongo_client = mock_mongo_driver(mocker)
    mocked_findings_collection = mongo_client.findings

    to_ignore_1 = build_finding_dict(tenant_id=tenant_id, with_specs=True, plan_items=["p1"])
    to_ignore_2 = build_finding_dict(tenant_id=tenant_id, with_specs=True, plan_items=["p2"])
    to_ignore_3 = build_finding_dict(tenant_id=tenant_id, with_specs=True, plan_items=["p1", "p2"])
    to_not_ignore_1 = build_finding_dict(tenant_id=tenant_id, with_specs=True, plan_items=["p1", "p3"])
    to_not_ignore_2 = build_finding_dict(tenant_id=tenant_id, with_specs=True, plan_items=["p1", "p2", "p3"])

    mocked_findings_collection.insert_many([to_ignore_1, to_ignore_2, to_ignore_3, to_not_ignore_1, to_not_ignore_2])

    # Mock the creation of the 'IgnoreRuleCreatedSideEffectsQueue' sqs queue
    mock_sqs_queue(queue_name=IGNORE_RULE_UPSERTED_SIDE_EFFECTS_QUEUE_NAME)

    apply_ignore_rule_updated_on_findings(mocked_event, {})

    _assert_finding_in_db(mocked_findings_collection, ignore_rule, to_ignore_1)
    _assert_finding_in_db(mocked_findings_collection, ignore_rule, to_ignore_2)
    _assert_finding_in_db(mocked_findings_collection, ignore_rule, to_ignore_3)
    assert mocked_findings_collection.find_one({"id": to_not_ignore_1["id"]}) == to_not_ignore_1
    assert mocked_findings_collection.find_one({"id": to_not_ignore_2["id"]}) == to_not_ignore_2

    # Assert: The IgnoreRuleCreatedSideEffectsOnFindings message should be sent to the queue
    expected_message = IgnoreRuleUpsertedSideEffectsOnFindings(
        tenant_id=tenant_id,
        ignore_rule=ignore_rule,
        total_effected_findings_count=3
    )
    assert_queue_content(
        queue_name=IGNORE_RULE_UPSERTED_SIDE_EFFECTS_QUEUE_NAME,
        expected_messages=[expected_message.dict()]
    )

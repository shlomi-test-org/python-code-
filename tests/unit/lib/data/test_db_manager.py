import uuid
from typing import List

import pytest

from jit_utils.models.findings.entities import Finding
from src.lib.data.saved_filters import FindingsDynamoManager
from src.lib.models.finding_model import Filters, SavedFilter
from tests.fixtures import build_finding_dict, get_saved_filter_sample

tenant_id = str(uuid.uuid4())

FINDING_SAMPLE = build_finding_dict()
SAVED_FILTERS_SAMPLE = get_saved_filter_sample(tenant_id)


def test_db_manager_get_key():
    assert FindingsDynamoManager.get_key(MyKey='MyValue') == 'MYKEY#MyValue'
    assert FindingsDynamoManager.get_key(Key1='Value1', Key2='Value2') == 'KEY1#Value1#KEY2#Value2'
    assert FindingsDynamoManager.get_key(Key1='Value1', Key2=None) == 'KEY1#Value1'
    assert FindingsDynamoManager.get_key(Key1='Value1', Key2=None, Key3='Value3') == 'KEY1#Value1'


def test_create_saved_filter(saved_filters_manager):
    saved_filter = SavedFilter(**SAVED_FILTERS_SAMPLE[0])
    saved_filters_manager.put_saved_filter(saved_filter)
    assert saved_filters_manager.get_saved_filters_for_tenant_id(tenant_id) == [saved_filter]


def test_get_saved_filters(saved_filters_manager):
    saved_filter = SavedFilter(**SAVED_FILTERS_SAMPLE[0])
    saved_filter_2 = saved_filter.copy()
    saved_filter_2.tenant_id = str(uuid.uuid4())
    saved_filters_manager.put_saved_filter(saved_filter)
    saved_filters_manager.put_saved_filter(saved_filter_2)
    result = saved_filters_manager.get_saved_filters_for_tenant_id(tenant_id)
    assert len(result) == 1
    assert result[0] == saved_filter


def test_update_saved_filters(saved_filters_manager):
    saved_filter = SavedFilter(**SAVED_FILTERS_SAMPLE[0]).copy()
    saved_filters_manager.put_saved_filter(saved_filter)
    result = saved_filters_manager.get_saved_filters_for_tenant_id(tenant_id)
    assert len(result) == 1
    assert result[0] == saved_filter
    saved_filter.should_notify = True
    saved_filter.name = "new filter name"
    saved_filters_manager.put_saved_filter(saved_filter)
    result = saved_filters_manager.get_saved_filters_for_tenant_id(tenant_id)
    assert len(result) == 1
    assert result[0] == saved_filter


def _put_sample_findings(findings: List[Finding], saved_filters_manager: FindingsDynamoManager):
    for finding in findings:
        pk = FindingsDynamoManager.get_key(tenant=finding.tenant_id)
        gsi3sk = FindingsDynamoManager.get_key(created_at=finding.created_at) if (
            not finding.code_attributes.pr_number) else None

        item = {
            **finding.dict(exclude_unset=True),
            'PK': pk,
            'SK': FindingsDynamoManager.get_key(asset=finding.asset_id, finding=finding.id),
            'GSI2PK': pk,
            'GSI2SK': FindingsDynamoManager.get_key(
                asset_id=finding.asset_id,
                snapshot_id=str(finding.scan_scope),
                control_id=finding.control_name
            ),
            'created_at': str(finding.created_at),
        }
        if gsi3sk:
            item['GSI3PK'] = pk
            item['GSI3SK'] = gsi3sk

        saved_filters_manager.table.put_item(Item=item)


def test_delete_tenant_data(saved_filters_manager):
    finding = Finding(**FINDING_SAMPLE)
    _put_sample_findings([finding], saved_filters_manager)
    assert saved_filters_manager.table.scan()["Count"] == 1
    saved_filters_manager.delete_tenant_data(finding.tenant_id)
    assert saved_filters_manager.table.scan()["Count"] == 0


def _build_full_scan_findings(
        tenant_id, count: int = 1, issue_severity: str = None, asset_type: str = None,
        resolution: str = None) -> List[Finding]:
    findings = []
    for i in range(count):
        finding = Finding(**FINDING_SAMPLE)
        # remove code_attribute.pr_number from finding to simulate full scan finding
        finding.code_attributes.pr_number = None
        finding.id = str(uuid.uuid4())  # TODO use the new Finding creation function in PR #1802
        finding.tenant_id = tenant_id

        finding.issue_severity = issue_severity if issue_severity else "HIGH"
        finding.asset_type = asset_type if asset_type else "repo"
        finding.resolution = resolution if resolution else "OPEN"

        findings.append(finding)

    return findings


@pytest.mark.parametrize('filters_dict, result', [
    ({}, True),  # no filters
    ({"issue_severity": ["HIGH"]}, True),
    ({"issue_severity": ["HIGH", "LOW"]}, True),
    ({"issue_severity": ["LOW"]}, False),
    ({"issue_severity": ["LOW", "MEDIUM"]}, False),
    ({"issue_severity": ["HIGH"], "asset_type": ["repo"]}, True),
    ({"issue_severity": ["LOW"], "asset_type": ["repo"]}, False),
    ({"issue_severity": ["HIGH"], "ui_resolution": ["OPEN"]}, False),
    ({"issue_severity": ["HIGH"], "ui_resolution": ["IGNORED"]}, True),
    ({"issue_severity": ["HIGH"], "ui_resolution": ["FIXED"]}, False),
    ({"issue_severity": ["HIGH"], "test_name": ["substring", "lalalala"]}, True),
    ({"issue_severity": ["HIGH"], "test_name": ["lalalala"]}, False),
])
def test_is_filter_remain_finding(saved_filters_manager, filters_dict, result):
    tenant_id = str(uuid.uuid4())
    filters = Filters(**filters_dict)
    finding = _build_full_scan_findings(
        tenant_id=tenant_id, count=1, issue_severity="HIGH", asset_type="repo", resolution="OPEN")[0]
    finding.test_name = "this is a string with a substring"

    finding.ignored = True

    assert result == saved_filters_manager.does_finding_remain_after_filters(
        finding=finding, filters=filters
    )

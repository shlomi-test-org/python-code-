from typing import List

from jit_utils.models.findings.entities import Finding


def get_expected_high_severity_findings_slack_notification(finding: Finding, channel: str):
    return {
        "notification_payload": {
            "view_url": f"https://platform.jit.io/findings?"
                        f"resolution=OPEN&issue_severity=HIGH%2CCRITICAL&time_ago=ONE_WEEK&"
                        f"control_name={finding.control_name}&"
                        f"asset_name={finding.asset_name}",
            "tool_name": finding.control_name,
            "resource_name": finding.asset_name,
            "findings": [
                {"test_name": finding.test_name,
                 "vulnerability_type": finding.vulnerability_type,
                 "severity": finding.issue_severity,
                 "control_name": finding.control_name,
                 "location_text": finding.location_text,
                 "location": finding.location,
                 "finding_url": f"https://platform.jit.io/findings?id={finding.id}"}]},
        "targets": {"slack": {"channel_id": channel}},
        "tenant_id": finding.tenant_id
    }


def get_expected_saved_view_findings_slack_notification(findings: List[Finding], channel: str,
                                                        view_name: str):
    return {
        'notification_payload': {
            'view_url': 'https://platform.jit.io/findings?'
                        'created_at_start=0001-01-01T00%3A00%3A00&'
                        'created_at_end=2022-01-14T00%3A00%3A00',
            'tool_name': findings[0].control_name,
            'resource_name': findings[0].asset_name,
            'findings': [
                {'test_name': finding.test_name,
                 'vulnerability_type': finding.vulnerability_type,
                 'severity': finding.issue_severity,
                 'control_name': finding.control_name,
                 'location_text': finding.location_text,
                 'location': finding.location,
                 'finding_url': f"https://platform.jit.io/findings?id={finding.id}"}
                for finding in findings],
            'view_name': view_name},
        "targets": {"slack": {"channel_id": channel}},
        "tenant_id": findings[0].tenant_id
    }

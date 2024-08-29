import uuid
import pytest
from jit_utils.models.findings.entities import Resolution

from src.lib.models.finding_model import Finding
from jit_utils.models.finding import AppFindingsPayload, AppsPayload, VulnerabilityType, PlanLayer, \
    AppRawControlFinding, Severity
from pydantic import ValidationError


def test_init_finding_model_with_zap_app_payload():
    """
    Test that when we use the entire AppRawControlFinding model as a dict when we initialize a new Finding Model,
    there will be a Validation Error with Zap attribute on the AppRawControlFinding model "tags: Optional[dict]"
    to the new "tags: List[Tag] = []" attribute on the findings model.
    We'll get a Validation error, that None is not an allowed value.
    And when we use only the needed attributes from the AppRawControlFinding model, this prevents the error
    """
    findings = []
    # Initialize AppsPayload model with tags=None
    apps_payload = AppsPayload(control_name='Zap',
                               status='PASS',
                               event_type='control_results',
                               created_at='2023-07-14T15:43:42.364868',
                               vulnerability_type=VulnerabilityType.RUNTIME_VULNERABILITY,
                               plan_layer=PlanLayer.RUNTIME,
                               workflow_slug='workflow-web-app-scanner',
                               findings=[AppRawControlFinding(
                                   test_name='Vulnerable JS Library',
                                   fingerprint='9dd5bc01f241470b1501cd10425be568ad50647508ab64cb770e1dafbe889ef7',
                                   test_id='10003',
                                   issue_text='<p>The identified library bootstrap, version 3.3.4 is vulnerable.</p>',
                                   issue_confidence='MEDIUM',
                                   issue_severity=Severity.MEDIUM,
                                   references=[{
                                       'name': 'https://github.com/twbs/bootstrap/issues/28236',
                                       'url': 'https://github.com/twbs/bootstrap/issues/28236'}],
                                   location='https://patterns.3m.com/cutx/js/jqueryUI/jquery-ui.min.js',
                                   location_text='https://patterns.3m.com/cutx/js/jqueryUI/jquery-ui.min.js',
                                   snapshot_attributes={
                                       'authentication': 'True',
                                       'scan_mode': 'web',
                                       'location': 'https://patterns.3m.com/cutx/js/jqueryUI/jquery-ui.min.js'},
                                   fix_suggestion=None,
                                   target_url='https://patterns.3m.com/js/jqueryUI/jquery-ui.min.js',
                                   request_header='GET https://patterns.3m.com/cutx/js/jqueryUI/'
                                                  'jquery-ui.min.js?1687199764 HTTP/1.1\r\n'
                                                  'Host: patterns.3m.com\r\n'
                                                  'user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:105.0)'
                                                  ' Gecko/20100101 Firefox/105.0\r\n'
                                                  'pragma: no-cache\r\ncache-control: no-cache\r\n'
                                                  'Referer: https://patterns.3m.com/cutx/\r\n\r\n',
                                   response_header='HTTP/1.1 200 OK\r\nDate: Fri, 14 Jul 2023 15:41:52 GMT\r\n'
                                                   'Content-Type: text/javascript\r\nContent-Length: 240427\r\n'
                                                   'Connection: keep-alive\r\nServer: Apache\r\n'
                                                   'Last-Modified: Mon, 19 Jun 2023 18:36:04 GMT\r\n'
                                                   'Accept-Ranges: bytes\r\n\r\n',
                                   param='', path='/cutx', method='GET',
                                   solution='<p>Please upgrade to the latest version of bootstrap.</p>',
                                   cweid='829', tags=None)])
    # Initialize FindingsPayload
    findings_payload = AppFindingsPayload(tenant_id='87ce72c4-2385-42c6-b111-b3629980585e',
                                          vendor='domain',
                                          asset_name='3m',
                                          asset_domain=None,
                                          jit_event_id='1d84fda3-f752-4c8a-8ad7-2df4b39c82e8',
                                          execution_id='22b3a0f4-8a29-4d4f-95d8-86d6127e5bf4',
                                          jit_event_name='item_activated',
                                          workflow_suite_id='1d84fda3-f752-4c8a-8ad7-2df4b39c82e8',
                                          workflow_id='22b3a0f4-8a29-4d4f-95d8-86d6127e5bf4',
                                          job_name='web-security-detection',
                                          user_vendor_id=None,
                                          user_vendor_name=None,
                                          asset_type='web',
                                          payload=apps_payload)
    # Tries to init a new Finding model from the findings_payload and fails for validation error
    with pytest.raises(ValidationError):
        for finding_item in findings_payload.payload.findings:
            finding = Finding(
                **finding_item.dict(exclude_unset=True),
                id=str(uuid.uuid4()),
                created_at="",
                tenant_id='87ce72c4-2385-42c6-b111-b3629980585e',
                asset_id=str(uuid.uuid4()),
                asset_name="asset_name",
                asset_domain="asset_domain",
                asset_type="asset_type",
                workflow_suite_id=findings_payload.workflow_suite_id,
                first_workflow_suite_id=findings_payload.workflow_suite_id,
                workflow_id=findings_payload.workflow_id,
                first_workflow_id=findings_payload.workflow_id,
                jit_event_id="jit_event_id",
                jit_event_name="jit_event_name",
                first_jit_event_name="jit_event_name",
                execution_id="execution_id",
                job_name=findings_payload.job_name,
                control_name="control_name",
                event_type=findings_payload.payload.event_type,
                status=findings_payload.payload.status,
                vendor=findings_payload.vendor,
                last_detected_at="run_time",
                resolution=Resolution.OPEN,
                backlog=True,
                plan_layer=findings_payload.payload.plan_layer,
                vulnerability_type=findings_payload.payload.vulnerability_type,
                plan_item="plan_item_slug"
            )
            findings.append(finding)
    # Asset, No new findings instances
    assert len(findings) == 0

    # Tries to init a new Finding model with the needed attributes from the finding payload and succeed
    for finding_item in findings_payload.payload.findings:
        finding = Finding(
            test_name=finding_item.test_name,
            fingerprint=finding_item.fingerprint,
            test_id=finding_item.test_id,
            issue_text=finding_item.issue_text,
            issue_confidence=finding_item.issue_confidence,
            issue_severity=finding_item.issue_severity,
            references=finding_item.references,
            location=finding_item.location,
            location_text=finding_item.location_text,
            snapshot_attributes=finding_item.snapshot_attributes,
            fix_suggestion=finding_item.fix_suggestion,
            id=str(uuid.uuid4()),
            created_at="",
            tenant_id='87ce72c4-2385-42c6-b111-b3629980585e',
            asset_id=str(uuid.uuid4()),
            asset_name="asset_name",
            asset_domain="asset_domain",
            asset_type="asset_type",
            workflow_suite_id=findings_payload.workflow_suite_id,
            first_workflow_suite_id=findings_payload.workflow_suite_id,
            workflow_id=findings_payload.workflow_id,
            first_workflow_id=findings_payload.workflow_id,
            jit_event_id="jit_event_id",
            jit_event_name="jit_event_name",
            first_jit_event_name="jit_event_name",
            execution_id="execution_id",
            job_name=findings_payload.job_name,
            control_name="control_name",
            event_type=findings_payload.payload.event_type,
            status=findings_payload.payload.status,
            vendor=findings_payload.vendor,
            last_detected_at="run_time",
            resolution=Resolution.OPEN,
            backlog=True,
            plan_layer=findings_payload.payload.plan_layer,
            vulnerability_type=findings_payload.payload.vulnerability_type,
            plan_item="plan_item_slug"
        )
        findings.append(finding)

    # Asset, new finding instance
    assert len(findings) == 1

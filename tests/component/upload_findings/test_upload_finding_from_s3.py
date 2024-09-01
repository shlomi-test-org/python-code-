import json
from decimal import Decimal
from pathlib import Path

import freezegun
import responses

from src.handlers.findings.upload_findings import handle_finding_from_s3
from test_utils.aws.mock_eventbridge import mock_eventbridge

from tests.component.utils.mock_clients.mock_authentication import mock_get_internal_token_api
from tests.component.utils.mock_clients.mock_execution import mock_get_execution_api
from tests.component.utils.mock_clients.mock_plan import mock_get_job_scopes

S3_BUCKET_NAME = 'bucket_name'

ASSET_ID_FROM_FINDING = 'bba671c3-bb7e-49a7-8c3d-87d97ec0b7fc'
TENANT_ID_FROM_FINDING = '1b2bc442-b8a6-4ab8-a037-d536c2859094'
JIT_EVENT_ID_FROM_FINDING = '8ddc8ce1-9636-4457-9f4b-c0055278e6fa'
EXECUTION_ID_FROM_FINDING = '5c5d3bf8-59da-4a7d-a20c-eda720676f29'

S3_FILE_NAME = 'findings_file.json'
EVENT = {
    "Records": [
        {"s3": {"object": {"key": S3_FILE_NAME}, "bucket": {"name": S3_BUCKET_NAME}}}
    ]
}


def assert_all_expected_scan_scopes_uploaded(event, raw_data):
    findings_for_scan_scope = event['detail']['findings_for_scan_scope']

    expected_scope_locations = sorted(raw_data['snapshot_attributes']['location'])
    assert len(findings_for_scan_scope) == len(expected_scope_locations)
    expected_scan_scopes = [{
        'authentication': False,
        'location': expected_scope_locations[i],
        'scan_mode': 'Web',
    } for i in range(len(expected_scope_locations))]
    for scope in findings_for_scan_scope:
        assert scope['scan_scope'] in expected_scan_scopes
        for finding in scope['findings']:
            assert finding['scan_scope'] == scope['scan_scope']


def assert_expected_event_detail_type(event):
    assert event['detail-type'] == 'create-findings-scan-scopes-batch'


def assert_upload_status_item_created(upload_status_table, jit_event_name, backlog, snapshots_count):
    status_items = upload_status_table.scan()['Items']
    assert len(status_items) == 1
    assert status_items[0] == {
        'PK': f'TENANT#{TENANT_ID_FROM_FINDING}',
        'SK': f'JIT_EVENT_ID#{JIT_EVENT_ID_FROM_FINDING}#EXECUTION_ID#{EXECUTION_ID_FROM_FINDING}',
        'jit_event_id': JIT_EVENT_ID_FROM_FINDING,
        'jit_event_name': jit_event_name,
        'execution_id': EXECUTION_ID_FROM_FINDING,
        'created_at': '2023-01-20T11:17:48.356174',
        'tenant_id': TENANT_ID_FROM_FINDING, 'snapshots_count': Decimal(snapshots_count),
        'error_count': Decimal('0'), 'completed_at': None, 'failed_snapshots': [],
        'is_backlog': backlog
    }


def setup_test_data(data_file_path, mocker, s3_client):
    s3_client.create_bucket(Bucket=S3_BUCKET_NAME)
    mock_get_internal_token_api()
    mock_get_execution_api(JIT_EVENT_ID_FROM_FINDING, EXECUTION_ID_FROM_FINDING, TENANT_ID_FROM_FINDING)
    with open(Path(__file__).parent.parent.parent.parent / data_file_path, 'rb') as f:
        s3_client.upload_fileobj(f, S3_BUCKET_NAME, S3_FILE_NAME)

    with open(Path(__file__).parent.parent.parent.parent / data_file_path, 'r') as f:
        raw_data = json.load(f)
        return raw_data


@freezegun.freeze_time("2020-01-01")
@responses.activate
def test_upload_finding_from_s3__happy_flow__backlog_control(dynamodb, mocked_tables, mocker, s3_client):
    """
    This test checks that the handle_finding_from_s3() lambda sends a create_finding_batch event
    with the correct finding data when a finding file is uploaded to S3.

    Setup:
        1) Upload an example finding file to S3
        2) Mock requests
        3) Mock eventbridge

    Test:
        1) Call the handler once

    Assert:
        1) The call should send the events to create findings as expected: with correct detail-type, scan scopes,
        and actual findings.
        2) A new UploadStatus item should be created in the table with the correct data.

    """
    BRANCH_PROTECTION_UPLOAD_S3_JSON = "tests/raw/findings_file_with_asset_info.json"
    setup_test_data(BRANCH_PROTECTION_UPLOAD_S3_JSON, mocker, s3_client)
    mock_get_job_scopes(
        workflow_slug='workflow_slug',
        job_name='branch-protection-github-checker',
        response_scopes=[
            {'scopes': {}, 'plan_item_slug': 'branch-protection-1'},
            {
                'scopes': {
                    'test_id': ['a-private-repository-in-a-non-premium-account-cannot-use-branch-protection', 'foo']
                },
                'plan_item_slug': 'branch-protection-2'
            },
            {
                'scopes': {'location_text': ['jonathanTest9876/e2e-test-repository']},
                'plan_item_slug': 'branch-protection-3'
            },
            {
                'scopes': {'test_id': ['not found']},  # This one shouldn't be matched
                'plan_item_slug': 'not-found'
            },
        ]
    )

    # Test
    with mock_eventbridge('findings') as get_sent_events:
        handle_finding_from_s3(EVENT, None)

    # Assert
    EXPECTED_JIT_EVENT_NAME = 'trigger_scheduled_task'
    assert_upload_status_item_created(
        upload_status_table=mocked_tables[1], jit_event_name=EXPECTED_JIT_EVENT_NAME, backlog=True, snapshots_count=1,
    )

    events = get_sent_events()
    assert len(events) == 1
    event = events[0]
    assert event['source'] == 'finding-service'
    details = event['detail']
    assert details['job'] == {'workflow_slug': 'workflow_slug', 'job_name': 'branch-protection-github-checker'}
    findings_for_scan_scope = event['detail']['findings_for_scan_scope']
    assert len(findings_for_scan_scope) == 1
    assert findings_for_scan_scope[0]['scan_scope'] == {}
    findings_to_upload = findings_for_scan_scope[0]['findings']

    assert_expected_event_detail_type(event)
    assert len(findings_to_upload) == 1
    uploaded_finding = findings_to_upload[0]
    uploaded_finding['plan_items'] = sorted(uploaded_finding['plan_items'])
    assert uploaded_finding == {
        'id': uploaded_finding['id'], 'status': 'PASS',
        'tenant_id': TENANT_ID_FROM_FINDING,
        'asset_id': ASSET_ID_FROM_FINDING, 'asset_type': 'repo',
        'asset_name': 'some-repo', 'asset_domain': None,
        'workflow_suite_id': JIT_EVENT_ID_FROM_FINDING,
        'workflow_id': EXECUTION_ID_FROM_FINDING,
        'first_workflow_suite_id': JIT_EVENT_ID_FROM_FINDING,
        'first_workflow_id': EXECUTION_ID_FROM_FINDING,
        'jit_event_id': JIT_EVENT_ID_FROM_FINDING,
        'jit_event_name': EXPECTED_JIT_EVENT_NAME,
        'first_jit_event_name': EXPECTED_JIT_EVENT_NAME,
        'execution_id': EXECUTION_ID_FROM_FINDING,
        'fixed_at_jit_event_id': None,
        'fixed_at_execution_id': None,
        'vendor': 'github', 'responsible': None, 'control_name': 'github-branch-protection',
        'test_name': 'Branch protection cannot be enabled on this repository',
        'fingerprint': '4b3dc1b6451300d5fc2c2374e6033a15ccbfb47aa635f546c74f1ca182ddde70',
        'test_id': 'a-private-repository-in-a-non-premium-account-cannot-use-branch-protection',
        'issue_text': 'A private repository in a non-premium account cannot use branch protection',
        'issue_confidence': 'UNDEFINED', 'issue_severity': 'HIGH', 'plan_layer': 'code',
        'vulnerability_type': 'code_vulnerability', 'resolution': 'OPEN', 'references': [],
        'location': None, 'location_text': 'jonathanTest9876/e2e-test-repository',
        'code_attributes': None, 'cloud_attributes': None, 'app_attributes': None,
        'created_at': '2023-01-20T11:17:48.356174', 'ended_at': None, 'modified_at': None,
        'last_detected_at': '2023-01-20T11:17:48.356174', 'fix_suggestion': None,
        'backlog': True, 'ignore_rules_ids': [],
        'ignored': False, 'tags': [{'name': 'team', 'value': 'birds'}],
        'asset_priority_score': None, 'filename': None,
        'jobs': [{'workflow_slug': 'workflow_slug', 'job_name': 'branch-protection-github-checker'}],
        'scan_scope': {}, 'job_name': 'branch-protection-github-checker', 'old_fingerprints': ['old_fingerprint'],
        'priority_factors': [], 'priority_score': 0, 'priority_context': None,
        'plan_items': ['branch-protection-1', 'branch-protection-2', 'branch-protection-3'],
        'tickets': [],
        'original_priority_context': None,
        'original_priority_factors': [],
        'manual_factors': {'added': [], 'removed': []},
        'fix_pr_url': None,
        'cwes': [],
        'cves': [],
    }


@freezegun.freeze_time("2020-01-01")
@responses.activate
def test_upload_finding_from_s3__no_findings(dynamodb, mocked_tables, mocker, s3_client):
    """
    This test checks that the handle_finding_from_s3() lambda sends a create_finding_batch event
    with the case of no findings.

    Setup:
        1) Upload an example finding file to S3 with no findings
        2) Mock requests
        3) Mock eventbridge

    Test:
        1) Call the handler once

    Assert:
        1) The call should send the events to create findings as expected: with correct detail-type, scan scopes,
        and actual findings.
        2) A new UploadStatus item should be created in the table with the correct data.

    """
    BRANCH_PROTECTION_UPLOAD_S3_JSON = "tests/raw/branch_protection_no_new_findings.json"
    setup_test_data(BRANCH_PROTECTION_UPLOAD_S3_JSON, mocker, s3_client)
    mock_get_job_scopes(
        workflow_slug='workflow_slug',
        job_name='branch-protection-github-checker',
        response_scopes=[
            {'scopes': {}, 'plan_item_slug': 'branch-protection-1'},
        ]
    )

    # Test
    with mock_eventbridge('findings') as get_sent_events:
        handle_finding_from_s3(EVENT, None)

    # Assert
    EXPECTED_JIT_EVENT_NAME = 'trigger_scheduled_task'
    assert_upload_status_item_created(
        upload_status_table=mocked_tables[1], jit_event_name=EXPECTED_JIT_EVENT_NAME, backlog=True, snapshots_count=1,
    )

    events = get_sent_events()
    assert len(events) == 1
    event = events[0]
    assert event['source'] == 'finding-service'
    details = event['detail']
    assert details['job'] == {'workflow_slug': 'workflow_slug', 'job_name': 'branch-protection-github-checker'}
    findings_for_scan_scope = event['detail']['findings_for_scan_scope']
    assert len(findings_for_scan_scope) == 1
    assert findings_for_scan_scope[0]['scan_scope'] == {}
    findings_to_upload = findings_for_scan_scope[0]['findings']

    assert_expected_event_detail_type(event)
    assert len(findings_to_upload) == 0


@freezegun.freeze_time("2020-01-01")
@responses.activate
def test_upload_finding_from_s3__happy_flow__pr_jit_event(dynamodb, mocked_tables, mocker, s3_client):
    """
    This test checks that the handle_finding_from_s3() lambda sends a create_finding_batch event
    with the correct finding data when a finding file is uploaded to S3.

    Setup:
        1) Upload an example finding file to S3
        2) Mock requests
        3) Mock eventbridge

    Test:
        1) Call the handler once

    Assert:

        1) The call should send the events to create findings as expected: with correct detail-type, scan scopes,
        and actual findings.
        2) A new UploadStatus item should be created in the table with the correct data.

    """
    SEMGREP_UPLOAD_S3_JSON = "tests/raw/semgrep_pr_finding_file.json"
    setup_test_data(SEMGREP_UPLOAD_S3_JSON, mocker, s3_client)
    mock_get_job_scopes(
        workflow_slug='workflow-sast',
        job_name='static-code-analysis-python-semgrep',
        response_scopes=[
            {'scopes': {}, 'plan_item_slug': 'sast'},
        ]
    )
    # Test
    with mock_eventbridge('findings') as get_sent_events:
        handle_finding_from_s3(EVENT, None)

    # Assert

    EXPECTED_JIT_EVENT_NAME = 'pull_request_updated'
    assert_upload_status_item_created(upload_status_table=mocked_tables[1], jit_event_name=EXPECTED_JIT_EVENT_NAME,
                                      backlog=False, snapshots_count=1)

    events = get_sent_events()
    assert len(events) == 1
    event = events[0]
    assert event['source'] == 'finding-service'
    details = event['detail']
    assert details['job'] == {'workflow_slug': 'workflow-sast', 'job_name': 'static-code-analysis-python-semgrep'}
    findings_for_scan_scope = event['detail']['findings_for_scan_scope']
    assert len(findings_for_scan_scope) == 1
    assert findings_for_scan_scope[0]['scan_scope'] == {
        'branch': 'sc-23449-team-service-fix-warmup-plugin-configuration',
        'language': 'python',
        'pr_number': '157',
    }
    findings_to_upload = findings_for_scan_scope[0]['findings']

    assert_expected_event_detail_type(event)
    assert len(findings_to_upload) == 1
    uploaded_finding = findings_to_upload[0]
    assert uploaded_finding == {
        'id': uploaded_finding['id'],
        'status': 'PASS',
        'tenant_id': TENANT_ID_FROM_FINDING,
        'asset_id': ASSET_ID_FROM_FINDING,
        'asset_type': 'repo',
        'asset_name': 'subgroup1/subgroup2/team-service',
        'asset_domain': 'jitsecurity',
        'workflow_suite_id': JIT_EVENT_ID_FROM_FINDING,
        'workflow_id': EXECUTION_ID_FROM_FINDING,
        'first_workflow_suite_id': JIT_EVENT_ID_FROM_FINDING,
        'first_workflow_id': EXECUTION_ID_FROM_FINDING,
        'jit_event_id': JIT_EVENT_ID_FROM_FINDING,
        'jit_event_name': EXPECTED_JIT_EVENT_NAME,
        'first_jit_event_name': EXPECTED_JIT_EVENT_NAME,
        'execution_id': EXECUTION_ID_FROM_FINDING,
        'fixed_at_jit_event_id': None,
        'fixed_at_execution_id': None,
        'vendor': 'github', 'responsible': None, 'control_name': 'semgrep',
        'test_name': 'wp-sql-injection-audit',
        'fingerprint': '7f0ec4076f45ce0c29e86a76c8fa3c6df95eec8d645d2cc1aa4ef85d9a5ae5de',
        'test_id': 'wp-sql-injection-audit',
        'issue_text': 'Detected unsafe API methods. This could lead to SQL Injection '
                      'if the used variable in the functions are user controlled and '
                      'not properly escaped or sanitized. In order to prevent SQL '
                      'Injection, use safe api methods like',
        'issue_confidence': 'UNDEFINED', 'issue_severity': 'HIGH', 'plan_layer': 'code',
        'vulnerability_type': 'code_vulnerability', 'resolution': 'OPEN', 'references': None,
        'location': 'https://github.com/some_org/some_repo/class-database-tools.php#L148-L148',
        'location_text': 'some_org/some_repo',
        'code_attributes': {'base_sha': 'f596060340d632e9c72999a1a8daf807b27f35ef',
                            'branch': 'sc-23449-team-service-fix-warmup-plugin-configuration',
                            'code_snippet': '',
                            'filename': 'class-database-tools.php',
                            'head_sha': '755ffd175a19f3ff8249abf66ae483d93df96892',
                            'last_head_sha': '755ffd175a19f3ff8249abf66ae483d93df96892',
                            'line_range': '148-148',
                            'pr_number': '157',
                            'user_vendor_id': '6392804',
                            'user_vendor_username': 'Shuki-L'}, 'cloud_attributes': None, 'app_attributes': None,
        'created_at': '2023-01-20T11:17:48.356174', 'ended_at': None, 'modified_at': None,
        'last_detected_at': '2023-01-20T11:17:48.356174', 'fix_suggestion': None,
        'backlog': False, 'ignore_rules_ids': [],
        'ignored': False, 'tags': [],
        'asset_priority_score': None, 'filename': None,
        'jobs': [{'workflow_slug': 'workflow-sast', 'job_name': 'static-code-analysis-python-semgrep'}],
        'scan_scope': {'branch': 'sc-23449-team-service-fix-warmup-plugin-configuration', 'language': 'python',
                       'pr_number': '157', 'filepath': 'class-database-tools.php'},
        'job_name': 'static-code-analysis-python-semgrep',
        'old_fingerprints': None,
        'priority_factors': [],
        'priority_score': 0,
        'priority_context': None,
        'plan_items': ['sast'],
        'tickets': [],
        'original_priority_context': None,
        'original_priority_factors': [],
        'manual_factors': {'added': [], 'removed': []},
        'fix_pr_url': None,
        'cwes': [],
        'cves': [],
    }


@freezegun.freeze_time("2020-01-01")
@responses.activate
def test_upload_finding_from_s3__happy_flow__zap(dynamodb, mocked_tables, mocker, s3_client):
    """
    This test checks that the handle_finding_from_s3() lambda sends a create_finding_batch event
    with the correct finding data when a finding file is uploaded to S3.

    Setup:
        1) Upload an example finding file to S3
        2) Mock requests
        3) Mock eventbridge

    Test:
        1) Call the handler once

    Assert:
        1) The call should send the events to create findings as expected: with correct detail-type, scan scopes,
        and actual findings.
        2) A new UploadStatus item should be created in the table with the correct data.

    """
    ZAP_UPLOAD_S3_JSON = "tests/raw/zap_finding.json"
    raw_data = setup_test_data(ZAP_UPLOAD_S3_JSON, mocker, s3_client)
    mock_get_job_scopes(
        workflow_slug='api-security-detection',
        job_name='api-security-detection',
        response_scopes=[
            {'scopes': {}, 'plan_item_slug': 'dast-big'},
            {'scopes': {'issue_severity': ['MEDIUM']}, 'plan_item_slug': 'dast-small'},
        ]
    )

    # Test
    with mock_eventbridge('findings') as get_sent_events:
        handle_finding_from_s3(EVENT, None)

    # Assert
    assert_upload_status_item_created(upload_status_table=mocked_tables[1], jit_event_name='resource_added',
                                      backlog=True, snapshots_count=15)

    events = get_sent_events()
    assert len(events) == 1
    event = events[0]
    assert event['source'] == 'finding-service'
    assert event['detail']['job'] == {'workflow_slug': 'api-security-detection',
                                      'job_name': 'api-security-detection'}
    assert_all_expected_scan_scopes_uploaded(event, raw_data)

    assert_expected_event_detail_type(event)

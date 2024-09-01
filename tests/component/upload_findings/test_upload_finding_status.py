from _decimal import Decimal

import freezegun
import responses

from src.handlers.findings.upload_findings import handle_finding_from_s3
from test_utils.aws.mock_eventbridge import mock_eventbridge

from tests.component.utils.mock_clients.mock_asset import mock_get_asset_api
from tests.component.utils.mock_clients.mock_authentication import mock_get_internal_token_api
from tests.component.utils.mock_clients.mock_execution import mock_get_execution_api
from tests.component.utils.mock_clients.mock_plan import mock_get_job_scopes

FULL_FINDING_FILE_PATH = "tests/raw/findings_file.json"
S3_FILE_NAME = 'findings_file.json'
S3_BUCKET_NAME = 'bucket_name'

S3_RECORD = {
    "Records": [
        {"s3": {"object": {"key": S3_FILE_NAME}, "bucket": {"name": S3_BUCKET_NAME}}}
    ]
}

ASSET_ID_FROM_FINDING = 'bba671c3-bb7e-49a7-8c3d-87d97ec0b7fc'
TENANT_ID_FROM_FINDING = 'bba671c3-bb7e-49a7-8c3d-87d97ec0b7fc'
JIT_EVENT_ID_FROM_FINDING = '8ddc8ce1-9636-4457-9f4b-c0055278e6fa'
EXECUTION_ID_FROM_FINDING = '5c5d3bf8-59da-4a7d-a20c-eda720676f29'


@freezegun.freeze_time("2020-01-01")
@responses.activate
def test_upload_finding_status_dedup(dynamodb, mocked_tables, s3_client):
    """
    This test checks that the handle_finding_from_s3() lambda can be retried. It does that by calling it twice
    with the same parameters, and ensuring that on the first call, the relevant events are sent, and the second call
    with the same events are sent/

    Setup:
        1) Upload an example finding file to S3
        2) Mock requests
        3) Mock eventbridge

    Test:
        1) Call the handler once
        2) Call the handler again

    Assert:
        1) The first call should send the events to create findings batches
        2) The second call should send the events to create findings batches
    """
    s3_client.create_bucket(Bucket=S3_BUCKET_NAME)
    with open(FULL_FINDING_FILE_PATH, 'rb') as f:
        s3_client.upload_fileobj(f, S3_BUCKET_NAME, S3_FILE_NAME)
    mock_get_internal_token_api()
    mock_get_asset_api(ASSET_ID_FROM_FINDING)
    mock_get_execution_api(JIT_EVENT_ID_FROM_FINDING, EXECUTION_ID_FROM_FINDING, TENANT_ID_FROM_FINDING)
    mock_get_job_scopes(workflow_slug='workflow_slug', job_name='branch-protection-github-checker')
    upload_findings_table = mocked_tables[1]

    with mock_eventbridge('findings') as get_sent_events:
        handle_finding_from_s3(S3_RECORD, None)
        items = upload_findings_table.scan()['Items']
        assert len(items) == 1
        assert items[0] == {'PK': 'TENANT#1b2bc442-b8a6-4ab8-a037-d536c2859094',
                            'SK': 'JIT_EVENT_ID#8ddc8ce1-9636-4457-9f4b-c0055278e6fa#'
                                  'EXECUTION_ID#5c5d3bf8-59da-4a7d-a20c-eda720676f29',
                            'jit_event_id': '8ddc8ce1-9636-4457-9f4b-c0055278e6fa', 'jit_event_name':
                                'pull_request_created',
                            'execution_id': '5c5d3bf8-59da-4a7d-a20c-eda720676f29',
                            'created_at': '2023-01-20T11:17:48.356174',
                            'tenant_id': '1b2bc442-b8a6-4ab8-a037-d536c2859094', 'snapshots_count': Decimal('1'),
                            'error_count': Decimal('0'), 'completed_at': None, 'failed_snapshots': [],
                            'is_backlog': False}
    events = get_sent_events()
    assert len(events) == 1
    full_event = events[0]
    batch_id = full_event['detail']['batch_id']
    assert {
               'version': '0',
               'detail-type': 'create-findings-scan-scopes-batch',
               'source': 'finding-service',
               'account': '123456789012',
               'time': '2020-01-01T00:00:00Z',
               'region': 'us-east-1',
               'resources': [],
           }.items() <= full_event.items()
    full_event_detail = full_event['detail']
    assert {
               'tenant_id': '1b2bc442-b8a6-4ab8-a037-d536c2859094',
               'jit_event_id': '8ddc8ce1-9636-4457-9f4b-c0055278e6fa',
               'execution_id': '5c5d3bf8-59da-4a7d-a20c-eda720676f29',
               'control_name': 'github-branch-protection',
               'asset_id': 'bba671c3-bb7e-49a7-8c3d-87d97ec0b7fc',
               'batch_id': batch_id,
               'created_at': '2023-01-20T11:17:48.356174'
           }.items() <= full_event_detail.items()

    with mock_eventbridge('findings') as get_sent_events:
        handle_finding_from_s3(S3_RECORD, None)
        items = upload_findings_table.scan()['Items']
        assert len(items) == 1
        assert items[0] == {'PK': 'TENANT#1b2bc442-b8a6-4ab8-a037-d536c2859094',
                            'SK': 'JIT_EVENT_ID#8ddc8ce1-9636-4457-9f4b-c0055278e6fa#'
                                  'EXECUTION_ID#5c5d3bf8-59da-4a7d-a20c-eda720676f29',
                            'jit_event_id': '8ddc8ce1-9636-4457-9f4b-c0055278e6fa', 'jit_event_name':
                                'pull_request_created',
                            'execution_id': '5c5d3bf8-59da-4a7d-a20c-eda720676f29',
                            'created_at': '2023-01-20T11:17:48.356174',
                            'tenant_id': '1b2bc442-b8a6-4ab8-a037-d536c2859094', 'snapshots_count': Decimal('1'),
                            'error_count': Decimal('0'), 'completed_at': None, 'failed_snapshots': [],
                            'is_backlog': False}
    events = get_sent_events()
    assert len(events) == 1
    full_event = events[0]
    assert {
               'version': '0',
               'detail-type': 'create-findings-scan-scopes-batch',
               'source': 'finding-service',
               'account': '123456789012',
               'time': '2020-01-01T00:00:00Z',
               'region': 'us-east-1',
               'resources': []
           }.items() <= full_event.items()
    full_event_detail = full_event['detail']
    assert {
               'tenant_id': '1b2bc442-b8a6-4ab8-a037-d536c2859094',
               'jit_event_id': '8ddc8ce1-9636-4457-9f4b-c0055278e6fa',
               'execution_id': '5c5d3bf8-59da-4a7d-a20c-eda720676f29',
               'control_name': 'github-branch-protection',
               'asset_id': 'bba671c3-bb7e-49a7-8c3d-87d97ec0b7fc',
               'batch_id': batch_id,  # ensure the batch_id is the same
               'created_at': '2023-01-20T11:17:48.356174'
           }.items() <= full_event_detail.items()

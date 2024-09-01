import json
from freezegun import freeze_time
from test_utils.aws.mock_eventbridge import mock_eventbridge

from src.lib.constants import EXCLUDED_FINDINGS_UPLOAD_BUCKET_NAME
from src.handlers.findings.replay_invalid_findings_upload import handler
from tests.component.utils.mock_mongo_driver import mock_mongo_driver
from tests.fixtures import build_finding_dict


@freeze_time("2023-01-01")
def test_replay_invalid_findings_upload__happy_flow(mocker, mocked_tables, create_firehose_mock, s3_client):
    """
    This test verifies that the replay_invalid_findings_upload handler works as expected.
    Setup:
        - Create a bucket for the excluded findings upload
        - Insert findings to s3 bucket
    Test:
        - Call the handler with the s3 object path
    Verify:
        - The findings are saved to the findings collection
        - All related events are sent to eventbridge
    """

    # Assign
    # Mock mongo driver
    collection = mock_mongo_driver(mocker).findings
    tenant_id = "87ce72c4-2385-42c6-b111-b3629980585e"
    control_name = "control_name"
    asset_name = "asset_name"

    NEW_FINDINGS_AMOUNT = 100
    findings_in_file = [
        build_finding_dict(
            finding_id=f"finding_id-{i}",
            fingerprint=f"fingerprint-{i}",
            tenant_id=tenant_id,
            asset_name=asset_name,
            control_name=control_name,
            jit_event_name='item_activated',
            backlog=True,
        )
        for i in range(NEW_FINDINGS_AMOUNT)
    ]

    # Setup - Create excluded findings bucket
    s3_client.create_bucket(Bucket=EXCLUDED_FINDINGS_UPLOAD_BUCKET_NAME)

    # Insert findings to s3 bucket
    object_key = f'{tenant_id}/2023/1/1-0-0-{control_name}-{asset_name}.json'
    s3_client.put_object(
        Bucket=EXCLUDED_FINDINGS_UPLOAD_BUCKET_NAME,
        Key=object_key,
        Body=json.dumps(findings_in_file),
    )

    event = {"s3_object_path": object_key}
    with mock_eventbridge(bus_name=['findings', 'analytics']) as get_sent_events:
        handler(event, {})

    findings_in_collection = list(collection.find({}))
    assert len(findings_in_collection) == len(findings_in_file)
    sent_events = get_sent_events['findings']()

    # Assert 'findings-created' events were sent correctly
    findings_created_events = sent_events[0:4]
    for i, event in enumerate(findings_created_events):
        assert event['detail-type'] == 'findings-created'
        assert event['source'] == 'finding-service'
        assert event['detail']['tenant_id'] == tenant_id
        assert len(event['detail']['findings']) == 25  # 100 findings in file, 4 batches of 25
        assert event['detail']['is_backlog']
        assert event['detail']['inner_use_case'] == 'upload-findings'
        assert event['detail']['total_batches'] == 4
        assert event['detail']['batch_number'] == i + 1

    finding_opened_events = sent_events[4:]
    assert len(finding_opened_events) == NEW_FINDINGS_AMOUNT
    for i, event in enumerate(finding_opened_events):
        assert event['detail-type'] == 'FindingOpened'
        assert event['source'] == 'finding-service'
        assert event['detail'] == {
            'prev_resolution': None, 'new_resolution': 'OPEN', 'has_fix_suggestion': True,
            'fix_suggestion_source': 'control', 'tenant_id': tenant_id,
            'finding_id': f'finding_id-{i}', 'is_backlog': True, 'duration_minutes': 0.0,
            'asset_id': findings_in_file[i]['asset_id'], 'asset_name': findings_in_file[i]['asset_name'],
            'jit_event_id': findings_in_file[i]['jit_event_id'], 'jit_event_name': 'item_activated',
            'control_name': control_name, 'plan_layer': 'code',
            'vulnerability_type': 'code_vulnerability', 'timestamp': '2023-01-01 00:00:00',
            'created_at': '2023-01-01T00:00:00.000000', 'test_id': 'B105', 'plan_items': ['dummy-plan-item'],
            'priority_factors': [], 'priority_score': 0, 'asset_priority_score': 0,
        }

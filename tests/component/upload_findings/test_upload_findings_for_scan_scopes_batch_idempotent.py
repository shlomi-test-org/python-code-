import uuid
from decimal import Decimal
import responses

from jit_utils.jit_event_names import JitEventName

from src.lib.constants import PK, SK
from src.lib.data.db_table import DbTable
from src.lib.models.finding_model import UploadFindingsStatusItem
from tests.component.utils.mock_clients.mock_asset import mock_get_asset_api
from tests.component.utils.mock_clients.mock_authentication import mock_get_internal_token_api
from tests.component.utils.mock_get_ssm_param import mock_get_ssm_param
from tests.component.utils.mock_mongo_driver import mock_mongo_driver
from tests.fixtures import build_finding_dict


@responses.activate
def test_upload_findings_for_snapshots_batch_handler_is_idempotent(mocker, mocked_tables, create_firehose_mock):
    """
    This test checks that the upload_findings_for_scan_scopes_batch lambda is idempotent. It does that by calling it
    twice
    with the same parameters, and ensuring that on the first call, the relevant events are sent, while the second call
    exists gracefully.
    Setup:
        1) Batch of 3 new findings from 2 snapshots.
        2) Mock requests
        3) Mock eventbridge
    Test:
        1) Call the handler once
        2) Call the handler again
    Assert:
        1) verify all snapshots are uploaded
        2) verify all findings are uploaded to mongo
        3) The second call should exist gracefully
    """
    batch_id = str(uuid.uuid4())
    tenant_id = str(uuid.uuid4())
    asset_id = str(uuid.uuid4())
    control_name = "control_name"
    created_at = "2021-01-01T00:00:00Z"
    jit_event_id = str(uuid.uuid4())
    execution_id = str(uuid.uuid4())
    SCAN_SCOPE_1 = {'branch': 'main'}
    SCAN_SCOPE_2 = {'branch': 'feature'}
    # Assign
    # Mock mongo driver
    collection = mock_mongo_driver(mocker).findings
    mock_get_internal_token_api()

    mock_tags = [{"name": "tag_key", "value": "tag_value"}]
    mock_get_asset_api(asset_id, tags=mock_tags)
    # mock mongo ssm get connection string
    mock_get_ssm_param(mocker)

    # Initialize status item in upload_findings_status_table
    status_item = UploadFindingsStatusItem(jit_event_id=jit_event_id, jit_event_name='An event',
                                           execution_id=execution_id, created_at=created_at,
                                           tenant_id=tenant_id, snapshots_count=2, error_count=0,
                                           failed_snapshots=[],
                                           is_backlog=True)
    item = {
        PK: DbTable.get_key(tenant=tenant_id),
        SK: DbTable.get_key(jit_event_id=jit_event_id, execution_id=execution_id),
        **status_item.dict(),
    }
    _, upload_findings_status_table = mocked_tables

    upload_findings_status_table.put_item(Item=item)
    # Create mock findings for snapshots
    findings_for_scan_scopes = [
        {
            "id": "scan_scope_id_1",
            "scan_scope": SCAN_SCOPE_1,
            "findings": [
                build_finding_dict(
                    tenant_id=tenant_id, asset_id=asset_id, control_name=control_name, scan_scope=SCAN_SCOPE_1,
                    plan_item="p1", plan_items=["p1", "p2"],
                )
            ]
        },
        {
            "id": "scan_scope_id_2",
            "scan_scope": SCAN_SCOPE_2,
            "findings": [
                build_finding_dict(
                    tenant_id=tenant_id, asset_id=asset_id, control_name=control_name, scan_scope=SCAN_SCOPE_2,
                    fingerprint="fingerprint_1", plan_item="p1", plan_items=["p1", "p2"]
                ),
                build_finding_dict(
                    tenant_id=tenant_id, asset_id=asset_id, control_name=control_name, scan_scope=SCAN_SCOPE_2,
                    fingerprint="fingerprint_2", plan_item="p1", plan_items=["p1", "p2"]
                )
            ]
        }
    ]
    event = {
        "detail": {
            "tenant_id": tenant_id,
            "control_name": control_name,
            "asset_id": asset_id,
            "created_at": created_at,
            "jit_event_id": jit_event_id,
            "jit_event_name": JitEventName.MergeDefaultBranch,
            "execution_id": execution_id,
            "findings_for_scan_scope": findings_for_scan_scopes,
            "batch_id": batch_id,
            "job": {
                "workflow_slug": "workflow_slug",
                "job_name": "job_name"
            }
        }
    }
    # Act
    from src.handlers.findings.upload_findings import upload_findings_for_scan_scopes_batch_handler
    upload_findings_for_scan_scopes_batch_handler(event, None)  # type: ignore

    # Assert
    db_items = upload_findings_status_table.scan()['Items']
    assert len(db_items) == 1

    assert db_items[0] == {
        'PK': f'TENANT#{tenant_id}',
        'SK': f'JIT_EVENT_ID#{jit_event_id}#EXECUTION_ID#{execution_id}',
        'jit_event_id': jit_event_id, 'jit_event_name': 'An event',
        'execution_id': execution_id, 'created_at': '2021-01-01T00:00:00Z',
        'tenant_id': tenant_id, 'snapshots_count': Decimal('0'),
        'error_count': Decimal('0'), 'completed_at': None, 'failed_snapshots': [], 'is_backlog': True
    }

    mongo_findings = list(collection.find({}))

    assert len(mongo_findings) == 3

    for finding in mongo_findings:
        assert finding['tenant_id'] == tenant_id
        assert finding['asset_id'] == asset_id
        assert finding['control_name'] == control_name
        assert finding['tags'] == mock_tags
        assert {'k': 'plan_items', 'v': 'p1'} in finding['specs']
        assert {'k': 'plan_items', 'v': 'p2'} in finding['specs']

    # Act
    upload_findings_for_scan_scopes_batch_handler(event, None)  # type: ignore

    # Assert
    # Ensure that no new findings were uploaded to mongo on the second call
    mongo_findings = list(collection.find({}))
    assert len(mongo_findings) == 3

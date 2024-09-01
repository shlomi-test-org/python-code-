import uuid

from src.handlers.findings.upload_findings import upload_findings_completed_handler
from src.lib.data.upload_findings_status import UploadFindingsStatusManager
from src.lib.models.finding_model import UploadFindingsStatusItem


def test_upload_findings_completed_handler(mocker):
    # Assign
    tenant_id = str(uuid.uuid4())
    created_at = "2021-01-01T00:00:00Z"
    jit_event_id = str(uuid.uuid4())
    execution_id = str(uuid.uuid4())
    event = {'Records': [{'eventID': '2660c7db2a01283810c271a553be4307', 'eventName': 'MODIFY', 'eventVersion': '1.1',
                          'eventSource': 'aws:dynamodb', 'awsRegion': 'us-east-1',
                          'dynamodb': {'ApproximateCreationDateTime': 1663759893.0, 'Keys': {'SK': {
                              'S': f'JIT_EVENT_ID#{jit_event_id}#EXECUTION_ID#{execution_id}'},
                              'PK': {
                                  'S': f'TENANT#{tenant_id}'}},
                                       'NewImage': {'failed_snapshots': {'L': []},
                                                    'tenant_id': {'S': tenant_id},
                                                    'completed_at': {'NULL': True},
                                                    'execution_id': {'S': execution_id},
                                                    'jit_event_id': {'S': jit_event_id},
                                                    'SK': {
                                                        'S': f'JIT_EVENT_ID{jit_event_id}#EXECUTION_ID#{execution_id}'},
                                                    'created_at': {'S': created_at},
                                                    'PK': {'S': f'TENANT#{tenant_id}'},
                                                    'is_backlog': {'BOOL': False},
                                                    'jit_event_name': {'S': 'merge_default_branch'},
                                                    'error_count': {'N': '0'}, 'snapshots_count': {'N': '0'}},
                                       'SequenceNumber': '13525400000000041262024781', 'SizeBytes': 529,
                                       'StreamViewType': 'NEW_IMAGE'},
                          'eventSourceARN': 'arn:aws:dynamodb:us-east-1:963685750466:table'
                                            '/UploadFindingsStatus/stream/2022-09-21T11:26:04.755'}]}
    status_item = UploadFindingsStatusItem(jit_event_id=jit_event_id,
                                           jit_event_name='An event',
                                           execution_id=execution_id,
                                           created_at=created_at,
                                           tenant_id=tenant_id,
                                           snapshots_count=0,
                                           error_count=0,
                                           failed_snapshots=[],
                                           is_backlog=False)
    upload_findings_status_manager_mock = mocker.patch.object(
        UploadFindingsStatusManager, "parse_dynamodb_item_to_python_dict",
        return_value=status_item.dict())

    handle_upload_findings_completion_mock = mocker.patch(
        'src.handlers.findings.upload_findings.handle_upload_findings_completion')
    # Act
    upload_findings_completed_handler(event, {})

    # Assert
    assert handle_upload_findings_completion_mock.call_count == 1
    assert upload_findings_status_manager_mock.call_count == 1

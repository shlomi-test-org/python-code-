def get_dynamo_stream_event(tenant_id: str, execution_id: str, jit_event_id: str, created_at: str):
    return {
        'Records': [{
            'eventID': '2660c7db2a01283810c271a553be4307', 'eventName': 'MODIFY', 'eventVersion': '1.1',
            'eventSource': 'aws:dynamodb', 'awsRegion': 'us-east-1',
            'dynamodb': {'ApproximateCreationDateTime': 1663759893.0, 'Keys': {'SK': {
                'S': f'JIT_EVENT_ID#{jit_event_id}#EXECUTION_ID#{execution_id}'},
                'PK': {
                    'S': f'TENANT#{tenant_id}'}},
                         'NewImage': {
                             'failed_snapshots': {'L': []},
                             'tenant_id': {'S': tenant_id},
                             'completed_at': {'NULL': True},
                             'execution_id': {'S': execution_id},
                             'jit_event_id': {'S': jit_event_id},
                             'SK': {
                                 'S': f'JIT_EVENT_ID{jit_event_id}#EXECUTION_ID#{execution_id}'},
                             'created_at': {'S': created_at},
                             'PK': {'S': f'TENANT#{tenant_id}'},
                             'is_backlog': {'BOOL': True},
                             'jit_event_name': {'S': 'merge_default_branch'},
                             'error_count': {'N': '0'}, 'snapshots_count': {'N': '0'}},
                         'SequenceNumber': '13525400000000041262024781', 'SizeBytes': 529,
                         'StreamViewType': 'NEW_IMAGE'},
            'eventSourceARN': 'arn:aws:dynamodb:us-east-1:963685750466:table/'
                              'UploadFindingsStatus/stream/2022-09-21T11:26:04.755'
        }]}

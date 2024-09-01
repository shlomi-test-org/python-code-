import uuid


def put_upload_findings_record_in_db(table, tenant_id='my_tenant_id'):
    jit_event_id = str(uuid.uuid4())
    execution_id = str(uuid.uuid4())
    created_at = '2021-01-01T00:00:00.000Z'
    table.put_item(Item={
        'PK': f'TENANT#{tenant_id}',
        'SK': f'JIT_EVENT_ID#{jit_event_id}#EXECUTION_ID#{execution_id}',
        'jit_event_id': jit_event_id,
        'jit_event_name':   'An event',
        'execution_id': execution_id,
        'created_at': created_at,
        'tenant_id': tenant_id,
        'snapshots_count': 2, 'error_count': 0, 'completed_at': None,
        'failed_snapshots': [], 'is_backlog': True
    })

import boto3


def put_new_batch_status_in_db(
    tenant_id="my_tenant_id",
    jit_event_id="event_id",
    execution_id="exec_id",
    snapshot_count=1,
):
    db = boto3.resource("dynamodb", region_name="us-east-1")
    table = db.Table("UploadFindingsStatus")
    item_to_add = {
        "PK": f"TENANT#{tenant_id}",
        "SK": f"JIT_EVENT_ID#{jit_event_id}#EXECUTION_ID#{execution_id}",
        "completed_at": None,
        "created_at": "2023-01-01T00:00:00",
        "error_count": 0,
        "execution_id": execution_id,
        "failed_snapshots": [],
        "is_backlog": True,
        "jit_event_id": jit_event_id,
        "jit_event_name": "trigger_scheduled_task",
        "snapshots_count": snapshot_count,
        "tenant_id": tenant_id,
    }
    table.put_item(Item=item_to_add)
    return item_to_add

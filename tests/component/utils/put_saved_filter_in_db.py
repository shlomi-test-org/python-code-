import uuid

import boto3

from src.lib.constants import PK, SK, GSI1PK, GSI1SK


def put_saved_filter_in_db(tenant_id: str, should_notify: bool = True):
    db = boto3.resource("dynamodb", region_name="us-east-1")
    table = db.Table("Findings")
    id = str(uuid.uuid4())
    created_at = "now"
    item = {
        'should_notify': should_notify,
        'id': id,
        'tenant_id': tenant_id,
        'name': 'some-filter',
        'description': 'desc',
        'is_default': False,
        'created_at': created_at,
        'filters': [
            {
                "key": "time_ago",
                "type": "single_select",
                "valueOptions": [
                    "ONE_WEEK",
                    "TWO_WEEKS",
                    "ONE_MONTH"
                ],
                "selectedValue": "ONE_MONTH",
                "defaultValue": "ONE_MONTH",
                "isVisible": False,
                "defaultVisibility": True
            },
            {
                "key": "resolution",
                "type": "multi_select",
                "valueOptions": [
                    "OPEN",
                    "FIXED",
                    "IGNORED"
                ],
                "selectedValue": [
                    "OPEN"
                ],
                "defaultValue": [
                    "OPEN"
                ],
                "isVisible": False,
                "defaultVisibility": True
            },
        ],
        PK: f"TENANT#{tenant_id}",
        SK: f"SAVED_FILTER#{id}",
        GSI1PK: f"TENANT#{tenant_id}",
        GSI1SK: f"CREATED_AT#{created_at}",
    }
    table.put_item(Item=item)
    return item

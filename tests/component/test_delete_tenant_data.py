import uuid
from http import HTTPStatus

from jit_utils.models.findings.entities import Resolution

from src.handlers.delete_tenant_data import handler
from tests.component.utils.findings_dict_to_mongo_record import finding_dict_to_mongo_record
from tests.component.utils.get_handler_event import get_handler_event
from tests.component.utils.mock_mongo_driver import mock_mongo_driver
from tests.component.utils.put_finding_in_db import put_finding_in_db
from tests.component.utils.put_upload_findings_record_in_db import put_upload_findings_record_in_db
from tests.fixtures import build_finding_dict, build_ignore_rule_dict


def test_delete_tenant_data__happy_flow(mocked_tables, mocker):
    """
    Setup:
        - A tenant with data in the DB
    Test:
        - Call the handler with the correct tenant id
    Assert:
        - All data is deleted
    """
    # Setup - Mocked tables and insert tenant data
    tenant_id = str(uuid.uuid4())

    # Mock mongo driver
    mongo_finding_record = finding_dict_to_mongo_record(
        build_finding_dict(tenant_id=tenant_id, resolution=Resolution.OPEN)
    )
    mongo_ignore_rule_record = build_ignore_rule_dict(tenant_id=tenant_id)

    mongo_client = mock_mongo_driver(mocker)
    mocked_findings_collection = mongo_client.findings
    mocked_ignore_rules_collection = mongo_client.ignore_rules
    mocked_findings_collection.insert_one(mongo_finding_record)
    mocked_ignore_rules_collection.insert_one(mongo_ignore_rule_record)

    # Mock dynamo tables
    findings_table, upload_findings_status_table = mocked_tables
    put_finding_in_db(tenant_id=tenant_id)
    put_upload_findings_record_in_db(upload_findings_status_table, tenant_id=tenant_id)

    # Test - Call delete tenant data with correct tenant id
    event = get_handler_event(tenant_id=tenant_id, body={})
    response = handler(event, {})

    # Assert - All data has deleted
    assert response['statusCode'] == HTTPStatus.OK
    assert findings_table.scan()['Count'] == 0
    assert upload_findings_status_table.scan()['Count'] == 0
    assert list(mocked_findings_collection.find()) == []
    assert list(mocked_ignore_rules_collection.find()) == []


def test_delete_tenant_data__different_tenant_id(mocked_tables, mocker):
    """
    Setup:
        - A tenant with data in the DB
    Test:
        - Call the handler with tenant id that differs from your own
    Assert:
        - No data has deleted
    """
    # Setup - Mocked tables and insert tenant data
    tenant_id = str(uuid.uuid4())

    # Mock mongo driver
    mongo_finding_record = finding_dict_to_mongo_record(
        build_finding_dict(tenant_id=tenant_id, resolution=Resolution.OPEN)
    )
    mongo_ignore_rule_record = build_ignore_rule_dict(tenant_id=tenant_id)

    mongo_client = mock_mongo_driver(mocker)
    mocked_findings_collection = mongo_client.findings
    mocked_ignore_rules_collection = mongo_client.ignore_rules
    mocked_findings_collection.insert_one(mongo_finding_record)
    mocked_ignore_rules_collection.insert_one(mongo_ignore_rule_record)

    # Mock dynamo tables
    findings_table, upload_findings_status_table = mocked_tables
    put_finding_in_db(tenant_id=tenant_id)
    put_upload_findings_record_in_db(upload_findings_status_table, tenant_id=tenant_id)

    # Test - Call delete tenant data with correct tenant id
    different_tenant_id = str(uuid.uuid4())
    event = get_handler_event(tenant_id=different_tenant_id, body={})
    response = handler(event, {})

    # Assert - All data has deleted
    assert response['statusCode'] == HTTPStatus.OK
    assert findings_table.scan()['Count'] == 1
    assert upload_findings_status_table.scan()['Count'] == 1
    assert len(list(mocked_findings_collection.find())) == 1
    assert len(list(mocked_ignore_rules_collection.find())) == 1

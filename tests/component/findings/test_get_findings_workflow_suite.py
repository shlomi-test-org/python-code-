import json
import uuid

from jit_utils.utils.permissions import Read

from src.handlers.get_findings import get_by_workflow_id
from src.lib.data.mongo.utils import convert_item_to_return_finding
from tests.component.utils.get_handler_event import get_handler_event
from tests.component.utils.mock_get_ssm_param import mock_get_ssm_param
from tests.component.utils.mock_mongo_data_api import MongoDataApiMock
from tests.fixtures import build_finding_dict
import responses


@responses.activate
def test_get_findings_for_workflow_suite_id(mocker, mocked_tables, env_variables):
    """
    This test verifies that the get_findings handler returns the correct open findings map for a given workflow suite id
    Setup:
        1) Mock the get_api_url_from_ssm function
        2) Initialize the MongoDataApiMock
        3) Insert 5 mock findings in the database, only 3 of them from that workflow suite id, and one of them ignored
    Test:
        1) Call the get_by_workflow_id handler
    Assert:
        1) Verify that the HTTP response status code is 200
        2) check that the open findings with the requested suite id are returned mapped to the control
    """
    tenant_id = str(uuid.uuid4())
    token = "token"
    workflow_suite_id = str(uuid.uuid4())
    requested_workflow_suite_id = str(uuid.uuid4())

    findings = [
        build_finding_dict(finding_id="123", tenant_id=tenant_id,
                           issue_severity='HIGH',
                           control_name="kics",
                           workflow_suite_id=requested_workflow_suite_id,
                           created_at="2023-03-26T06:09:03.063186"),
        build_finding_dict(finding_id="234", tenant_id=tenant_id,
                           issue_severity='HIGH',
                           control_name="gitleaks",
                           workflow_suite_id=requested_workflow_suite_id,
                           created_at="2023-03-28T06:09:03.063186"),
        build_finding_dict(finding_id="456", tenant_id=tenant_id,
                           issue_severity='HIGH',
                           control_name="kics",
                           ignored=True,
                           workflow_suite_id=requested_workflow_suite_id,
                           created_at="2023-03-25T06:09:03.063186"),
        build_finding_dict(finding_id="458", tenant_id=tenant_id,
                           issue_severity='HIGH',
                           control_name="kics",
                           workflow_suite_id=workflow_suite_id,
                           created_at="2023-03-24T06:09:03.063186"),
        build_finding_dict(finding_id="784", tenant_id=tenant_id,
                           issue_severity='HIGH',
                           control_name="kics",
                           workflow_suite_id=workflow_suite_id,
                           created_at="2023-02-28T06:09:03.063186"),

    ]

    event = get_handler_event(
        tenant_id=tenant_id,
        token=token,
        permissions=[Read.FINDINGS],
        path_parameters={'workflow_suite_id': requested_workflow_suite_id}
    )

    # Mock the get_api_url_from_ssm function
    mocked_base_path = mock_get_ssm_param(mocker)

    # Initialize the mocked data api class and mock the find request
    mocked_data_api = MongoDataApiMock(mocked_base_path)

    # Insert some mock data
    mocked_data_api.db.findings.insert_many(findings)

    expected_response = {'gitleaks': [
        convert_item_to_return_finding(findings[1]),
    ],
        'kics': [
            convert_item_to_return_finding(findings[0])
            ]
    }

    # Act
    response = get_by_workflow_id(event, {})

    # Assert
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body == expected_response

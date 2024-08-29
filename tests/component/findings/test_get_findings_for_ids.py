import json
import uuid

from jit_utils.utils.permissions import Read
from jit_utils.models.findings.entities import Finding, UiResolution

from src.handlers.get_findings import get_by_ids
from tests.component.utils.get_handler_event import get_handler_event
from tests.component.utils.mock_get_ssm_param import mock_get_ssm_param
from tests.component.utils.mock_mongo_data_api import MongoDataApiMock
from tests.fixtures import build_finding_dict
import responses


@responses.activate
def test_get_findings_for_ids(mocker, mocked_tables, env_variables):
    """
    This test verifies that the get_findings handler returns the correct findings for a given finding_ids list
    Setup:
        1) Mock the get_api_url_from_ssm function
        2) Initialize the MongoDataApiMock
        3) Insert 5 mock findings in the database, 1- ignore, 1- fixed, 3- open
    Test:
        1) Call the get_by_ids handler
    Assert:
        1) Verify that the HTTP response status code is 200
        2) Check that the response body contains the 5 mock findings returned by the function
        with the expected resolutions
    """
    tenant_id = str(uuid.uuid4())
    token = "token"
    findings = [
        build_finding_dict(finding_id="123", tenant_id=tenant_id,
                           with_specs=True, issue_severity='HIGH',
                           ignored=True,
                           created_at="2023-03-26T06:09:03.063186"),
        build_finding_dict(finding_id="234", tenant_id=tenant_id,
                           resolution=UiResolution.FIXED,
                           with_specs=True, issue_severity='HIGH',
                           created_at="2023-03-28T06:09:03.063186"),
        build_finding_dict(finding_id="456", tenant_id=tenant_id,
                           with_specs=True, issue_severity='HIGH',
                           created_at="2023-03-25T06:09:03.063186"),
        build_finding_dict(finding_id="458", tenant_id=tenant_id,
                           with_specs=True, issue_severity='HIGH',
                           created_at="2023-03-24T06:09:03.063186"),
        build_finding_dict(finding_id="784", tenant_id=tenant_id,
                           with_specs=True, issue_severity='HIGH',
                           created_at="2023-02-28T06:09:03.063186"),

    ]
    event = get_handler_event(
        tenant_id=tenant_id,
        token=token,
        body=[finding['id'] for finding in findings],
        permissions=[Read.FINDINGS],
    )

    # Mock the get_api_url_from_ssm function
    mocked_base_path = mock_get_ssm_param(mocker)

    # Initialize the mocked data api class and mock the find request
    mocked_data_api = MongoDataApiMock(mocked_base_path)

    # Insert some mock data
    mocked_data_api.db.findings.insert_many(findings)

    expected_sorted_findings = sorted(findings, key=lambda x: x['created_at'], reverse=True)
    expected_sorted_findings = [Finding(**finding) for finding in expected_sorted_findings]
    for expected_finding in expected_sorted_findings:
        if expected_finding.ignored:
            expected_finding.resolution = UiResolution.IGNORED

    # Act
    response = get_by_ids(event, {})

    # Assert
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert len(body) == 5
    assert body == expected_sorted_findings

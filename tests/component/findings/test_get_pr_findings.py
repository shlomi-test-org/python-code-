import json
import uuid

import responses
from jit_utils.utils.permissions import Read
from jit_utils.models.findings.entities import Finding, UiResolution

from src.handlers.get_findings import get_by_pr
from src.lib.tools import decode_next_page_key
from tests.component.utils.get_handler_event import get_handler_event
from tests.component.utils.mock_get_ssm_param import mock_get_ssm_param
from tests.component.utils.mock_mongo_data_api import MongoDataApiMock
from tests.fixtures import build_finding_dict


@responses.activate
def test_less_than_page_limit_pr_findings__with_scrolling(mocker, mocked_tables, env_variables):
    """
    Setup:
        1) insert 30 findings to MongoDB
        2) Mock ignore rules table
        4) Mock get_api_url_from_ssm function
        5) Initialize the MongoDataApiMock class
    Test:
        1) Call 'get_pr_findings' handler to retrieve the findings
    Assert:
        1) Verify that the HTTP response status code is 200
        2) Check that the 30 first findings were actually returned
        3) Verify that the next page token is None
    """
    # Mock the get_api_url_from_ssm function
    mocked_base_path = mock_get_ssm_param(mocker)

    # Initialize the mocked data api class and mock the find request
    mocked_data_api = MongoDataApiMock(mocked_base_path)

    # Insert some mock data
    tenant_id = str(uuid.uuid4())
    branch = "branch"
    assert_id = "0199ab9b-1862-437d-9eb6-7e07400654e1"
    pull_request_number = '163'
    params = {'asset_id': assert_id,
              'branch': branch,
              'pull_request_number': pull_request_number}
    event = get_handler_event(query_string_parameters=params, tenant_id=tenant_id, token='token',
                              permissions=[Read.FINDINGS])
    findings = [build_finding_dict(finding_id=f"finding-{i}", tenant_id=tenant_id,
                                   branch=branch, asset_id=assert_id,
                                   ignored=True,
                                   pr_number=pull_request_number)
                for i in range(30)]

    mocked_data_api.db.findings.insert_many(findings)
    # sort the findings by created_at
    expected_sorted_findings = sorted(findings, key=lambda x: x['created_at'], reverse=True)
    expected_sorted_findings = [Finding(**finding) for finding in expected_sorted_findings]
    # update the findings with the ui resolution ignored
    for finding in expected_sorted_findings:
        finding.resolution = UiResolution.IGNORED

    # Act
    response = get_by_pr(event, {})

    # Assert
    body = json.loads(response['body'])
    assert body['findings'] == expected_sorted_findings[:30]
    last_evaluated_key = body.get('last_evaluated_key')
    assert not last_evaluated_key


@responses.activate
def test_get_exact_page_limit_pr_findings__with_scrolling(mocker, mocked_tables, env_variables):
    """
    Setup:
        1) insert 50 findings to MongoDB
        2) Mock get_api_url_from_ssm function
        3) Initialize the MongoDataApiMock class
    Test:
        1) Call 'get_pr_findings' handler to retrieve the findings
    Assert:
        1) Verify that the HTTP response status code is 200
        2) Check that all 50 findings were actually returned
        3) Verify that the next page token is None
    """
    # Mock the get_api_url_from_ssm function
    mocked_base_path = mock_get_ssm_param(mocker)

    # Initialize the mocked data api class and mock the find request
    mocked_data_api = MongoDataApiMock(mocked_base_path)

    # Insert some mock data
    tenant_id = str(uuid.uuid4())
    branch = "branch"
    assert_id = "0199ab9b-1862-437d-9eb6-7e07400654e1"
    pull_request_number = '163'
    params = {'asset_id': assert_id,
              'branch': branch,
              'pull_request_number': pull_request_number}
    event = get_handler_event(query_string_parameters=params, tenant_id=tenant_id, token='token',
                              permissions=[Read.FINDINGS])
    findings = [build_finding_dict(finding_id=f"finding-{i}", tenant_id=tenant_id,
                                   branch=branch, asset_id=assert_id,
                                   pr_number=pull_request_number)
                for i in range(50)]
    mocked_data_api.db.findings.insert_many(findings)
    # sort the findings by created_at
    expected_sorted_findings = sorted(findings, key=lambda x: x['created_at'], reverse=True)
    expected_sorted_findings = [Finding(**finding) for finding in expected_sorted_findings]

    # Act
    response = get_by_pr(event, {})

    # Assert
    body = json.loads(response['body'])
    assert body['findings'] == expected_sorted_findings[:50]
    last_evaluated_key = body.get('last_evaluated_key')
    assert not last_evaluated_key


@responses.activate
def test_more_than_one_page_of_get_pr_findings__with_scrolling(mocker, mocked_tables, env_variables):
    """
    Setup:
        1) insert 60 findings to MongoDB
        2) Mock get_api_url_from_ssm function
        3) Initialize the MongoDataApiMock class
    Test:
        1) Call 'get_pr_findings' handler to retrieve the findings
    Assert:
        1) Verify that the HTTP response status code is 200
        2) Check that the 50 first findings were actually returned
        3) Verify that the next page token is the last finding id
    Test:
        1) Call 'get_pr_findings' handler to retrieve the findings with a limit of 3
        and next_page_key of the previous response
    Assert:
        1) Verify that the HTTP response status code is 200
        2) Check that the 10 last findings were actually returned
        3) Verify that the next_page_key in the response body is None
    """
    # Mock the get_api_url_from_ssm function
    mocked_base_path = mock_get_ssm_param(mocker)

    # Initialize the mocked data api class and mock the find request
    mocked_data_api = MongoDataApiMock(mocked_base_path)

    # Insert some mock data
    tenant_id = str(uuid.uuid4())
    branch = "branch"
    assert_id = "0199ab9b-1862-437d-9eb6-7e07400654e1"
    pull_request_number = '163'
    params = {'asset_id': assert_id,
              'branch': branch,
              'pull_request_number': pull_request_number}
    event = get_handler_event(query_string_parameters=params, tenant_id=tenant_id, token='token',
                              permissions=[Read.FINDINGS])
    findings = [build_finding_dict(finding_id=f"finding-{i}", tenant_id=tenant_id,
                                   branch=branch, asset_id=assert_id,
                                   pr_number=pull_request_number)
                for i in range(60)]
    mocked_data_api.db.findings.insert_many(findings)
    # sort the findings by created_at
    expected_sorted_findings = sorted(findings, key=lambda x: x['created_at'], reverse=True)
    expected_sorted_findings = [Finding(**finding) for finding in expected_sorted_findings]

    # Act
    response = get_by_pr(event, {})

    # Assert
    body = json.loads(response['body'])
    assert body['findings'] == expected_sorted_findings[:50]
    last_evaluated_key = body['last_evaluated_key']
    assert last_evaluated_key

    last_id, last_created_at = decode_next_page_key(last_evaluated_key)
    # Assert that the last id is the last id in the mocked findings
    assert last_id == body['findings'][49]['id']

    # ----- Get the next batch of findings the last 10 findings -----
    event['queryStringParameters']['last_evaluated_key'] = last_evaluated_key

    # Act
    response = get_by_pr(event, {})

    # Assert
    body = json.loads(response['body'])
    # expected_sorted_findings[50:] should be the last 10 findings in the list (total of 5 findings)
    assert body['findings'] == expected_sorted_findings[50:]
    last_evaluated_key = body['last_evaluated_key']
    assert last_evaluated_key is None

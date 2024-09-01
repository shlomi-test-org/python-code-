import copy
import json
import uuid

import responses
from jit_utils.models.findings.entities import Resolution, Finding

from jit_utils.models.tags.entities import Tag
from jit_utils.utils.permissions import Read

from src.handlers.findings.get_findings import handler
from src.lib.tools import decode_next_page_key
from tests.component.findings.mock_events import GET_OPEN_NOT_IGNORED_HIGH_SEVERITY_FINDINGS_EVENT, \
    GET_OPEN_NOT_IGNORED_HIGH_SEVERITY_FINDINGS_EVENT_AS_CSV, GET_IGNORED_HIGH_SEVERITY_FINDINGS_EVENT, \
    GET_FINDINGS_EVENT_NO_FILTERS, GET_TEAM_FINDINGS_EVENT
from tests.component.utils.get_handler_event import get_handler_event
from tests.component.utils.mock_get_ssm_param import mock_get_ssm_param
from tests.component.utils.mock_mongo_data_api import MongoDataApiMock
from tests.component.utils.mock_mongo_driver import mock_mongo_driver
from tests.fixtures import build_finding_dict
from src.lib.constants import S3_FINDINGS_CSV_BUCKET_NAME


@responses.activate
def test_get_all_findings(mocker, mocked_tables, env_variables):
    """
      This test should get all the findings in the database (5 findings), the findings are from different resolutions:
       OPEN, FIXED and IGNORED
      Setup:
          1) Mock the get_api_url_from_ssm function
          2) Initialize the MongoDataApiMock
          3) Insert 5 mock findings in the database
          4) Create ignore rules for 3 of the findings
      Test:
          1) Call the get_findings handler to retrieve the findings with a limit of 5
      Assert:
          1) Verify that the HTTP response status code is 200
          2) Check that the response body contains the 5 mock findings returned by the function,
          with the correct resolutions
          3) Verify that the next_page_key in the response body is None
      """
    # Assign
    tenant_id = GET_FINDINGS_EVENT_NO_FILTERS['requestContext']['authorizer']['tenant_id']
    findings = [
        build_finding_dict(finding_id="123", tenant_id=tenant_id,
                           fingerprint="fingerprint1",
                           resolution=Resolution.OPEN,
                           with_specs=True, issue_severity='HIGH',
                           ignored=True,
                           created_at="2023-07-28T06:09:03.063186"),
        build_finding_dict(finding_id="234", tenant_id=tenant_id,
                           fingerprint="fingerprint2",
                           resolution=Resolution.OPEN,
                           with_specs=True, issue_severity='HIGH',
                           ignored=True,
                           created_at="2023-07-26T05:09:03.063186"),
        build_finding_dict(finding_id="456", tenant_id=tenant_id,
                           fingerprint="fingerprint3",
                           resolution=Resolution.OPEN,
                           with_specs=True, issue_severity='HIGH',
                           ignored=True,
                           created_at="2023-07-25T04:09:03.063186"),
        build_finding_dict(finding_id="458", tenant_id=tenant_id,
                           fingerprint="fingerprint4",
                           resolution=Resolution.OPEN,
                           with_specs=True, issue_severity='HIGH',
                           created_at="2023-03-24T06:09:03.063186"),
        build_finding_dict(finding_id="784", tenant_id=tenant_id,
                           fingerprint="fingerprint5",
                           resolution=Resolution.FIXED,
                           with_specs=True, issue_severity='HIGH',
                           created_at="2023-02-28T06:09:03.063186"),
    ]

    # Mock the get_api_url_from_ssm function
    mocked_base_path = mock_get_ssm_param(mocker)

    # Initialize the mocked data api class and mock the find request
    mocked_data_api = MongoDataApiMock(mocked_base_path)

    # Insert some mock data
    mocked_data_api.db.findings.insert_many(findings)

    # sort the findings by created_at
    expected_findings = sorted(findings, key=lambda x: x['created_at'], reverse=True)
    expected_findings = [Finding(**finding) for finding in expected_findings]

    # 5 findings should be returned and the next page token should be None,
    expected_response = {'findings': expected_findings,
                         'next_page_key': None}

    # Spy on the find method of the mocked_data_api
    mocker.spy(mocked_data_api.db.findings, 'find')

    # Act
    event = copy.deepcopy(GET_FINDINGS_EVENT_NO_FILTERS)
    event['queryStringParameters']['page_limit'] = 5
    event['queryStringParameters']['next_page_key'] = None
    response = handler(event, {})

    # Assert
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body == expected_response

    # Verify the find method was called with the correct arguments
    args, kwargs = mocked_data_api.db.findings.find.call_args
    assert kwargs['filter'] == {
        'tenant_id': tenant_id,
        '$and': [
            {'specs': {'$elemMatch': {'k': 'resolution', 'v': {'$in': ['OPEN', 'FIXED']}}}}
        ]
    }
    assert kwargs['limit'] == 6
    assert list(kwargs['sort']) == [('created_at', -1), ('_id', -1)]


def test_get_findings__with_no_next_page__should_return_findings_without_next_token_no_jwt_token(mocker,
                                                                                                 mocked_tables,
                                                                                                 env_variables):
    """
    This test case verifies that the get_findings function correctly returns all findings when there are no more pages
    left to paginate through. Specifically, the test aims to verify that when a request is made to fetch the findings
    with a limit of 5 findings, and the MongoDB database contains 5 findings, then 5 findings should be returned,
    and the next token should be None.
    No jwt token is passed in the event, so the MongoDriver should be used.
    Setup:
        1) Mock the get_api_url_from_ssm function
        2) Initialize the MongoDataApiMock
        3) Insert 5 mock findings in the database
    Test:
        1) Call the get_findings handler to retrieve the findings with a limit of 5
        2) The event that is sent is the GET_OPEN_HIGH_SEVERITY_FINDINGS_EVENT
    Assert:
        1) Verify that the HTTP response status code is 200
        2) Check that the response body contains the 5 mock findings returned by the function
        3) Verify that the next_page_key in the response body is None
    """
    # Assign
    # Mock mongo driver
    findings_collection = mock_mongo_driver(mocker).findings
    # Insert some mock data
    tenant_id = GET_OPEN_NOT_IGNORED_HIGH_SEVERITY_FINDINGS_EVENT['requestContext']['authorizer']['tenant_id']
    findings = [
        build_finding_dict(finding_id="123", tenant_id=tenant_id,
                           with_specs=True, issue_severity='HIGH',
                           created_at="2023-03-26T06:09:03.063186"),
        build_finding_dict(finding_id="234", tenant_id=tenant_id,
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
    findings_collection.insert_many(findings)
    # sort the findings by created_at
    expected_findings = sorted(findings, key=lambda x: x['created_at'], reverse=True)
    expected_findings = [Finding(**finding) for finding in expected_findings]
    expected_response = {'findings': expected_findings,
                         'next_page_key': None}
    # Act
    event = copy.deepcopy(GET_OPEN_NOT_IGNORED_HIGH_SEVERITY_FINDINGS_EVENT)
    event['queryStringParameters']['page_limit'] = len(findings)
    event['requestContext']['authorizer'].pop('token')  # remove the jwt token
    response = handler(event, {})

    # Assert
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    body['findings'] = [Finding(**finding) for finding in body['findings']]

    assert body == expected_response


@responses.activate
def test_get_findings__with_ignore_rules__request_ignored_true(mocker, mocked_tables, env_variables):
    """
    The lambda should return the ignored findings
    Setup:
        1) insert 5 findings to MongoDB
        4) Mock get_api_url_from_ssm function
        5) Initialize the MongoDataApiMock class
    Test:
        1) Call 'get_findings' handler

    Assert:
        1) response status code == 200
        2) check that the 3 ignored findings were actually returned
        3) there is no next page key
    """
    # Assign
    tenant_id = GET_IGNORED_HIGH_SEVERITY_FINDINGS_EVENT['requestContext']['authorizer']['tenant_id']
    findings = [
        build_finding_dict(finding_id="123", tenant_id=tenant_id,
                           fingerprint="fingerprint1",
                           with_specs=True, issue_severity='HIGH',
                           ignored=True,
                           created_at="2023-07-28T06:09:03.063186"),
        build_finding_dict(finding_id="234", tenant_id=tenant_id,
                           fingerprint="fingerprint2",
                           with_specs=True, issue_severity='HIGH',
                           ignored=True,
                           created_at="2023-07-26T05:09:03.063186"),
        build_finding_dict(finding_id="456", tenant_id=tenant_id,
                           fingerprint="fingerprint3",
                           with_specs=True, issue_severity='HIGH',
                           ignored=True,
                           created_at="2023-07-25T04:09:03.063186"),
        build_finding_dict(finding_id="458", tenant_id=tenant_id,
                           fingerprint="fingerprint4",
                           with_specs=True, issue_severity='HIGH',
                           created_at="2023-03-24T06:09:03.063186"),
        build_finding_dict(finding_id="784", tenant_id=tenant_id,
                           fingerprint="fingerprint5",
                           with_specs=True, issue_severity='HIGH',
                           created_at="2023-02-28T06:09:03.063186"),
    ]
    ignored_findings = [Finding(**findings[0]), Finding(**findings[1]), Finding(**findings[2])]

    # Mock the get_api_url_from_ssm function
    mocked_base_path = mock_get_ssm_param(mocker)

    # Initialize the mocked data api class and mock the find request
    mocked_data_api = MongoDataApiMock(mocked_base_path)

    # Insert some mock data
    mocked_data_api.db.findings.insert_many(findings)

    expected_response = {'findings': ignored_findings, 'next_page_key': None}

    # Act
    event = copy.deepcopy(GET_IGNORED_HIGH_SEVERITY_FINDINGS_EVENT)
    event['queryStringParameters']['page_limit'] = 5
    event['queryStringParameters']['next_page_key'] = None
    response = handler(event, {})

    # Assert
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body == expected_response


@responses.activate
def test_get_findings__with_no_next_page__should_return_findings_without_next_token(mocker,
                                                                                    mocked_tables,
                                                                                    env_variables):
    """
    This test case verifies that the get_findings function correctly returns all findings when there are no more pages
    left to paginate through. Specifically, the test aims to verify that when a request is made to fetch the findings
    with a limit of 5 findings, and the MongoDB database contains 5 findings, then 5 findings should be returned,
    and the next token should be None.
    Setup:
        1) Mock the get_api_url_from_ssm function
        2) Initialize the MongoDataApiMock
        3) Insert 5 mock findings in the database
    Test:
        1) Call the get_findings handler to retrieve the findings with a limit of 5
        2) The event that is sent is the GET_OPEN_HIGH_SEVERITY_FINDINGS_EVENT
    Assert:
        1) Verify that the HTTP response status code is 200
        2) Check that the response body contains the 5 mock findings returned by the function
        3) Verify that the next_page_key in the response body is None
    """
    # Assign
    # Mock the get_api_url_from_ssm function
    mocked_base_path = mock_get_ssm_param(mocker)
    # Initialize the mocked data api class and mock the find request
    mocked_data_api = MongoDataApiMock(mocked_base_path)
    # Insert some mock data
    tenant_id = GET_OPEN_NOT_IGNORED_HIGH_SEVERITY_FINDINGS_EVENT['requestContext']['authorizer']['tenant_id']
    findings = [
        build_finding_dict(finding_id="123", tenant_id=tenant_id,
                           with_specs=True, issue_severity='HIGH',
                           created_at="2023-03-26T06:09:03.063186"),
        build_finding_dict(finding_id="234", tenant_id=tenant_id,
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
    mocked_data_api.db.findings.insert_many(findings)
    # sort the findings by created_at
    expected_findings = sorted(findings, key=lambda x: x['created_at'], reverse=True)
    expected_findings = [Finding(**finding) for finding in expected_findings]
    expected_response = {'findings': expected_findings,
                         'next_page_key': None}
    # Act
    event = copy.deepcopy(GET_OPEN_NOT_IGNORED_HIGH_SEVERITY_FINDINGS_EVENT)
    event['queryStringParameters']['page_limit'] = len(findings)
    response = handler(event, {})

    # Assert
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    body['findings'] = [Finding(**finding) for finding in body['findings']]

    assert body == expected_response


@responses.activate
def test_get_open_not_ignored_findings(mocker, mocked_tables, env_variables):
    """
    This tests a request to get the findings with a limit of 5 findings, the DB contains total of 5 findings.
    4 findings should be returned because one of the findings is ignored.
    Setup:
        1) insert 5 findings to MongoDB, one is ignored
        2) Mock ignore rules table
        4) Mock get_api_url_from_ssm function
        5) Initialize the MongoDataApiMock class
    Test:
        1) Call 'get_findings' handler to retrieve the findings with a limit of 5 and next_page_key = None
        2) The event that is sent is GET_OPEN_HIGH_SEVERITY_FINDINGS_EVENT

    Assert:
        1) Verify that the HTTP response status code is 200
        2) Check that the 4 not ignored findings are returned
        3) Verify that the next_page_key in the response body is None
    """
    # Assign
    tenant_id = GET_OPEN_NOT_IGNORED_HIGH_SEVERITY_FINDINGS_EVENT['requestContext']['authorizer']['tenant_id']
    findings = [
        build_finding_dict(finding_id="123", tenant_id=tenant_id,
                           fingerprint="fingerprint1",
                           with_specs=True, issue_severity='HIGH',
                           ignored=True,
                           created_at="2023-07-26T06:09:03.063186"),
        build_finding_dict(finding_id="234", tenant_id=tenant_id,
                           fingerprint="fingerprint2",
                           with_specs=True, issue_severity='HIGH',
                           created_at="2023-03-28T06:09:03.063186"),
        build_finding_dict(finding_id="456", tenant_id=tenant_id,
                           fingerprint="fingerprint3",
                           with_specs=True, issue_severity='HIGH',
                           created_at="2023-03-25T06:09:03.063186"),
        build_finding_dict(finding_id="458", tenant_id=tenant_id,
                           fingerprint="fingerprint4",
                           with_specs=True, issue_severity='HIGH',
                           created_at="2023-03-24T06:09:03.063186"),
        build_finding_dict(finding_id="784", tenant_id=tenant_id,
                           fingerprint="fingerprint5",
                           with_specs=True, issue_severity='HIGH',
                           created_at="2023-02-28T06:09:03.063186"),
    ]
    # Mock the get_api_url_from_ssm function
    mocked_base_path = mock_get_ssm_param(mocker)

    # Initialize the mocked data api class and mock the find request
    mocked_data_api = MongoDataApiMock(mocked_base_path)

    # Insert some mock data
    mocked_data_api.db.findings.insert_many(findings)
    # sort the findings by created_at
    expected_sorted_findings = sorted(findings, key=lambda x: x['created_at'], reverse=True)
    expected_sorted_findings = [Finding(**finding) for finding in expected_sorted_findings]

    # 4 findings should be returned and the next page token should be None
    # expected_sorted_findings[1:] because the first finding is ignored
    expected_response = {'findings': expected_sorted_findings[1:],
                         'next_page_key': None}

    # Act
    event = copy.deepcopy(GET_OPEN_NOT_IGNORED_HIGH_SEVERITY_FINDINGS_EVENT)
    event['queryStringParameters']['page_limit'] = 5
    event['queryStringParameters']['next_page_key'] = None
    response = handler(event, {})

    # Assert
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body == expected_response


@responses.activate
def test_get_all_findings__with_scrolling(mocker, mocked_tables, env_variables):
    """
    A request to get the findings with a limit of 3 findings, the DB contains total of 5 findings.
    We should get the first 3 findings and the next page token should be the last finding is.
    With the next page token we should get the last 2 findings and the next page token should be None
    Setup:
        1) insert 5 findings to MongoDB
        4) Mock get_api_url_from_ssm function
        5) Initialize the MongoDataApiMock class
    Test:
        1) Call 'get_findings' handler to retrieve the findings with a limit of 3 and next_page_key = None
        2) The event that is sent is GET_OPEN_HIGH_SEVERITY_FINDINGS_EVENT
    Assert:
        1) Verify that the HTTP response status code is 200
        2) Check that the 3 first findings were actually returned
        3) Verify that the next page token is the last finding id
    Test:
        1) Call 'get_findings' handler to retrieve the findings with a limit of 3
        and next_page_key of the previous response
        2) The event that is sent is GET_OPEN_HIGH_SEVERITY_FINDINGS_EVENT
    Assert:
        1) Verify that the HTTP response status code is 200
        2) Check that the 2 last findings were actually returned
        3) Verify that the next_page_key in the response body is None
    """
    # Mock the get_api_url_from_ssm function
    mocked_base_path = mock_get_ssm_param(mocker)

    # Initialize the mocked data api class and mock the find request
    mocked_data_api = MongoDataApiMock(mocked_base_path)

    # Insert some mock data
    tenant_id = GET_OPEN_NOT_IGNORED_HIGH_SEVERITY_FINDINGS_EVENT['requestContext']['authorizer']['tenant_id']
    findings = [
        build_finding_dict(finding_id="123", tenant_id=tenant_id,
                           fingerprint="fingerprint1",
                           with_specs=True, issue_severity='HIGH',
                           created_at="2023-03-26T06:09:03.063186"),
        build_finding_dict(finding_id="234", tenant_id=tenant_id,
                           fingerprint="fingerprint2",
                           with_specs=True, issue_severity='HIGH',
                           created_at="2023-03-28T06:09:03.063186"),
        build_finding_dict(finding_id="456", tenant_id=tenant_id,
                           fingerprint="fingerprint3",
                           with_specs=True, issue_severity='HIGH',
                           created_at="2023-03-25T06:09:03.063186"),
        build_finding_dict(finding_id="458", tenant_id=tenant_id,
                           fingerprint="fingerprint4",
                           with_specs=True, issue_severity='HIGH',
                           created_at="2023-03-24T06:09:03.063186"),
        build_finding_dict(finding_id="784", tenant_id=tenant_id,
                           fingerprint="fingerprint5",
                           with_specs=True, issue_severity='HIGH',
                           created_at="2023-02-28T06:09:03.063186"),
    ]
    mocked_data_api.db.findings.insert_many(findings)
    # sort the findings by created_at
    expected_sorted_findings = sorted(findings, key=lambda x: x['created_at'], reverse=True)
    expected_sorted_findings = [Finding(**finding) for finding in expected_sorted_findings]

    # The first 3 findings should be returned and the next page token should be the last id
    # expected_sorted_findings[:3] is the first 3 findings
    expected_response = {'findings': expected_sorted_findings[:3],
                         'next_page_key': 'NDU2IzIwMjMtMDMtMjVUMDY6MDk6MDMuMDYzMTg2'}

    # Prepare the event
    event = copy.deepcopy(GET_OPEN_NOT_IGNORED_HIGH_SEVERITY_FINDINGS_EVENT)
    event['queryStringParameters']['page_limit'] = 3
    event['queryStringParameters']['sort_by'] = 'created_at'
    event['queryStringParameters']['sort_desc'] = True

    # Act
    response = handler(event, {})

    # Assert
    body = json.loads(response['body'])
    assert body == expected_response
    assert response['statusCode'] == 200

    last_id, last_created_at = decode_next_page_key(body['next_page_key'])
    # Assert that the last id is the last id in the mocked findings
    assert last_id == body['findings'][2]['id']

    # ----- Get the next page of findings (the last 2 findings -----
    event['queryStringParameters']['next_page_key'] = body['next_page_key']

    # Act
    response = handler(event, {})

    # Assert
    body = json.loads(response['body'])
    # expected_sorted_findings[3:] should be the last 2 findings in the list (total of 5 findings)
    expected_response = {'findings': expected_sorted_findings[3:],
                         'next_page_key': None}
    assert body == expected_response


@responses.activate
def test_get_all_findings__with_scrolling_sorted_asc(mocker, mocked_tables, env_variables):
    """
    A request to get the findings with a limit of 3 findings, the DB contains total of 5 findings.
    We should get the first 3 findings and the next page token should be the last finding is.
    With the next page token we should get the last 2 findings and the next page token should be None
    Setup:
        1) insert 5 findings to MongoDB
        2) Mock ignore rules table
        3) Insert 1 ignore rules to ignore rules table for the first finding
        4) Mock get_api_url_from_ssm function
        5) Initialize the MongoDataApiMock class
    Test:
        1) Call 'get_findings' handler to retrieve the findings with a limit of 3 and next_page_key = None
        2) The event that is sent is GET_OPEN_HIGH_SEVERITY_FINDINGS_EVENT with the following query params:
            a) page_limit = 3
            b) sort_by = 'created_at'
            c) sort_desc = False
            d) next_page_key = None
    Assert:
        1) Verify that the HTTP response status code is 200
        2) Check that the 3 findings were actually returned sorted by created_at asc
        3) Verify that the next page token is the last finding id
    Test:
        1) Call 'get_findings' handler to retrieve the findings with a limit of 3 and next_page_key
         of the previous response
    Assert:
        1) Verify that the HTTP response status code is 200
        2) Check that the 2 last findings were actually returned
        3) Verify that the next_page_key in the response body is None
    """
    # Assign
    # Mock the get_api_url_from_ssm function
    mocked_base_path = mock_get_ssm_param(mocker)

    # Initialize the mocked data api class and mock the find request
    mocked_data_api = MongoDataApiMock(mocked_base_path)

    # Insert some mock data
    tenant_id = GET_OPEN_NOT_IGNORED_HIGH_SEVERITY_FINDINGS_EVENT['requestContext']['authorizer']['tenant_id']
    findings = [
        build_finding_dict(finding_id="123", tenant_id=tenant_id,
                           with_specs=True, issue_severity='HIGH',
                           created_at="2023-03-26T06:09:03.063186"),
        build_finding_dict(finding_id="234", tenant_id=tenant_id,
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
    mocked_data_api.db.findings.insert_many(findings)
    # sort the findings by created_at
    expected_sorted_asc_findings = sorted(findings, key=lambda x: x['created_at'], reverse=False)
    expected_sorted_asc_findings = [Finding(**finding) for finding in expected_sorted_asc_findings]

    # The first 3 findings should be returned and the next page token should be the last id
    expected_response = {'findings': expected_sorted_asc_findings[:3],
                         'next_page_key': 'NDU2IzIwMjMtMDMtMjVUMDY6MDk6MDMuMDYzMTg2'}
    # Act
    event = copy.deepcopy(GET_OPEN_NOT_IGNORED_HIGH_SEVERITY_FINDINGS_EVENT)
    event['queryStringParameters']['page_limit'] = 3
    event['queryStringParameters']['sort_by'] = 'created_at'
    event['queryStringParameters']['sort_desc'] = False
    event['queryStringParameters']['next_page_key'] = None
    response = handler(event, {})

    # Assert
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body == expected_response
    last_id, last_created_at = decode_next_page_key(body['next_page_key'])
    # Assert that the last id is the last id in the mocked findings
    assert last_id == body['findings'][2]['id']

    # ----- Get the next page of findings (the last 2 findings -----
    event['queryStringParameters']['next_page_key'] = body['next_page_key']

    # Act
    response = handler(event, {})

    # Assert
    body = json.loads(response['body'])
    expected_response = {'findings': expected_sorted_asc_findings[3:],
                         'next_page_key': None}
    assert body == expected_response


@responses.activate
def test_get_all_findings__as_csv(mocker, mocked_tables, s3_client, env_variables):
    """
    This test a request to get the findings as a link to a S3 csv file.
    Setup:
        1) create S3 bucket and make sure it's empty
        2) Mock get_api_url_from_ssm function
        3) Initialize the MongoDataApiMock class
        4) insert 3 findings to MongoDB
    Test:
        1) Call 'get_findings' handler to retrieve the findings with a limit of 3 and next_page_key = None
        2) The event that is sent is GET_OPEN_HIGH_SEVERITY_FINDINGS_EVENT_AS_CSV

    Assert:
        1) Verify that S3 bucket (S3_FINDINGS_CSV_BUCKET_NAME) has 1 file
        2) Check that we got a s3 url in the response
        3) Verify that the HTTP response status code is 200
    """
    s3_client.create_bucket(Bucket=S3_FINDINGS_CSV_BUCKET_NAME)
    # check that the bucket is empty
    objects = s3_client.list_objects(Bucket=S3_FINDINGS_CSV_BUCKET_NAME)
    files = objects.get("Contents")
    assert files is None

    # Mock the get_api_url_from_ssm function
    mocked_base_path = mock_get_ssm_param(mocker)

    # Initialize the mocked data api class and mock the find request
    mocked_data_api = MongoDataApiMock(mocked_base_path)

    # Insert some mock data
    tenant_id = GET_OPEN_NOT_IGNORED_HIGH_SEVERITY_FINDINGS_EVENT_AS_CSV['requestContext']['authorizer']['tenant_id']
    findings = [
        build_finding_dict(finding_id="123", tenant_id=tenant_id,
                           fingerprint="fingerprint1",
                           with_specs=True, issue_severity='HIGH',
                           created_at="2023-03-26T06:09:03.063186"),
        build_finding_dict(finding_id="234", tenant_id=tenant_id,
                           fingerprint="fingerprint2",
                           with_specs=True, issue_severity='HIGH',
                           created_at="2023-03-28T06:09:03.063186"),
        build_finding_dict(finding_id="456", tenant_id=tenant_id,
                           fingerprint="fingerprint3",
                           with_specs=True, issue_severity='HIGH',
                           created_at="2023-03-25T06:09:03.063186"),
    ]
    mocked_data_api.db.findings.insert_many(findings)

    # Prepare the event
    event = GET_OPEN_NOT_IGNORED_HIGH_SEVERITY_FINDINGS_EVENT_AS_CSV
    event['queryStringParameters']['page_limit'] = 3
    event['queryStringParameters']['sort_by'] = 'created_at'
    event['queryStringParameters']['sort_desc'] = True

    # Act
    response = handler(event, {})

    objects = s3_client.list_objects(Bucket=S3_FINDINGS_CSV_BUCKET_NAME)
    body = json.loads(response['body'])
    # Assert
    # check that a file was created in the bucket
    assert len(objects["Contents"]) == 1
    assert body['s3_url']
    assert response['statusCode'] == 200


@responses.activate
def test_get_findings__with_team_filter__filter_findings_by_team(mocker, mocked_tables, env_variables):
    """
    The lambda should return the findings tagged with team1
    Setup:
        1) insert 5 findings to MongoDB, 3 of which are tagged with team1
        2) Mock get_api_url_from_ssm function
        3) Initialize the MongoDataApiMock class
    Test:
        1) Call 'get_findings' handler with team filter
    Assert:
        1) response status code == 200
        2) check that only 3 findings with team1 tag were returned
        3) there is no next page key
    """
    # Assign
    tenant_id = GET_TEAM_FINDINGS_EVENT['requestContext']['authorizer']['tenant_id']
    findings = [
        build_finding_dict(finding_id="123", tenant_id=tenant_id,
                           fingerprint="fingerprint1",
                           with_specs=True, issue_severity='HIGH',
                           created_at="2023-07-28T06:09:03.063186",
                           tags=[Tag(name='team', value='team1')]),
        build_finding_dict(finding_id="234", tenant_id=tenant_id,
                           fingerprint="fingerprint2",
                           with_specs=True, issue_severity='HIGH',
                           created_at="2023-07-26T05:09:03.063186",
                           tags=[Tag(name='team', value='team1')]),
        build_finding_dict(finding_id="456", tenant_id=tenant_id,
                           fingerprint="fingerprint3",
                           with_specs=True, issue_severity='HIGH',
                           created_at="2023-07-25T04:09:03.063186",
                           tags=[Tag(name='team', value='team1')]),
        build_finding_dict(finding_id="458", tenant_id=tenant_id,
                           fingerprint="fingerprint4",
                           with_specs=True, issue_severity='HIGH',
                           created_at="2023-03-24T06:09:03.063186",
                           tags=[Tag(name='team', value='team2')]),
        build_finding_dict(finding_id="784", tenant_id=tenant_id,
                           fingerprint="fingerprint5",
                           with_specs=True, issue_severity='HIGH',
                           created_at="2023-02-28T06:09:03.063186",
                           tags=[Tag(name='team', value='team2')]),
        build_finding_dict(finding_id="785", tenant_id=tenant_id,
                           fingerprint="fingerprint6",
                           with_specs=True, issue_severity='HIGH',
                           created_at="2023-02-28T06:09:03.063186",
                           tags=[]),
    ]

    mocked_base_path = mock_get_ssm_param(mocker)
    mocked_data_api = MongoDataApiMock(mocked_base_path)

    mocked_data_api.db.findings.insert_many(findings)

    expected_response = {'findings': [Finding(**finding) for finding in findings[:3]],
                         'next_page_key': None}
    # Only the first 3 findings are tagged with 'team1'

    # Act
    event = copy.deepcopy(GET_TEAM_FINDINGS_EVENT)
    event['queryStringParameters']['page_limit'] = 5
    event['queryStringParameters']['next_page_key'] = None
    response = handler(event, {})

    # Assert
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body == expected_response


@responses.activate
def test_get_findings__filter_by_plan_item(mocker, mocked_tables, env_variables):
    """
    The lambda should return findings related to the requested plan item
    Setup:
        1) insert 5 findings to MongoDB 2 of which are related to the requested plan item
        4) Mock get_api_url_from_ssm function
        5) Initialize the MongoDataApiMock class
    Test:
        1) Call 'get_findings' handler

    Assert:
        1) response status code == 200
        2) check that only 2 findings related to the requested plan item were returned
        3) there is no next page key
    """
    # Assign
    tenant_id = str(uuid.uuid4())
    event = get_handler_event(
        token="token",
        tenant_id=tenant_id,
        query_string_parameters={
            "filters": '{"resolution":"OPEN","backlog":true,"plan_item":["plan_item1"]}',
            "sort": "created_at",
            "sort_desc": "true",
            "next_page_key": None,
        },
        permissions=[Read.FINDINGS],
    )
    findings = [build_finding_dict(finding_id=f"finding_{i}",
                                   fingerprint=f"fingerprint_{i}",
                                   with_specs=True,
                                   backlog=True,
                                   tenant_id=tenant_id)
                for i in range(3)]
    plan_item_findings = [
        build_finding_dict(finding_id="finding_3", tenant_id=tenant_id,
                           fingerprint="fingerprint_3",
                           with_specs=True,
                           backlog=True,
                           plan_items=["plan_item1", "plan_item2"]),
        build_finding_dict(finding_id="finding_4", tenant_id=tenant_id,
                           fingerprint="fingerprint_4",
                           with_specs=True,
                           backlog=True,
                           plan_items=["plan_item1"])
    ]

    # Mock the get_api_url_from_ssm function
    mocked_base_path = mock_get_ssm_param(mocker)

    # Initialize the mocked data api class and mock the find request
    mocked_data_api = MongoDataApiMock(mocked_base_path)

    # Insert some mock data
    mocked_data_api.db.findings.insert_many(findings + plan_item_findings)

    # sort the findings by created_at
    expected_findings = sorted(plan_item_findings, key=lambda x: x['created_at'], reverse=True)
    expected_findings = [Finding(**finding).dict() for finding in expected_findings]

    expected_response = {'findings': expected_findings, 'next_page_key': None}

    # Act
    response = handler(event, {})

    # Assert
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert len(body['findings']) == 2
    assert body == expected_response

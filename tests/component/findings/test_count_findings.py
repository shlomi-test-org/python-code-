import copy
import json

import pytest
import responses
from jit_utils.models.findings.entities import Resolution

from src.handlers.findings.count_findings import handler
from tests.component.findings.mock_events import (
    COUNT_NO_FILTERS_FINDINGS_GROUP_BY_CONTROL_NAME_EVENT, COUNT_OPEN_NOT_IGNORED_HIGH_SEVERITY_EVENT,
    COUNT_FIXED_NOT_IGNORED_HIGH_SEVERITY_FINDINGS_EVENT, COUNT_OPEN_NOT_IGNORED_FINDINGS_GROUP_BY_CONTROL_NAME_EVENT,
    COUNT_FINDINGS_NO_FILTERS_EVENT, COUNT_FINDINGS_ALL_RESOLUTION_FILTERS_EVENT, COUNT_PLAN_ITEM_INDEX_EVENT,
    COUNT_PLAN_ITEM_INDEX_GROUP_BY_PLAN_ITEM_EVENT
)
from tests.component.utils.mock_get_ssm_param import mock_get_ssm_param
from tests.component.utils.mock_mongo_data_api import MongoDataApiMock
from tests.component.utils.mock_mongo_driver import mock_mongo_driver
from tests.fixtures import build_finding_dict


def test_no_jwt_token_count_open_findings_high_severity(mocker,
                                                        env_variables):
    """
    This test verifies that the handler returns the correct count depending on the filters passed
    No jwt token is passed in the event, so the MongoDriver should be used
    Setup:
        1) Mock mongo driver
        2) Insert findings to the mocked collection

    Test:
        1) Call the handler once

    Assert:
        1) The handler returns the correct count of 3 findings which apply to the filters
    """
    # Assign
    # Mock mongo driver
    findings_collection = mock_mongo_driver(mocker).findings

    tenant_id = COUNT_OPEN_NOT_IGNORED_HIGH_SEVERITY_EVENT['requestContext']['authorizer']['tenant_id']
    # Insert some mock data
    findings_collection.insert_many([
        build_finding_dict(tenant_id=tenant_id, with_specs=True, issue_severity='HIGH'),
        build_finding_dict(tenant_id=tenant_id, with_specs=True, issue_severity='HIGH'),
        build_finding_dict(tenant_id=tenant_id, with_specs=True, issue_severity='HIGH'),
        build_finding_dict(tenant_id=tenant_id, with_specs=True, issue_severity='LOW'),
        build_finding_dict(tenant_id=tenant_id, with_specs=True, resolution=Resolution.FIXED),
    ])

    expected_response = {'count': 3}
    # Act
    event = copy.deepcopy(COUNT_OPEN_NOT_IGNORED_HIGH_SEVERITY_EVENT)
    event['requestContext']['authorizer'].pop('token', None)  # remove the jwt token
    response = handler(event, {})

    # Assert
    assert response['statusCode'] == 200
    assert response['body'] == json.dumps(expected_response)


@responses.activate
def test_count_open_findings_high_severity(mocker,
                                           env_variables):
    """
    This test verifies that the handler returns the correct count depending on the filters passed
    jwt token is passed in the event, so the MongoDataApi should be used
    Setup:
        1) Mock mongo driver
        2) Mock ignore rules table
        3) Insert findings to the mocked findings_collection

    Test:
        1) Call the handler once

    Assert:
        1) The handler returns the correct count of 3 findings which apply to the filters
    """
    # Assign
    # Mock the get_api_url_from_ssm function
    mocked_base_path = mock_get_ssm_param(mocker)

    # Initialize the mocked data api class and mock the find request
    mocked_data_api = MongoDataApiMock(mocked_base_path)
    tenant_id = COUNT_OPEN_NOT_IGNORED_HIGH_SEVERITY_EVENT['requestContext']['authorizer']['tenant_id']
    # Insert some mock data
    mocked_data_api.db.findings.insert_many([
        build_finding_dict(tenant_id=tenant_id, with_specs=True, issue_severity='HIGH'),
        build_finding_dict(tenant_id=tenant_id, with_specs=True, issue_severity='HIGH'),
        build_finding_dict(tenant_id=tenant_id, with_specs=True, issue_severity='HIGH'),
        build_finding_dict(tenant_id=tenant_id, with_specs=True, issue_severity='LOW'),
        build_finding_dict(tenant_id=tenant_id, with_specs=True, resolution=Resolution.FIXED),
    ])

    expected_response = {'count': 3}
    # Act
    response = handler(COUNT_OPEN_NOT_IGNORED_HIGH_SEVERITY_EVENT, {})

    # Assert
    assert response['statusCode'] == 200
    assert response['body'] == json.dumps(expected_response)


@responses.activate
def test_count_all_findings(mocker,
                            mocked_tables,
                            env_variables):
    """
    This test verifies that the handler returns the correct count of findings
    jwt token is passed in the event, so the MongoDataApi should be used
    Setup:
        1) Mock mongo driver
        2) Mock ignore rules table
        3) Insert findings to the mocked findings_collection

    Test:
        1) Call the handler once with no filters
        2) Call the handler once with no filters, with resolution : [OPEN, IGNORED, FIXED]

    Assert:
        1) The handler returns the correct count of 3 findings which apply to the filters
    """
    # Assign
    _, _ = mocked_tables

    # Mock the get_api_url_from_ssm function
    mocked_base_path = mock_get_ssm_param(mocker)

    # Initialize the mocked data api class and mock the find request
    mocked_data_api = MongoDataApiMock(mocked_base_path)
    tenant_id = COUNT_FINDINGS_NO_FILTERS_EVENT['requestContext']['authorizer']['tenant_id']
    # Insert some mock data
    findings = [
        build_finding_dict(tenant_id=tenant_id, with_specs=True, resolution=Resolution.OPEN, ignored=True,
                           ignore_rules_ids=["some_ignore_rule_id"]),
        build_finding_dict(tenant_id=tenant_id, with_specs=True, resolution=Resolution.OPEN, ignored=True,
                           ignore_rules_ids=["some_ignore_rule_id2"]),
        build_finding_dict(tenant_id=tenant_id, with_specs=True, resolution=Resolution.OPEN),
        build_finding_dict(tenant_id=tenant_id, with_specs=True, resolution=Resolution.OPEN),
        build_finding_dict(tenant_id=tenant_id, with_specs=True, resolution=Resolution.FIXED),
    ]
    mocked_data_api.db.findings.insert_many(findings)

    expected_response = {'count': 5}

    # Act - call the handler twice, once with no filters and once with all supported resolutions filter
    response_no_filters = handler(COUNT_FINDINGS_NO_FILTERS_EVENT, {})
    response_all_supported_resolutions_filter = handler(COUNT_FINDINGS_ALL_RESOLUTION_FILTERS_EVENT, {})

    # Assert
    assert response_no_filters['statusCode'] == 200
    assert response_no_filters['body'] == json.dumps(
        expected_response)

    assert response_all_supported_resolutions_filter['statusCode'] == 200
    assert response_all_supported_resolutions_filter['body'] == json.dumps(expected_response)


@responses.activate
def test_count_fixed_findings_high_severity(mocker,
                                            env_variables):
    """
    This test verifies that the handler returns the correct count depending on the filters passed.
    The handler that is being tested only queries the DB, so we don't need to mock ignore rules
    Setup:
        1) Mock mongo driver
        3) Insert findings to the mocked findings_collection

    Test:
        1) Call the handler once

    Assert:
        1) The handler returns the correct count of 2 findings which apply to the filters

    """
    # Assign
    # Mock the get_api_url_from_ssm function
    mocked_base_path = mock_get_ssm_param(mocker)

    # Initialize the mocked data api class and mock the find request
    mocked_data_api = MongoDataApiMock(mocked_base_path)
    tenant_id = COUNT_FIXED_NOT_IGNORED_HIGH_SEVERITY_FINDINGS_EVENT['requestContext']['authorizer']['tenant_id']
    # Insert some mock data
    mocked_data_api.db.findings.insert_many([
        build_finding_dict(tenant_id=tenant_id, with_specs=True, issue_severity='HIGH'),
        build_finding_dict(tenant_id=tenant_id, with_specs=True, issue_severity='HIGH'),
        build_finding_dict(tenant_id=tenant_id, with_specs=True, issue_severity='LOW', resolution=Resolution.FIXED),
        build_finding_dict(tenant_id=tenant_id, with_specs=True, issue_severity='HIGH', resolution=Resolution.FIXED),
        build_finding_dict(tenant_id=tenant_id, with_specs=True, issue_severity='HIGH', resolution=Resolution.FIXED),
    ])

    expected_response = {'count': 2}
    # Act
    response = handler(COUNT_FIXED_NOT_IGNORED_HIGH_SEVERITY_FINDINGS_EVENT, {})

    # Assert
    assert response['statusCode'] == 200
    assert response['body'] == json.dumps(expected_response)


@responses.activate
def test_count_findings_grouped_by_control_name(mocker,
                                                env_variables):
    """
    This test verifies that the handler returns the correct count depending on the filters passed.
    The handler that is being tested only queries the DB, so we don't need to mock ignore rules
    Setup:
        1) Mock mongo driver
        2) Insert findings to the mocked findings_collection

    Test:
        1) Call the handler once

    Assert:
        1) The handler returns the correct count of 2 findings which apply to the filters

    """
    # Assign
    # Mock the get_api_url_from_ssm function
    mocked_base_path = mock_get_ssm_param(mocker)

    # Initialize the mocked data api class and mock the find request
    mocked_data_api = MongoDataApiMock(mocked_base_path)
    tenant_id = COUNT_NO_FILTERS_FINDINGS_GROUP_BY_CONTROL_NAME_EVENT['requestContext']['authorizer']['tenant_id']
    # Insert some mock data
    mocked_data_api.db.findings.insert_many([
        build_finding_dict(tenant_id=tenant_id, with_specs=True, control_name='control1'),
        build_finding_dict(tenant_id=tenant_id, with_specs=True, control_name='control1'),
        build_finding_dict(tenant_id=tenant_id, with_specs=True, control_name='control1'),
        build_finding_dict(tenant_id=tenant_id, with_specs=True, control_name='control2'),
        build_finding_dict(tenant_id=tenant_id, with_specs=True, control_name='control2'),
    ])

    expected_response = [{'key': 'control1', 'count': 3}, {'key': 'control2', 'count': 2}]
    # Act
    response = handler(COUNT_NO_FILTERS_FINDINGS_GROUP_BY_CONTROL_NAME_EVENT, {})

    # Assert
    assert response['statusCode'] == 200
    assert response['body'] == json.dumps(expected_response)


@responses.activate
def test_count_open_findings_grouped_by_control_name(mocker,
                                                     env_variables):
    """
    This test verifies that the handler returns the correct count depending on the filters passed.
    The handler that is being tested only queries the DB, so we don't need to mock ignore rules
    Setup:
        1) Mock mongo driver
        2) Insert findings to the mocked findings_collection

    Test:
        1) Call the handler once

    Assert:
        1) The handler returns the correct count of 2 findings which apply to the filters

    """
    # Assign
    # Mock the get_api_url_from_ssm function
    mocked_base_path = mock_get_ssm_param(mocker)

    # Initialize the mocked data api class and mock the find request
    mocked_data_api = MongoDataApiMock(mocked_base_path)
    tenant_id = COUNT_OPEN_NOT_IGNORED_FINDINGS_GROUP_BY_CONTROL_NAME_EVENT['requestContext']['authorizer']['tenant_id']
    # Insert some mock data
    mocked_data_api.db.findings.insert_many([
        build_finding_dict(tenant_id=tenant_id, with_specs=True, control_name='control1'),
        build_finding_dict(tenant_id=tenant_id, with_specs=True, control_name='control1'),
        build_finding_dict(tenant_id=tenant_id, with_specs=True, control_name='control1'),
        build_finding_dict(tenant_id=tenant_id, with_specs=True, control_name='control2'),
        build_finding_dict(tenant_id=tenant_id, with_specs=True, control_name='control2'),
        build_finding_dict(tenant_id=tenant_id, with_specs=True, control_name='control2', resolution=Resolution.FIXED),
    ])

    expected_response = [{'key': 'control1', 'count': 3}, {'key': 'control2', 'count': 2}]
    # Act
    response = handler(COUNT_OPEN_NOT_IGNORED_FINDINGS_GROUP_BY_CONTROL_NAME_EVENT, {})

    # Assert
    assert response['statusCode'] == 200
    # we will check if the response is the same, but the order of the items is not important
    assert sorted(json.loads(response['body']),
                  key=lambda x: x['key']) == sorted(expected_response, key=lambda x: x['key'])


@responses.activate
def test_count_open_findings_grouped_by_control_name_user_not_have_findings(mocker,
                                                                            env_variables):
    """
    This test verifies that the handler returns the correct count depending on the filters passed.
    The handler that is being tested only queries the DB, so we don't need to mock ignore rules
    Setup:
        1) Mock mongo driver

    Test:
        1) Call the handler once

    Assert:
        1) The handler returns the correct empty list

    """
    # Assign
    # Mock the get_api_url_from_ssm function
    mocked_base_path = mock_get_ssm_param(mocker)

    # Initialize the mocked data api class and mock the find request
    MongoDataApiMock(mocked_base_path)

    # Act
    response = handler(COUNT_OPEN_NOT_IGNORED_FINDINGS_GROUP_BY_CONTROL_NAME_EVENT, {})

    # Assert
    assert response['statusCode'] == 200
    assert response['body'] == json.dumps([])


@responses.activate
@pytest.mark.parametrize("event, expected_response", [
    [COUNT_PLAN_ITEM_INDEX_EVENT, {'count': 3}],
    [
        COUNT_PLAN_ITEM_INDEX_GROUP_BY_PLAN_ITEM_EVENT,
        [{"key": "plan_item1", "count": 3}, {"key": "plan_item2", "count": 2}],
    ],
])
def test_count_findings__plan_item_index(mocker, env_variables, event, expected_response):
    """
    This test verifies that the handler returns the correct count when it uses the plan-item-index.
    Setup:
        1) Mock mongo driver
        2) Insert findings to the mocked findings_collection

    Test:
        1) Call the handler once

    Assert:
        1) The handler returns the correct count of 2 findings which apply to the filters

    """
    # Assign
    # Mock the get_api_url_from_ssm function
    mocked_base_path = mock_get_ssm_param(mocker)

    # Initialize the mocked data api class and mock the find request
    mocked_data_api = MongoDataApiMock(mocked_base_path)
    tenant_id = event['requestContext']['authorizer']['tenant_id']
    # Insert some mock data
    mocked_data_api.db.findings.insert_many([
        build_finding_dict(tenant_id=tenant_id, backlog=True, plan_items=["plan_item1"], asset_id="asset_id1"),
        build_finding_dict(tenant_id=tenant_id, backlog=True, plan_items=["plan_item2"], asset_id="asset_id1"),
        build_finding_dict(tenant_id=tenant_id, backlog=True, plan_items=["plan_item1"], asset_id="asset_id2"),
        build_finding_dict(
            tenant_id=tenant_id, backlog=True, plan_items=["plan_item1", "plan_item2"], asset_id="asset_id2"
        ),
    ])
    # Act
    response = handler(event, {})

    # Assert
    assert response['statusCode'] == 200
    assert response['body'] == json.dumps(expected_response)

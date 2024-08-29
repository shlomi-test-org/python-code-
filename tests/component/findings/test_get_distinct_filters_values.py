import json

import responses
from jit_utils.models.findings.entities import Resolution
from jit_utils.utils.permissions import Read

from src.handlers.findings.get_distinct_filters_values import handler

from jit_utils.models.tags.entities import Tag
from src.lib.models.finding_model import UiResolution
from tests.component.utils.get_handler_event import get_handler_event
from tests.component.utils.mock_get_ssm_param import mock_get_ssm_param
from tests.component.utils.mock_mongo_data_api import MongoDataApiMock
from tests.fixtures import build_finding_dict


@responses.activate
def test_get_distinct_filters_values_no_findings_matched(mocker, env_variables):
    """
    Test get distinct filters values for a tenant with no findings matched
    Setup:
        1) Mock mongo data api
        2) Mock ssm param
        2) empty filters dict

    Test:
        1) Call the handler once

    Assert:
        1) Dict of empty list for each the distinct values for location_text, test_name, vulnerability_type
    """
    # Assign
    # Mock the get_api_url_from_ssm function
    mocked_base_path = mock_get_ssm_param(mocker)

    # Initialize the mocked data api class and mock the find request
    mocked_data_api = MongoDataApiMock(mocked_base_path)
    event = get_handler_event(token="token", permissions=[Read.FINDINGS])
    tenant_id_2 = 'tenant_id_2'
    # Insert some mock data
    mocked_data_api.db.findings.insert_many([
        build_finding_dict(tenant_id=tenant_id_2, with_specs=True, issue_severity='HIGH', location_text='location1',
                           test_name='test1', vulnerability_type='code vulnerability', control_name='kics'),

        build_finding_dict(tenant_id=tenant_id_2, with_specs=True, issue_severity='HIGH', location_text='location2',
                           control_name='bandit', vulnerability_type='secret', test_name='test2'),

        build_finding_dict(tenant_id=tenant_id_2, with_specs=True, issue_severity='HIGH', location_text='location3',
                           control_name='kics', vulnerability_type='code vulnerability', test_name='test3'),

        build_finding_dict(tenant_id=tenant_id_2, with_specs=True, issue_severity='LOW', location_text='location1',
                           test_name='test1',
                           control_name='bandit', vulnerability_type='code vulnerability'),

        build_finding_dict(tenant_id=tenant_id_2, with_specs=True, resolution=Resolution.FIXED, test_name='test1',
                           location_text='location1',
                           control_name='bandit', vulnerability_type='code vulnerability'),
    ])
    expected_response = {
        "location_text": [],
        "test_name": [],
        "vulnerability_type": [],
        "control_name": [],
        "plan_item": [],
        "asset_name": [],
        "asset_type": [],
        "plan_layer": [],
        "issue_severity": [],
        "resolution": [UiResolution.OPEN, UiResolution.FIXED],
        'team': [],
        "exposure": [],
        "environment": [],
        "priority_factors": []
    }
    # Act
    response = handler(event, {})

    # Assert
    assert response['statusCode'] == 200
    assert response['body'] == json.dumps(expected_response)


@responses.activate
def test_get_distinct_filters_values(mocker, env_variables):
    """
    Test get distinct filters values
    Setup:
        1) Mock mongo data api
        2) Mock ssm param
        2) empty filters dict

    Test:
        1) Call the handler once

    Assert:
        1) Dict of all the distinct values for location_text, test_name, vulnerability_type
    """
    # Assign
    # Mock the get_api_url_from_ssm function
    mocked_base_path = mock_get_ssm_param(mocker)

    # Initialize the mocked data api class and mock the find request
    mocked_data_api = MongoDataApiMock(mocked_base_path)
    event = get_handler_event(token="token", permissions=[Read.FINDINGS])
    tenant_id = event['requestContext']['authorizer']['tenant_id']
    # Insert some mock data
    findings = [
        build_finding_dict(tenant_id=tenant_id, with_specs=True, issue_severity='HIGH', location_text='location1',
                           test_name='test1', vulnerability_type='code vulnerability', control_name='kics',
                           plan_items=['item-a', 'item-b']),

        build_finding_dict(tenant_id=tenant_id, with_specs=True, issue_severity='HIGH', location_text='location2',
                           control_name='bandit', vulnerability_type='secret', test_name='test2',
                           plan_items=['item-a', 'item-c'],
                           tags=[Tag(name='team', value='team1')], priority_factors=['Fix Available']),

        build_finding_dict(tenant_id=tenant_id, with_specs=True, issue_severity='HIGH', location_text='location1',
                           control_name='kics', vulnerability_type='code vulnerability', test_name='test3',
                           tags=[Tag(name='team', value='team1')], priority_factors=['Fix Available']),

        build_finding_dict(tenant_id=tenant_id, with_specs=True, issue_severity='LOW', location_text='location1',
                           test_name='test1', resolution=Resolution.OPEN,
                           control_name='bandit', vulnerability_type='code vulnerability',
                           tags=[Tag(name='team', value='team2')], priority_factors=['Externally Accessible']),

        build_finding_dict(tenant_id=tenant_id, with_specs=True, resolution=Resolution.FIXED, test_name='test1',
                           control_name='bandit', vulnerability_type='code vulnerability'),
        build_finding_dict(tenant_id=tenant_id, with_specs=True, issue_severity='HIGH', location_text='location1',
                           test_name='test1', vulnerability_type='code vulnerability', control_name='kics',
                           resolution=Resolution.INACTIVE),
        build_finding_dict(tenant_id=tenant_id, with_specs=True, issue_severity='HIGH', location_text='location1',
                           test_name='test1', vulnerability_type='code vulnerability', control_name='kics',
                           resolution=Resolution.DUP),
    ]
    findings[4]['location_text'] = None
    mocked_data_api.db.findings.insert_many(findings)
    expected_response = {
        "location_text": ["location1", "location2"],
        "test_name": ["test1", "test2", "test3"],
        "vulnerability_type": ["code vulnerability", "secret"],
        "control_name": ["kics", "bandit"],
        "plan_item": ['item-a', 'item-b', 'item-c', "dummy-plan-item"],
        "asset_name": ["repo-name"],
        "asset_type": ["repo"],
        "plan_layer": ["code"],
        "issue_severity": ["HIGH", "LOW"],
        "resolution": [UiResolution.OPEN, UiResolution.FIXED],
        "team": ["team1", "team2"],
        "exposure": [],
        "environment": [],
        "priority_factors": ['Fix Available', 'Externally Accessible']
    }
    # Act
    response = handler(event, {})

    # Assert
    assert response['statusCode'] == 200
    assert response['body'] == json.dumps(expected_response)


@responses.activate
def test_get_distinct_filters_values_no_findings_data_api(mocker, env_variables):
    """
    Test get distinct filters values
    Setup:
        1) Mock mongo data api
        2) Mock ssm param
        2) empty filters dict

    Test:
        1) Call the handler once

    Assert:
        1) Dict of all the empty distinct values for location_text, test_name, vulnerability_type
    """
    # Assign
    # Mock the get_api_url_from_ssm function
    mock_get_ssm_param(mocker)

    # Mock the data api return value because data api and mongo client return different values
    responses.add(responses.POST, 'https://api.dummy.mongo/action/aggregate',
                  json={})
    # Initialize the mocked data api class and mock the find request
    event = get_handler_event(token="token", permissions=[Read.FINDINGS])
    expected_response = {
        "location_text": [],
        "test_name": [],
        "vulnerability_type": [],
        "control_name": [],
        "plan_item": [],
        "asset_name": [],
        "asset_type": [],
        "plan_layer": [],
        "issue_severity": [],
        "resolution": [UiResolution.OPEN, UiResolution.FIXED],
        "team": [],
        "exposure": [],
        "environment": [],
        "priority_factors": []
    }
    # Act
    response = handler(event, {})

    # Assert
    assert response['statusCode'] == 200
    assert response['body'] == json.dumps(expected_response)

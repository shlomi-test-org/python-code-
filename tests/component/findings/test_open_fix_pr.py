import json

import freezegun
import responses
from jit_utils.utils.permissions import Write
from test_utils.aws.mock_eventbridge import mock_eventbridge
from test_utils.mongo.mock_mongo_data_api import MongoDataApiMock

from src.handlers.findings.open_fix_pr import handler
from tests.component.utils.get_handler_event import get_handler_event
from tests.component.utils.mock_clients.mock_installations import mock_get_installations_by_vendor_api
from tests.component.utils.mock_get_ssm_param import mock_get_ssm_param
from tests.fixtures import build_finding_dict


def setup_test(mocker):
    # Mock the get_api_url_from_ssm function
    mocked_base_path = mock_get_ssm_param(mocker)

    # Initialize the mocked data api class and mock the find request
    mocked_data_api = MongoDataApiMock(mocked_base_path)

    # Insert some mock data
    finding = build_finding_dict()
    findings_collection = mocked_data_api.db.findings
    findings_collection.insert_one(finding)

    return finding, findings_collection


@responses.activate
@freezegun.freeze_time("2024-06-26T11:23:26Z")
def test_open_fix_pr__happy_flow(mocker, env_variables):
    """
    Setup: Mock SSM parameter and MongoDB, insert a finding.
    Test: Call the handler with valid data.
    Assert: Check status code and response body.
    """
    # Setup
    finding_in_db, _ = setup_test(mocker)
    mock_get_installations_by_vendor_api(finding_in_db['tenant_id'], 'github')
    event = get_handler_event(
        body={},
        tenant_id=finding_in_db['tenant_id'],
        token='token',
        permissions=[Write.FINDINGS],
        path_parameters={'finding_id': finding_in_db['_id']}
    )

    # Test with mocked EventBridge
    with mock_eventbridge(bus_name='trigger-execution') as get_sent_events:
        response = handler(event, {})

        # Assert
        assert response['statusCode'] == 201
        assert json.loads(response['body']) == {}

        sent_events = get_sent_events()
        assert len(sent_events) == 1
        assert sent_events[0] == {
            'version': '0', 'id': sent_events[0]['id'],
            'detail-type': 'handle-jit-event', 'source': 'finding-service',
            'account': '123456789012', 'time': '2024-06-26T11:23:26Z', 'region': 'us-east-1',
            'resources': [],
            'detail': {
                'tenant_id': finding_in_db['tenant_id'],
                'jit_event_name': 'open_fix_pull_request',
                'jit_event_id': sent_events[0]['detail']['jit_event_id'],
                'asset_id': finding_in_db['asset_id'],
                'workflows': None,
                'centralized_repo_asset_id': 'asset1-id',
                'centralized_repo_asset_name': 'asset1',
                'centralized_repo_files_location': None,
                'ci_workflow_files_path': None,
                'finding_id': str(finding_in_db['_id']),
                'action_id': None,
                'fix_suggestion': {'source': 'control'}, 'app_id': 'app1',
                'installation_id': 'installation1',
                'owner': 'org-name',
                'original_repository': 'repo-name'
            }
        }


@responses.activate
def test_open_fix_pr__finding_not_found(mocker, env_variables):
    """
    Setup: Mock SSM parameter and MongoDB, insert a finding.
    Test: Call the handler with a non-existent finding ID.
    Assert: Check status code and response body for not found error.
    """
    # Setup
    setup_test(mocker)
    event = get_handler_event(
        body={},
        tenant_id='tenant_id',
        token='token',
        permissions=[Write.FINDINGS],
        path_parameters={'finding_id': "NON_EXISTENT_FINDING_ID"}
    )

    # Test
    response = handler(event, {})

    # Assert
    assert response['statusCode'] == 404
    assert json.loads(response['body']) == {
        'error': 'NOT_FOUND',
        'message': 'Could not find finding with id: NON_EXISTENT_FINDING_ID',
    }


@responses.activate
def test_open_fix_pr__unauthorized(mocker, env_variables):
    """
    Setup: Mock SSM parameter and MongoDB, insert a finding.
    Test: Call the handler with missing permissions.
    Assert: Check status code and response body for forbidden error.
    """
    # Setup
    setup_test(mocker)
    event = get_handler_event(
        body={},
        tenant_id='tenant_id',
        token='token',
        permissions=[],
        path_parameters={'finding_id': "some_finding_id"}
    )

    # Test
    response = handler(event, {})

    # Assert
    assert response['statusCode'] == 403
    assert json.loads(response['body']) == {
        'error': 'FORBIDDEN',
        'message': 'User does not have the required permissions',
        'missing_permissions': ['jit.findings.write'],
    }


@responses.activate
def test_open_fix_pr__no_fix_suggestion(mocker, env_variables):
    """
    Setup: Mock SSM parameter and MongoDB, insert a finding without fix_suggestion.
    Test: Call the handler with a finding that has no fix_suggestion.
    Assert: Check status code and response body for bad request error.
    """
    # Setup
    finding_in_db, findings_collection = setup_test(mocker)

    # Update the inserted finding to remove fix_suggestion
    findings_collection.update_one(
        {'_id': finding_in_db['_id']},
        {'$unset': {'fix_suggestion': ""}}
    )

    event = get_handler_event(
        body={},
        tenant_id=finding_in_db['tenant_id'],
        token='token',
        permissions=[Write.FINDINGS],
        path_parameters={'finding_id': finding_in_db['_id']}
    )

    # Test
    response = handler(event, {})

    # Assert
    assert response['statusCode'] == 400
    assert json.loads(response['body']) == {
        'error': 'INVALID_INPUT',
        'message': f'Automatic fix is not available for finding with id: {finding_in_db["_id"]}'
    }


@responses.activate
def test_open_fix_pr__no_installation(mocker, env_variables):
    """
    Setup: Mock SSM parameter and MongoDB, insert a finding.
    Test: Call the handler when no installation is found for the tenant.
    Assert: Check status code and response body for not found error.
    """
    # Setup
    finding_in_db, _ = setup_test(mocker)

    mock_get_installations_by_vendor_api(finding_in_db['tenant_id'], 'github', installations_count=0)

    event = get_handler_event(
        body={},
        tenant_id=finding_in_db['tenant_id'],
        token='token',
        permissions=[Write.FINDINGS],
        path_parameters={'finding_id': finding_in_db['_id']}
    )

    # Test
    response = handler(event, {})

    # Assert
    assert response['statusCode'] == 400
    assert json.loads(response['body']) == {
        'error': 'UNPROCESSABLE_ENTITY',
        'message': (
            f'Could not find SCM installation for tenant_id {finding_in_db["tenant_id"]}, '
            f'vendor {finding_in_db["vendor"]}'
        )
    }

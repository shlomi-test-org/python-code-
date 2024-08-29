import json

import freezegun
import responses
from jit_utils.models.findings.entities import Finding
from jit_utils.utils.permissions import Write
from test_utils.aws.mock_eventbridge import mock_eventbridge
from test_utils.mongo.mock_mongo_data_api import MongoDataApiMock

from src.handlers.findings.update_finding import handler
from tests.component.utils.get_handler_event import get_handler_event
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
@freezegun.freeze_time("2024-06-26T15:55:39")
def test_update_finding__happy_flow(mocker, env_variables):
    """
    Setup: Mock SSM parameter and MongoDB, insert a finding.
    Test: Call the handler with valid update data.
    Assert: Check status code, response body, and database state.
    """
    # Setup
    finding_in_db, findings_collection = setup_test(mocker)
    body = {
        "manual_factors": {
            "added": [{"factor": "Production", "user_explanation": "Because", "source": "finding"}],
            "removed": [{"factor": "Administrator", "source": "finding"}],
        },
        'fix_pr_url': 'https://github.com/myOrg/myRepo/pull/1',
    }
    event = get_handler_event(
        body=body,
        tenant_id=finding_in_db['tenant_id'],
        token='token',
        permissions=[Write.FINDINGS],
        path_parameters={'finding_id': finding_in_db['_id']}
    )

    # Test
    with mock_eventbridge(bus_name="websocket-push") as get_sent_events:
        response = handler(event, {})

        # Assert
        assert response['statusCode'] == 200
        expected_finding = {
            **finding_in_db,
            'manual_factors': body['manual_factors'],
            'fix_pr_url': 'https://github.com/myOrg/myRepo/pull/1',
        }
        assert json.loads(response['body']) == Finding(**expected_finding).dict()
        assert findings_collection.find_one({'_id': finding_in_db['_id']}) == expected_finding

        sent_events = get_sent_events()
        assert sent_events == [{
            'version': '0', 'id': sent_events[0]['id'],
            'detail-type': 'websocket-push',
            'source': 'findings-service',
            'account': '123456789012',
            'time': '2024-06-26T15:55:39Z',
            'region': 'us-east-1',
            'resources': [],
            'detail': {
                'tenant_id': expected_finding['tenant_id'],
                'notification': {
                    'type': 'entity_update',
                    'topic': 'findings',
                    'timestamp': '2024-06-26T15:55:39',
                    'message': {
                        'created': None,
                        'updated': [Finding(**expected_finding).dict()],
                        'deleted': None
                    }
                }
            }
        }]


@responses.activate
def test_update_finding__finding_not_found(mocker, env_variables):
    """
    Setup: Mock SSM parameter and MongoDB, insert a finding.
    Test: Call the handler with a non-existent finding ID.
    Assert: Check status code and response body for not found error.
    """
    # Setup
    finding_in_db, findings_collection = setup_test(mocker)
    body = {
        "manual_factors": {
            "added": [],
            "removed": [],
        }
    }
    event = get_handler_event(
        body=body,
        tenant_id=finding_in_db['tenant_id'],
        token='token',
        permissions=[Write.FINDINGS],
        path_parameters={'finding_id': "DIFFERENT_FINDING_ID"}
    )

    # Test
    response = handler(event, {})

    # Assert
    assert response['statusCode'] == 404
    assert json.loads(response['body']) == {
        'error': 'NOT_FOUND',
        'message': 'Could not find finding with id: DIFFERENT_FINDING_ID'
    }


@responses.activate
def test_update_finding__unauthorized(mocker, env_variables):
    """
    Setup: Mock SSM parameter and MongoDB, insert a finding.
    Test: Call the handler with missing permissions.
    Assert: Check status code and response body for forbidden error.
    """
    # Setup
    setup_test(mocker)
    body = {
        "manual_factors": {
            "added": [],
            "removed": [],
        }
    }
    event = get_handler_event(
        body=body,
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
def test_update_finding__bad_request(mocker, env_variables):
    """
    Setup: Mock SSM parameter and MongoDB, insert a finding.
    Test: Call the handler with an empty body.
    Assert: Check status code and response body for invalid input error.
    """
    # Setup
    finding_in_db, findings_collection = setup_test(mocker)
    event = get_handler_event(
        body={},  # No body
        tenant_id='tenant_id',
        token='token',
        permissions=[Write.FINDINGS],
        path_parameters={'finding_id': "some_finding_id"}
    )

    # Test
    response = handler(event, {})

    # Assert
    assert response['statusCode'] == 400
    assert json.loads(response['body']) == {
        'error': 'INVALID_INPUT',
        'invalid_parameters': {'__root__': 'At least one of the fields must be not None'},
        'message': '__root__: At least one of the fields must be not None',
    }

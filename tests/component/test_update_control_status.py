import json
import uuid
from typing import Dict
from http import HTTPStatus

import pytest
from aws_lambda_powertools.utilities.typing import LambdaContext
from jit_utils.models.execution import Execution

from src.handlers.update_execution import update_control_status_handler
from src.lib.models.execution_models import ExecutionStatus
from tests.component.fixtures import _prepare_execution_to_update


def _get_event(tenant_id: str, event_body: Dict):
    mock_api_gateway_event = {
        "httpMethod": "POST",
        "requestContext": {
            "authorizer": {
                "tenant_id": tenant_id
            }
        },
        "body": json.dumps(event_body)
    }

    return mock_api_gateway_event


@pytest.mark.parametrize('has_findings_state', [None, True, False])
def test_update_control_status_handler(executions_manager, has_findings_state):
    """
    Test the update_control_status_handler function with different has_findings states.

    This test verifies the correct behavior of the update_control_status_handler function when the has_findings
    attribute is set to None, True, or False.

    Setup:
        2) Prepare an execution record with the status RUNNING and the specified has_findings state.
        3) Define the event body with the new execution details
        4) Mock an API Gateway event using the event body.

    Test:
        1) Call the update_control_status_handler function with the mocked event.

    Assert:
        1) Verify that the HTTP response status code is HTTPStatus.OK.
        4) Assert that the updated execution response matches the expected execution response.
        5) If has_findings is None, ensure the has_findings attribute is updated according to the event body.
    """
    tenant_id = str(uuid.uuid4())
    jit_event_id = str(uuid.uuid4())
    execution_id = str(uuid.uuid4())
    execution = _prepare_execution_to_update(
        executions_manager=executions_manager,
        tenant_id=tenant_id,
        jit_event_id=jit_event_id,
        execution_id=execution_id,
        status=ExecutionStatus.RUNNING,
        has_findings=has_findings_state
    )
    event_body = {
        "tenant_id": tenant_id,
        "jit_event_id": jit_event_id,
        "execution_id": execution_id,
        "status": ExecutionStatus.COMPLETED,
        "has_findings": True,
        "job_output": {
            "mime_types": ["text"],
            "languages": ["python"],
            "frameworks": ["ansible"],
            "package_managers": []
        },
        "errors": [],
        "stderr": ""
    }
    mock_api_gateway_event = _get_event(
        tenant_id=tenant_id,
        event_body=event_body
    )

    response = update_control_status_handler(mock_api_gateway_event, LambdaContext())

    assert response['statusCode'] == HTTPStatus.OK

    # Parse the response body into an Execution object
    response_body = json.loads(response['body'])
    updated_execution_response = Execution(**response_body)

    # Create the expected execution dictionary
    expected_execution_data = execution.dict()
    expected_execution_data.update({
        'control_status': event_body['status'],
        'job_output': event_body['job_output'],
        'errors': event_body['errors'],
        'stderr': event_body['stderr'],
    })

    # If has_findings is None, update the expected execution data with the has_findings attribute from the event body
    if has_findings_state is None:
        expected_execution_data['has_findings'] = event_body['has_findings']

    expected_execution_response = Execution(**expected_execution_data)

    # Assert that the updated execution response matches the expected execution
    assert updated_execution_response == expected_execution_response

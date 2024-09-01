import json

import boto3
import pytest
from jit_utils.utils.encoding import MultiTypeJSONEncoder
from test_utils.aws.idempotency import mock_idempotent_decorator

from src.handlers import handle_enrichment_completed
from jit_utils.models.execution import Execution
from src.lib.models.execution_models import ExecutionStatus

MOCK_JOB_OUTPUT = {"mcdonalds": ["wow"]}
MOCK_ADDITIONAL_ATTRIBUTES = {'task_token': '1234'}
EXECUTION_COMPLETED_EVENT_MOCK = {
    "source": "execution-service",
    "resources": [],
    "detail-type": "execution-completed",
    "detail": {
        "tenant_id": "610a53ca-a24c-4697-b2e8-428b182f2735", "execution_id":
            "c96545b9-701c-41c3-a965-53dc87529cc4", "entity_type": "job", "plan_item_slug": "item-mfa-scm",
        "workflow_slug": "workflow-mfa-github-checker", "job_name": "mfa-github-checker", "steps": [{
            "name": "Run MFA checker", "uses":
                "ghcr.io/jitsecurity-controls/control-mfa-github-alpine:latest", "params": {}}], "control_name":
            "Run MFA checker", "control_image":
            "ghcr.io/jitsecurity-controls/control-mfa-github-alpine:latest", "jit_event_name":
            "trigger_scheduled_task", "jit_event_id": "2bd88e45-46e6-4004-bd67-6cc1f9e77bdf", "created_at":
            "2023-01-09T08:13:53.286937", "created_at_ts": 1673252033, "dispatched_at":
            "2023-01-09T08:14:08.424938", "dispatched_at_ts": 1673252048, "registered_at":
            "2023-01-09T08:14:39.668684", "registered_at_ts": 1673252079, "completed_at":
            "2023-01-09T08:15:03.802862", "completed_at_ts": 1673252103, "run_id":
            "ec4ebc2e-6e37-46ea-80d9-83e1c68e3138", "status": "completed", "has_findings": True,
        "job_runner": "jit", "resource_type": "jit", "plan_slug": "jit-plan", "asset_type": "org",
        "asset_name": "chenravidjit", "asset_id": "c563d1e9-46f0-4ae8-8518-9b902b71842a",
        "vendor": "github", "additional_attributes":
            {"owner": "chenravidjit", "installation_id": "25009458", "app_id": "161076"},
        "priority": 3, "upload_findings_status": "completed",
        "control_status": "completed", "control_type": "detection", "execution_timeout":
            "2023-01-09T10:19:39.901976", "job_output": MOCK_JOB_OUTPUT},
}


def mock_sfn(mocker):
    """ Mock the step functions client """
    sf_client_mock = mocker.patch.object(boto3, 'client', return_value=mocker.MagicMock())
    # mock step functions send task success
    sf_client_mock.return_value.send_task_success = mocker.MagicMock()
    # mock step functions send task failure
    sf_client_mock.return_value.send_task_failure = mocker.MagicMock()
    return sf_client_mock


def mock_logger(mocker):
    """ Mock logger """
    return mocker.patch('src.handlers.handle_enrichment_completed.logger', return_value=mocker.MagicMock())


def test_handle_enrichment_completed__no_token(mocker):
    mock_idempotent_decorator(mocker, module_to_reload=handle_enrichment_completed)
    mocked_sfn = mock_sfn(mocker)
    mocked_logger = mock_logger(mocker)

    # Call the handler
    handle_enrichment_completed.handler(EXECUTION_COMPLETED_EVENT_MOCK, None)

    # Assert step functions client was not called
    mocked_sfn.return_value.send_task_failure.assert_not_called()
    mocked_sfn.return_value.send_task_success.assert_not_called()

    # Assert log error was called
    mocked_logger.error.assert_called_once()


def test_handle_enrichment_completed__task_success(mocker):
    """ Test that if the execution has a task token and execution status is completed,
     we call step functions send task success """
    mock_idempotent_decorator(mocker, module_to_reload=handle_enrichment_completed)
    mocked_sfn = mock_sfn(mocker)
    mocked_logger = mock_logger(mocker)

    event = EXECUTION_COMPLETED_EVENT_MOCK.copy()
    event['detail']['additional_attributes'] = MOCK_ADDITIONAL_ATTRIBUTES
    handle_enrichment_completed.handler(EXECUTION_COMPLETED_EVENT_MOCK, None)

    # Assert step functions client was initialized
    mocked_sfn.assert_called()

    # Assert step functions client was called with the correct arguments
    mocked_sfn.return_value.send_task_failure.assert_not_called()
    mocked_sfn.return_value.send_task_success.assert_called_once()
    mocked_sfn.return_value.send_task_success.assert_called_with(
        taskToken=MOCK_ADDITIONAL_ATTRIBUTES['task_token'],
        output=json.dumps(MOCK_JOB_OUTPUT)
    )

    mocked_logger.error.assert_not_called()


@pytest.mark.parametrize("error_body, stderr", [
    ("this has failed, hard.", ""),
    (None, "stderr"),
    (None, "")
])
def test_handle_enrichment_completed__task_failure(mocker, error_body, stderr):
    """ Test that if the execution has a task token and execution status is failed,
     we call step functions send task failure """
    mock_idempotent_decorator(mocker, module_to_reload=handle_enrichment_completed)
    mocked_sfn = mock_sfn(mocker)
    mocked_logger = mock_logger(mocker)

    event = EXECUTION_COMPLETED_EVENT_MOCK.copy()
    event_detail = event['detail']
    event_detail['additional_attributes'] = MOCK_ADDITIONAL_ATTRIBUTES
    event_detail['status'] = ExecutionStatus.FAILED
    event_detail['control_status'] = ExecutionStatus.FAILED
    event_detail['stderr'] = stderr
    event_detail['error_body'] = error_body

    handle_enrichment_completed.handler(event, None)

    # assert step functions client was initialized
    mocked_sfn.assert_called()
    # assert step functions client was called with the correct arguments
    mocked_sfn.return_value.send_task_failure.assert_called_once()
    mocked_sfn.return_value.send_task_failure.assert_called_with(
        taskToken=MOCK_ADDITIONAL_ATTRIBUTES['task_token'],
        cause=json.dumps(
            Execution(**event_detail).dict(
                exclude_none=True,
                exclude={'context', 'steps', 'additional_attributes'}),  # exclude irrelevant props
            cls=MultiTypeJSONEncoder,  # use custom encoder to handle types that break json serialization
        ),
        error=f"Control failed with status {event['detail']['control_status']}",
    )
    mocked_sfn.return_value.send_task_success.assert_not_called()

    # assert log error was not called
    mocked_logger.error.assert_not_called()

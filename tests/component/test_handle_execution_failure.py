import importlib
import json
import uuid

import pytest
from jit_utils.event_models.trigger_event import TriggerExecutionEvent
from jit_utils.models.execution import TriggerExecutionFailedUpdateEvent
from pydantic_factories import ModelFactory
from test_utils.aws import idempotency

from src.handlers import handle_execution_failure
from src.lib.models.execution_models import ExecutionStatus
from src.lib.models.execution_models import UpdateRequest
from tests.mocks.asset_mocks import MOCK_ASSET_ID
from tests.mocks.execution_mocks import _get_mock_execution_context
from tests.mocks.execution_mocks import MOCK_DYNAMODB_STREAM_INSERT_EVENT
from tests.mocks.execution_mocks import MOCK_EXECUTION_ID
from tests.mocks.execution_mocks import MOCK_JIT_EVENT_ID
from tests.mocks.tenant_mocks import MOCK_TENANT_ID


@pytest.fixture
def setup():
    """Setup for the tests in this module."""
    idempotency.create_idempotency_table()

    # Reload the module with the idempotency decorator to initialization under moto context
    importlib.reload(handle_execution_failure)  # Reload the core to update the reference to the new declared functions


MOCK_JIT_EVENT = {
    "tenant_id": MOCK_TENANT_ID,
    "jit_event_name": "item_activated",
    "jit_event_id": MOCK_JIT_EVENT_ID,
    "asset_id": MOCK_ASSET_ID,
    "workflows": None,
    "activated_plan_slug": "jit-plan",
    "activated_plan_item_slugs": ["item-github-misconfiguration"]
}


class TriggerExecutionEventFactory(ModelFactory):
    __model__ = TriggerExecutionEvent
    tenant_id = MOCK_TENANT_ID
    jit_event = MOCK_JIT_EVENT
    context = _get_mock_execution_context()


def get_eventbridge_event(detail: dict) -> dict:
    return {
        "version": "0",
        "detail-type": "trigger-execution",
        "source": "trigger-service",
        "account": "121169888995",
        "time": "2023-05-23T11:37:31Z",
        "region": "us-east-1",
        "resources": [
            "arn:aws:states:us-east-1:121169888995:stateMachine:bandit-handle-enrichment-process",
            "arn:aws:states:us-east-1:121169888995:execution:bandit-handle-enrichment-process:item_activated-01b8ca74"
            "-575d-4cb4-a331-ea775d6b91ca-1684841849.501928 "
        ],
        "detail": detail,
    }


def get_on_failure_event(original_lambda_input: dict, error_message: str) -> dict:
    return {
        "version": "1.0",
        "timestamp": "2023-05-16T10:24:39.031Z",
        "requestContext": {
            "requestId": str(uuid.uuid4()),
            "functionArn": "arn:aws:lambda:us-east-1:121169888995:function:execution-service-dev-error-handling-poc"
                           ":$LATEST",
            # noqa
            "condition": "RetriesExhausted",
            "approximateInvokeCount": 3
        },
        "requestPayload": original_lambda_input,
        "responseContext": {
            "statusCode": 200,
            "executedVersion": "$LATEST",
            "functionError": "Unhandled"
        },
        "responsePayload": {
            "errorMessage": error_message,
            "errorType": "Exception",
            "stackTrace": [
                "File \"/var/task/epsagon/wrappers/aws_lambda.py\", line 134, in _lambda_wrapper\n    result = func("
                "*args, **kwargs)\n",
                "File \"/var/task/jit_utils/logger/logger.py\", line 125, in wrapped\n    return func(*args, "
                "**kwargs)\n",
                "File \"/var/task/src/handlers/update_execution.py\", line 262, in error_handling_poc\n    raise "
                "Exception(\"an exception\")\n "
            ]
        }
    }


@pytest.mark.parametrize("original_lambda_event", [
    get_eventbridge_event(
        {"tenant_id": MOCK_TENANT_ID, "jit_event_id": MOCK_JIT_EVENT_ID, "execution_id": MOCK_EXECUTION_ID}
    ),
    MOCK_DYNAMODB_STREAM_INSERT_EVENT,
])
def test_handle_execution_failure__existing_execution(executions_manager, setup, mocker, original_lambda_event):
    from src.handlers import handle_execution_failure
    event = get_on_failure_event(original_lambda_event, "an error message")

    def assert_put_event(execution_event: str, detail_type: str) -> None:
        output_event = UpdateRequest(**json.loads(execution_event))
        assert output_event.tenant_id == MOCK_TENANT_ID
        assert output_event.jit_event_id == MOCK_JIT_EVENT_ID
        assert output_event.execution_id == MOCK_EXECUTION_ID
        assert output_event.status == ExecutionStatus.FAILED

    events_client_mock = mocker.patch(
        "src.lib.cores.execution_events.send_execution_event", side_effect=assert_put_event
    )
    handle_execution_failure.handler(event, None)  # noqa
    assert events_client_mock.call_count == 1


def test_handle_execution_failure__execution_triggers(mocker, executions_manager, setup):
    from src.handlers import handle_execution_failure
    trigger_execution_event = TriggerExecutionEventFactory.build()
    event = get_on_failure_event(
        get_eventbridge_event({
            "tenant_id": MOCK_TENANT_ID,
            "jit_event_name": "item_activated",
            "executions": [trigger_execution_event.dict()]
        }),  # noqa
        json.dumps({
            "failure_message": "Failed to trigger executions",
            "failed_triggers": [trigger_execution_event.dict()],
        }, default=list),
    )

    def assert_put_event(execution_event: str, detail_type: str) -> None:
        event = TriggerExecutionFailedUpdateEvent(**json.loads(execution_event))
        assert event.tenant_id == MOCK_TENANT_ID
        assert event.jit_event_id == MOCK_JIT_EVENT_ID
        assert event.vendor == trigger_execution_event.context.asset.vendor
        assert event.workflow_slug == trigger_execution_event.context.workflow.slug
        assert event.job_name == trigger_execution_event.context.job.job_name
        assert event.status == ExecutionStatus.FAILED
        assert event.asset_id == MOCK_ASSET_ID
        assert event.jit_event_name == trigger_execution_event.context.jit_event.jit_event_name

    events_client_mock = mocker.patch(
        "src.lib.cores.execution_events.send_execution_event", side_effect=assert_put_event
    )
    handle_execution_failure.handler(event, None)  # noqa
    assert events_client_mock.call_count == 1


def test_handle_execution_failure__idempotency(mocker, executions_manager, setup):
    from src.handlers import handle_execution_failure
    event = get_on_failure_event(MOCK_DYNAMODB_STREAM_INSERT_EVENT, "an error message")

    events_client_mock = mocker.patch("src.lib.cores.execution_events.send_execution_event")
    handle_execution_failure.handler(event, None)  # noqa
    handle_execution_failure.handler(event, None)  # noqa
    assert events_client_mock.call_count == 1

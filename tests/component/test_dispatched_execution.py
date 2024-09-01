from datetime import datetime

import boto3
import pytest
from aws_lambda_typing.events import EventBridgeEvent
from dateutil import parser
from jit_utils.models.execution_context import RunnerSetup
from test_utils.aws import idempotency
from test_utils.aws.mock_eventbridge import mock_eventbridge

from src.lib import constants as c
from src.lib.constants import CI_RUNNER_DISPATCHED_TIMEOUT, MINUTE_IN_SECONDS
from jit_utils.models.execution import Execution
from src.lib.models.execution_models import ExecutionDispatchUpdateEvent
from src.lib.models.execution_models import ExecutionStatus
from src.lib.models.execution_models import UpdateRequest
from tests.component.common import wrap_eventbridge_event
from tests.component.fixtures import _prepare_execution_to_update
from tests.factories import ExecutionDispatchUpdateEventFactory
from tests.mocks.execution_mocks import MOCK_EXECUTION_CODE_EVENT


def _get_test_event() -> EventBridgeEvent:
    event = wrap_eventbridge_event(
        ExecutionDispatchUpdateEvent(
            tenant_id="test-tid",
            jit_event_id="test-jeid",
            execution_id="test-eid",
            run_id=None,
        ).dict(),
    )
    event["id"] = "test-id"  # Append the id for the idempotency decorator

    return event


@pytest.mark.parametrize(
    "runner_setup, expected_timeout",
    [
        [None, CI_RUNNER_DISPATCHED_TIMEOUT],
        [RunnerSetup(timeout_minutes=10), CI_RUNNER_DISPATCHED_TIMEOUT],  # should not affect timeout
    ],
)
def test_handler__happy_flow(executions_manager, runner_setup, expected_timeout):
    idempotency.create_idempotency_table()
    from src.handlers import dispatched_execution

    _prepare_execution_to_update(
        executions_manager, "test-tid", "test-jeid", "test-eid", ExecutionStatus.DISPATCHING, runner_setup
    )

    event = _get_test_event()
    dispatched_execution.handler(event, None)

    execution = executions_manager.get_execution_by_jit_event_id_and_execution_id("test-tid", "test-jeid", "test-eid")

    assert execution.tenant_id == "test-tid"
    assert execution.jit_event_id == "test-jeid"
    assert execution.execution_id == "test-eid"
    assert execution.status == ExecutionStatus.DISPATCHED
    watchdog_timeout_delta = parser.parse(execution.execution_timeout) - datetime.utcnow()
    is_watchdog_timeout_as_expected = (
            expected_timeout - 10 < watchdog_timeout_delta.seconds < expected_timeout
    )
    assert is_watchdog_timeout_as_expected


@pytest.mark.parametrize(
    "config, jit_event_name, expected_timeout",
    [
        [
            {
                "resource_management": {
                    "runner_config": {
                        "job_setup_timeout_minutes": 20,
                        "pr_job_setup_timeout_minutes": 10,
                    },
                },
            },
            "pull_request_created",
            10 * MINUTE_IN_SECONDS,
        ],
        [
            {
                "resource_management": {
                    "runner_config": {
                        "job_setup_timeout_minutes": 20,
                        "pr_job_setup_timeout_minutes": 10,
                    },
                },
            },
            "item_activated",
            20 * MINUTE_IN_SECONDS,
        ],
    ],
)
def test_handler__with_resource_management_runner_config(executions_manager, config, jit_event_name, expected_timeout):
    idempotency.create_idempotency_table()
    from src.handlers import dispatched_execution

    _prepare_execution_to_update(
        executions_manager,
        "test-tid",
        "test-jeid",
        "test-eid",
        ExecutionStatus.DISPATCHING,
        RunnerSetup(timeout_minutes=10),
        jit_event_name=jit_event_name,
        config=config,
    )

    event = _get_test_event()
    dispatched_execution.handler(event, None)

    execution = executions_manager.get_execution_by_jit_event_id_and_execution_id("test-tid", "test-jeid", "test-eid")

    assert execution.tenant_id == "test-tid"
    assert execution.jit_event_id == "test-jeid"
    assert execution.execution_id == "test-eid"
    assert execution.status == ExecutionStatus.DISPATCHED
    watchdog_timeout_delta = parser.parse(execution.execution_timeout) - datetime.utcnow()
    is_watchdog_timeout_as_expected = expected_timeout - 10 < watchdog_timeout_delta.seconds < expected_timeout
    assert is_watchdog_timeout_as_expected


def test_handler__server_error_update(executions_manager):
    idempotency.create_idempotency_table()
    from src.handlers import dispatched_execution

    _prepare_execution_to_update(executions_manager, "test-tid", "test-jeid", "test-eid", ExecutionStatus.PENDING)
    event = _get_test_event()

    with pytest.raises(boto3.exceptions.botocore.exceptions.ClientError) as e:
        dispatched_execution.handler(event, None)
        assert e.response["Error"]["Code"] == "ConditionalCheckFailedException"


def test__with_execution_not_exists(mocker, executions_manager):
    """
    While we know the Executions table is empty, we expect an ExecutionNotExistsException to be raised and handled.
    """
    from src.handlers import dispatched_execution

    idempotency.mock_idempotent_decorator(
        mocker=mocker,
        module_to_reload=dispatched_execution,
    )

    event = ExecutionDispatchUpdateEventFactory().build(run_id=None)

    with mock_eventbridge(bus_name=c.EXECUTION_EVENT_BUS_NAME) as get_sent_events:
        rv = dispatched_execution.handler(
            {
                "detail": event.dict(),
            },
            None,
        )

        sent_events = get_sent_events()

    assert rv is None
    assert len(sent_events) == 1
    assert sent_events[0]["detail-type"] == c.EXECUTION_DEPROVISIONED_EXECUTION_EVENT_DETAIL_TYPE
    assert sent_events[0]["detail"] == {
        **event.dict(exclude_none=True),
        "status": ExecutionStatus.FAILED,
        "error_body": "There was an error during the execution process",
        "status_details": {
            "message": "There was an error during the execution process",
        },
        "errors": []
    }


@pytest.mark.parametrize(
    "current_status",
    [
        ExecutionStatus.DISPATCHED,
        ExecutionStatus.RUNNING,
        ExecutionStatus.COMPLETED,
        ExecutionStatus.FAILED,
        ExecutionStatus.CONTROL_TIMEOUT,
        ExecutionStatus.WATCHDOG_TIMEOUT,
    ],
)
def test_handler__client_error_update(executions_manager, current_status):
    idempotency.create_idempotency_table()
    from src.handlers import dispatched_execution

    _prepare_execution_to_update(executions_manager, "test-tid", "test-jeid", "test-eid", current_status)
    event = _get_test_event()

    execution = dispatched_execution.handler(event, None)

    assert execution is None


def test_dispatched_execution__idempotency(
    executions_manager,
):
    idempotency.create_idempotency_table()
    from src.handlers import dispatched_execution

    # Set up the execution in the DB
    e = MOCK_EXECUTION_CODE_EVENT
    e.status = ExecutionStatus.DISPATCHING
    e = executions_manager.create_execution(execution=e)

    # Assert the execution is in DISPATCHING state
    assert e.status == ExecutionStatus.DISPATCHING
    assert not e.dispatched_at
    assert not e.dispatched_at_ts
    assert not e.run_id

    # Launch the dispatched_execution handler
    event = {
        "id": "test-id",
        "detail": UpdateRequest(
            tenant_id=e.tenant_id,
            jit_event_id=e.jit_event_id,
            execution_id=e.execution_id,
            status=ExecutionStatus.DISPATCHED,
            run_id="test-run-id",
        ).dict(),
    }
    dispatched_execution.handler(event, None)

    def get_execution() -> Execution:
        return executions_manager.get_execution_by_jit_event_id_and_execution_id(
            tenant_id=e.tenant_id,
            jit_event_id=e.jit_event_id,
            execution_id=e.execution_id,
        )

    # Assert the execution has been updated
    e_after_first_handler = get_execution()
    assert e_after_first_handler.status == ExecutionStatus.DISPATCHED
    assert e_after_first_handler.dispatched_at is not None
    assert e_after_first_handler.dispatched_at_ts is not None
    assert e_after_first_handler.run_id == "test-run-id"

    # Send the same event again
    dispatched_execution.handler(event, None)

    # Assert the execution has not been changed (idempotency decorator works)
    e_after_second_handler = get_execution()
    assert e_after_second_handler.status == ExecutionStatus.DISPATCHED
    assert e_after_second_handler.dispatched_at == e_after_first_handler.dispatched_at
    assert e_after_second_handler.dispatched_at_ts == e_after_first_handler.dispatched_at_ts
    assert e_after_second_handler.run_id == e_after_first_handler.run_id

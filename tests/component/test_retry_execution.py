from unittest.mock import patch

import botocore.exceptions
from jit_utils.event_models.trigger_event import TriggerExecutionEvent
from pydantic import parse_obj_as
from test_utils.aws.mock_eventbridge import mock_eventbridge

from src.handlers.retry_execution import handler
from src.lib.constants import TRIGGER_EXECUTION_EVENT_BUS_NAME, TRIGGER_EXECUTION_DETAIL_TYPE, EXECUTION_RETRY_LIMIT, \
    EXECUTION_NOT_FOUND_ERROR_ALERT, EXECUTION_MAX_RETRIES_ALERT
from jit_utils.models.execution import Execution, ExecutionStatus, BaseExecutionIdentifiers
from tests.mocks.execution_mocks import MOCK_EXECUTION
from freezegun import freeze_time


@freeze_time("2022-12-12T00:00:00.000000")
def test_retry_execution_handler__happy_flow(executions_manager, resources_manager):
    """
    Test that the handler retries an execution and sends a trigger execution event to the bus.
    Setup:
        - Create a dispatched execution
        - Basic identifiers event
        - Mock the eventbridge

    Test:
        - Call the handler

    Assert:
        - The handler doesn't throw an exception
        - The execution is updated to RETRY
        - The execution retry count is incremented
        - The trigger execution event is sent
    """
    # Setup - Create the dispatched execution
    execution = MOCK_EXECUTION.copy()
    execution.status = ExecutionStatus.DISPATCHED
    executions_manager.create_execution(execution)

    # Setup - event
    event = {
        'execution_id': execution.execution_id,
        'tenant_id': execution.tenant_id,
        'jit_event_id': execution.jit_event_id,
    }

    # Setup - Mock the eventbridge
    with mock_eventbridge(bus_name=TRIGGER_EXECUTION_EVENT_BUS_NAME) as get_sent_events:
        # Test
        assert handler(event, {}) is None  # This means no exception was thrown

        # Assert bus event
        sent_events = get_sent_events()
        assert len(sent_events) == 1
        assert sent_events[0]['detail-type'] == TRIGGER_EXECUTION_DETAIL_TYPE
        event = sent_events[0]['detail']
        trigger_exec_event = parse_obj_as(TriggerExecutionEvent, event['Message'])
        assert trigger_exec_event.jit_event.jit_event_id == execution.jit_event_id
        assert trigger_exec_event.jit_event.tenant_id == execution.tenant_id
        assert trigger_exec_event.retry_count == execution.retry_count + 1
        assert trigger_exec_event.job_name == execution.job_name
        assert trigger_exec_event.jit_event.jit_event_name == execution.jit_event_name
        # Assert DB item
        items = executions_manager.table.scan()['Items']
        assert len(items) == 1
        execution_in_db = Execution(**items[0])

        assert execution_in_db.dict() == {
            **execution.dict(),
            'status': ExecutionStatus.RETRY,
            'retry_count': execution.retry_count + 1,
        }


def test_retry_execution_handler__retry_limit_exceeded(executions_manager, resources_manager):
    """
    Test that the handler correctly handles an execution that has reached the maximum retry limit.
    Setup:
        - Create an execution with retry count equal to the limit
        - Basic identifiers event
        - Mock the eventbridge and alert system

    Test:
        - Call the handler

    Assert:
        - The handler doesn't throw an exception
        - No event is sent to the event bus
        - An alert for reaching the max retry limit is triggered
    """
    # Setup - Create the execution at max retry limit
    execution = MOCK_EXECUTION.copy()
    execution.status = ExecutionStatus.RETRY
    execution.retry_count = EXECUTION_RETRY_LIMIT
    executions_manager.create_execution(execution)

    event = {
        'execution_id': execution.execution_id,
        'tenant_id': execution.tenant_id,
        'jit_event_id': execution.jit_event_id,
    }

    basic_execution_identifiers = BaseExecutionIdentifiers(**event)

    # Setup - Mock the eventbridge and alert system
    with mock_eventbridge(bus_name=TRIGGER_EXECUTION_EVENT_BUS_NAME) as get_sent_events, \
         patch('src.handlers.retry_execution.alert') as mock_alert:
        # Test
        assert handler(event, {}) is None  # This means no exception was thrown

        # Assert no bus event
        sent_events = get_sent_events()
        assert len(sent_events) == 0

        # Assert an alert has been triggered for max retries
        mock_alert.assert_called_once_with(
            f'Execution reached max retries {basic_execution_identifiers=}',
            alert_type=EXECUTION_MAX_RETRIES_ALERT
        )


def test_retry_execution_handler__execution_not_found(executions_manager, resources_manager):
    """
    Test that the handler alerts when no execution is found in the database matching the event identifiers.
    Setup:
        - Basic identifiers event for a non-existent execution
        - Mock the eventbridge

    Test:
        - Call the handler

    Assert:
        - The handler doesn't throw an exception
        - No event is sent to the event bus
        - An alert for a non-existing execution retry attempt is triggered
    """
    # Setup - event for non-existent execution
    event = {
        'execution_id': 'nonexistent_id',
        'tenant_id': 'nonexistent_tenant',
        'jit_event_id': 'nonexistent_event',
    }
    basic_execution_identifiers = BaseExecutionIdentifiers(**event)

    # Setup - Mock the eventbridge
    with mock_eventbridge(bus_name=TRIGGER_EXECUTION_EVENT_BUS_NAME) as get_sent_events:
        # Test
        with patch('src.handlers.retry_execution.alert') as mock_alert:
            assert handler(event, {}) is None

            # Assert no bus event
            sent_events = get_sent_events()
            assert len(sent_events) == 0

            # Assert an alert has been triggered for non-existent execution
            mock_alert.assert_called_once_with(
                f'Invoked retry for non existing execution {basic_execution_identifiers=}',
                alert_type=EXECUTION_NOT_FOUND_ERROR_ALERT
            )


def test_retry_execution_handler__invalid_status(executions_manager, resources_manager):
    """
    Test that the handler does not process retries for executions with an invalid status like PENDING.
    Setup:
        - Create an execution with PENDING status
        - Basic identifiers event
        - Mock the eventbridge

    Test:
        - Call the handler

    Assert:
        - No trigger execution event is sent
        - Execution status remains unchanged
    """
    # Setup - Create an execution with PENDING status
    execution = MOCK_EXECUTION.copy()
    execution.status = ExecutionStatus.PENDING
    executions_manager.create_execution(execution)

    event = {
        'execution_id': execution.execution_id,
        'tenant_id': execution.tenant_id,
        'jit_event_id': execution.jit_event_id,
    }

    with mock_eventbridge(bus_name=TRIGGER_EXECUTION_EVENT_BUS_NAME) as get_sent_events:
        # Test
        try:
            handler(event, {})
        except botocore.exceptions.ClientError as e:
            if 'ConditionalCheckFailedException' in str(e):
                pass

        # Assert no event is sent
        assert len(get_sent_events()) == 0

        # Assert execution remains unchanged
        items = executions_manager.table.scan()['Items']
        assert len(items) == 1
        execution_in_db = Execution(**items[0])

        assert execution_in_db == execution

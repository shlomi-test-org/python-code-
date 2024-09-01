import json
import pytest
from freezegun import freeze_time
from jit_utils.models.execution import ExecutionStatus, Execution, ExecutionError, ExecutionErrorType
from test_utils.aws import idempotency
from test_utils.aws.mock_eventbridge import mock_eventbridge

from src.lib.constants import EXECUTION_EVENT_BUS_NAME
from src.lib.data.executions_manager import ExecutionsManager
from src.lib.exceptions import ExecutionNotExistException
from tests.mocks.execution_mocks import MOCK_DYNAMODB_STREAM_INSERT_EVENT, MOCK_EXECUTION
from tests.unit.data.test_executions_manager import write_executions_to_db  # noqa (fixture import)


@freeze_time("2022-12-12T00:00:00.000000")
def test_complete_execution_handler__event_bridge(mocker, executions_manager):
    """
    Test the complete_execution_handler with an event bridge event
    setup the execution in the db, call the handler and assert the execution is completed
    assert the completed_at and completed_at_ts of actual execution are bigger than the expected execution
    assert the event is sent to event bridge
    assert status is completed
    """
    mocker.patch('src.lib.cores.executions_core.free_resource')
    # Setup - Create the dispatched execution
    execution = MOCK_EXECUTION.copy()
    execution.status = ExecutionStatus.RUNNING
    executions_manager.create_execution(execution)

    from src.handlers import complete_execution
    idempotency.mock_idempotent_decorator(
        mocker=mocker,
        module_to_reload=complete_execution,
    )
    # Setup - event
    event = {
        'id': 'test-id',
        'detail-type': '',
        'detail': {
            'tenant_id': execution.tenant_id,
            'jit_event_id': execution.jit_event_id,
            'execution_id': execution.execution_id,
            'status': ExecutionStatus.COMPLETED,
            'execution_timeout': '2023-12-12T00:00:00.000000',
        }
    }

    _assert_execution_completed(event, complete_execution, executions_manager, execution)


@freeze_time("2022-12-12T00:00:00.000000")
def test_complete_execution_handler__dynamo_stream(mocker, executions_manager):
    """
    Test the complete_execution_handler with a dynamo stream event
    setup the execution in the db, call the handler and assert the execution is completed
    assert the completed_at and completed_at_ts of actual execution are bigger than the expected execution
    assert the event is sent to event bridge
    assert status is completed
    """
    mocker.patch('src.lib.cores.executions_core.free_resource')
    # Setup - Create the dispatched execution
    execution = MOCK_EXECUTION.copy()
    execution.status = ExecutionStatus.RUNNING
    executions_manager.create_execution(execution)

    from src.handlers import complete_execution
    idempotency.mock_idempotent_decorator(
        mocker=mocker,
        module_to_reload=complete_execution,
    )
    # Setup - event
    event = MOCK_DYNAMODB_STREAM_INSERT_EVENT.copy()
    event['Records'][0]['dynamodb']['NewImage']['tenant_id']['S'] = execution.tenant_id
    event['Records'][0]['dynamodb']['NewImage']['jit_event_id']['S'] = execution.jit_event_id
    event['Records'][0]['dynamodb']['NewImage']['execution_id']['S'] = execution.execution_id
    event['Records'][0]['dynamodb']['NewImage']['control_status'] = {'S': ExecutionStatus.COMPLETED}

    _assert_execution_completed(event, complete_execution, executions_manager, execution)


def _assert_execution_completed(
        event: dict,
        complete_execution: callable,
        executions_manager: ExecutionsManager,
        execution: Execution):
    with mock_eventbridge(bus_name=[EXECUTION_EVENT_BUS_NAME]) as get_events:
        # Test
        assert complete_execution.complete_execution_handler(event, {}) is None
        execution_completed_events = get_events[EXECUTION_EVENT_BUS_NAME]()
        assert len(execution_completed_events) == 1

    # Assert DB item
    items = executions_manager.table.scan()['Items']
    assert len(items) == 1
    execution_in_db = Execution(**items[0])

    expected_execution = execution.copy()
    expected_execution.status = ExecutionStatus.COMPLETED
    # assert the completed_at and completed_at_ts of actual execution are bigger than the expected execution
    assert execution_in_db.completed_at >= expected_execution.completed_at
    assert execution_in_db.completed_at_ts >= expected_execution.completed_at_ts
    # remove the completed_at and completed_at_ts from the expected execution
    del expected_execution.completed_at
    del expected_execution.completed_at_ts
    del execution_in_db.completed_at
    del execution_in_db.completed_at_ts
    assert execution_in_db == expected_execution


def test_handler_with_nonexistent_execution(mocker, executions_manager):
    """
    Test the complete_execution_handler when it is called with a valid update request
    but the execution does not exist in the database, which should raise an ExecutionNotExistException.
    """
    from src.handlers import complete_execution
    idempotency.mock_idempotent_decorator(
        mocker=mocker,
        module_to_reload=complete_execution,
    )

    # Creating a mock event that simulates an EventBridge event where the execution does not exist
    event = {
        'id': 'test-id',
        'detail-type': 'UpdateExecutionDetail',
        'detail': {
            'tenant_id': 'tenant-id',
            'jit_event_id': 'jit-event-id',
            'execution_id': 'nonexistent-execution-id',
            'status': ExecutionStatus.COMPLETED,
        }
    }

    # Expecting an ExecutionNotExistException to be raised
    with pytest.raises(ExecutionNotExistException):
        complete_execution.complete_execution_handler(event, None)


@freeze_time("2022-12-12T00:00:00.000000")
def test_complete_execution_handler__with_retry(mocker, executions_manager):
    """
    Test the complete_execution_handler with an event bridge event
    setup the execution in the db, call the handler and assert the retry lambda was invoked
    """
    # Setup - Mock AWS Lambda client
    mock_lambda_client = mocker.patch('boto3.client')
    mock_invoke = mock_lambda_client.return_value.invoke
    mock_invoke.return_value = {'StatusCode': 202}

    mocker.patch('src.lib.cores.executions_core.free_resource')
    # Setup - Create the dispatched execution
    execution = MOCK_EXECUTION.copy()
    execution.status = ExecutionStatus.DISPATCHING
    execution.errors = [ExecutionError(error_type=ExecutionErrorType.VENDOR_ERROR, error_body='error')]
    executions_manager.create_execution(execution)

    from src.handlers import complete_execution
    idempotency.mock_idempotent_decorator(
        mocker=mocker,
        module_to_reload=complete_execution,
    )
    # Setup - event
    event = {
        'id': 'test-id',
        'detail-type': '',
        'detail': {
            'tenant_id': execution.tenant_id,
            'jit_event_id': execution.jit_event_id,
            'execution_id': execution.execution_id,
            'status': ExecutionStatus.DISPATCHING,
        }
    }

    assert complete_execution.complete_execution_handler(event, {}) is None

    # Asserts
    mock_invoke.assert_called_once()
    call_args = mock_invoke.call_args[1]
    assert call_args['FunctionName'] == 'retry-execution'
    assert json.loads(call_args['Payload']) == {
        'tenant_id': execution.tenant_id,
        'jit_event_id': execution.jit_event_id,
        'execution_id': execution.execution_id,
    }

    # Assert DB item
    items = executions_manager.table.scan()['Items']
    assert len(items) == 1
    execution_in_db = Execution(**items[0])
    execution_in_db.status = ExecutionStatus.DISPATCHING

import pytest
from jit_utils.event_models.trigger_event import BulkTriggerExecutionEvent
from jit_utils.event_models.trigger_event import TriggerExecutionEvent
from jit_utils.models.execution_context import Runner

import src.handlers.trigger_execution
from src.handlers.trigger_execution import handler
from src.lib.constants import EXECUTION_ENRICH_EXECUTION_EVENT_DETAIL_TYPE
from src.lib.constants import EXECUTION_EVENT_BUS_NAME
from src.lib.constants import TRIGGER_SERVICE_NAME
from tests.mocks.execution_mocks import generate_mock_executions
from tests.mocks.execution_mocks import MOCK_TENANT_ID


@pytest.mark.parametrize('mock_execution', [
    generate_mock_executions(1, MOCK_TENANT_ID)[0],
    generate_mock_executions(1, MOCK_TENANT_ID, job_runner=Runner.JIT)[0]
])
def test_trigger_execution_handler(mocker, mock_execution):
    mock_jit_event = mock_execution.context.jit_event
    trigger_execution_event = TriggerExecutionEvent(**{**mock_execution.dict(),
                                                       "jit_event": mock_jit_event})
    mock_event = {
        'detail': BulkTriggerExecutionEvent(executions=[trigger_execution_event], tenant_id=MOCK_TENANT_ID,
                                            jit_event_name=mock_jit_event.jit_event_name).dict(),
        'source': TRIGGER_SERVICE_NAME,
        'detail_type': EXECUTION_ENRICH_EXECUTION_EVENT_DETAIL_TYPE,
        'bus_name': EXECUTION_EVENT_BUS_NAME
    }

    mocker_trigger_execution_core = mocker.patch.object(src.handlers.trigger_execution, 'trigger_execution',
                                                        return_value=None)
    mocker_execution_manager = mocker.patch.object(src.handlers.trigger_execution, "ExecutionsManager")
    handler(mock_event, {})

    assert mocker_trigger_execution_core.call_count == 1
    assert mocker_execution_manager.call_count == 1
    assert mocker_trigger_execution_core.call_args[1]['trigger_event'] == trigger_execution_event


def test_trigger_execution_handler_step_function_event(mocker):
    mock_token = 'some_test_token'
    mock_execution = generate_mock_executions(1, MOCK_TENANT_ID)[0]
    mock_jit_event = mock_execution.context.jit_event
    trigger_execution_event = TriggerExecutionEvent(**{**mock_execution.dict(),
                                                       "jit_event": mock_jit_event})
    mock_event = {
        'detail': {'Message': BulkTriggerExecutionEvent(executions=[trigger_execution_event], tenant_id=MOCK_TENANT_ID,
                                                        jit_event_name=mock_jit_event.jit_event_name).dict(),
                   'TaskToken': mock_token},
        'source': TRIGGER_SERVICE_NAME,
        'detail_type': EXECUTION_ENRICH_EXECUTION_EVENT_DETAIL_TYPE,
        'bus_name': EXECUTION_EVENT_BUS_NAME
    }

    mocker_trigger_execution_core = mocker.patch.object(src.handlers.trigger_execution, 'trigger_execution',
                                                        return_value=None)
    mocker_execution_manager = mocker.patch.object(src.handlers.trigger_execution, "ExecutionsManager")
    handler(mock_event, {})

    assert mocker_trigger_execution_core.call_count == 1
    assert mocker_execution_manager.call_count == 1
    assert mocker_trigger_execution_core.call_args[1]['trigger_event'] == trigger_execution_event
    assert mocker_trigger_execution_core.call_args[1]['task_token'] == mock_token

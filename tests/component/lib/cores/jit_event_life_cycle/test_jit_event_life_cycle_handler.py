import pytest
from jit_utils.event_models import CodeRelatedJitEvent
from jit_utils.models.trigger.jit_event_life_cycle import JitEventStatus, JitEventLifeCycleEntity
from test_utils.aws.mock_eventbridge import mock_eventbridge

from src.lib.constants import JIT_EVENT_LIFE_CYCLE_EVENT_BUS_NAME, COMPLETED_JIT_EVENT_LIFE_CYCLE_EVENT_DETAIL_TYPE
from src.lib.cores.jit_event_life_cycle.jit_event_life_cycle_handler import JitEventLifeCycleHandler
from src.lib.exceptions import JitEventLifeCycleNonFinalStatusCompleteAttempt
from tests.common import CodeRelatedJitEventFactory

test_jit_event: CodeRelatedJitEvent = CodeRelatedJitEventFactory.build()


@pytest.mark.parametrize("status, expected_error", (
        (JitEventStatus.STARTED, JitEventLifeCycleNonFinalStatusCompleteAttempt(status=JitEventStatus.STARTED)),
        (JitEventStatus.FAILED, None),
        (JitEventStatus.COMPLETED, None),
))
def test_jit_event_completed(
        status: JitEventStatus,
        jit_event_life_cycle_handler: JitEventLifeCycleHandler,
        expected_error: Exception,
):
    # Start the jit event lifecycle
    with mock_eventbridge([JIT_EVENT_LIFE_CYCLE_EVENT_BUS_NAME]):
        jit_event_life_cycle_handler.start(test_jit_event)

    try:
        with mock_eventbridge([JIT_EVENT_LIFE_CYCLE_EVENT_BUS_NAME]) as get_events:
            jit_event_life_cycle_handler.jit_event_completed(
                tenant_id=test_jit_event.tenant_id,
                jit_event_id=test_jit_event.jit_event_id,
                status=status,
            )
    except Exception as e:
        if expected_error is not None:
            assert type(e) is type(expected_error)
            assert str(expected_error) in str(e)
        else:
            raise e
    else:
        jit_event_life_cycle_events = get_events[JIT_EVENT_LIFE_CYCLE_EVENT_BUS_NAME]()
        assert len(jit_event_life_cycle_events) == 1
        jit_event_life_cycle_event = jit_event_life_cycle_events[0]
        assert jit_event_life_cycle_event['detail-type'] == COMPLETED_JIT_EVENT_LIFE_CYCLE_EVENT_DETAIL_TYPE
        assert JitEventLifeCycleEntity(**jit_event_life_cycle_events[0]['detail']).status == status

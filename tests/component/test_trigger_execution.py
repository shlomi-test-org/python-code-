import importlib
import json
import responses

import pytest
from dateutil.parser import parse

from src.handlers import dispatch_execution
from jit_utils.event_models import ManualExecutionJitEvent
from test_utils.aws.idempotency import mock_idempotent_decorator
from jit_utils.event_models.trigger_event import BulkTriggerExecutionEvent, TriggerExecutionEvent
from jit_utils.jit_event_names import JitEventName
from jit_utils.models.execution_priority import ExecutionPriority
from jit_utils.models.oauth.entities import VendorEnum
from jit_utils.models.tenant.entities import Installation
from test_utils.aws import idempotency
from test_utils.aws.mock_eventbridge import mock_eventbridge

from src.handlers import trigger_execution
from src.lib.constants import EXECUTION_EVENT_BUS_NAME
from src.lib.cores import create_execution
from src.lib.data.executions_manager import ExecutionsManager
from src.lib.exceptions import FailedTriggersExceptions
from jit_utils.models.execution import Execution, TriggerExecutionFailedUpdateEvent
from src.lib.models.execution_models import ExecutionStatus
from tests.component.mock_responses.mock_asset_service import mock_get_asset_by_id
from tests.component.mock_responses.mock_authentication_service import mock_get_internal_token_api
from tests.component.mock_responses.mock_github_service import mock_github_service_dispatch
from tests.component.mock_responses.mock_tenant_service import mock_get_installations_api
from tests.component.test_get_execution import MOCK_TENANT_ID
from tests.mocks.asset_mocks import MOCK_ASSET_ID
from tests.mocks.execution_mocks import (
    generate_mock_trigger_execution_events,
    generate_mock_executions,
    MOCK_JIT_EVENT_ID,
)


@pytest.fixture
def setup():
    """Setup for the tests in this module."""
    idempotency.create_idempotency_table()

    # Reload the module with the idempotency decorator to initialization under moto context
    importlib.reload(create_execution)
    importlib.reload(trigger_execution)  # Reload the core to update the reference to the new declared functions


def test__happy_flow(executions_manager, setup):
    mock_execution = generate_mock_executions(1, MOCK_TENANT_ID)[0]
    jit_event_attribute = mock_execution.context.jit_event
    trigger_execution_event = TriggerExecutionEvent(**{**mock_execution.dict(),
                                                       "steps": mock_execution.context.job.steps,
                                                       "jit_event": jit_event_attribute})

    assert trigger_execution.handler({'detail': trigger_execution_event.dict()}, None) is None

    items = executions_manager.table.scan()['Items']

    assert len(items) == 1

    received_execution = Execution(**items[0])
    expected_execution = Execution(**trigger_execution_event.dict(),
                                   **trigger_execution_event.jit_event.dict(),
                                   created_at_ts=int(parse(trigger_execution_event.created_at).timestamp()),
                                   execution_id=received_execution.execution_id,
                                   status=ExecutionStatus.PENDING,
                                   control_name=trigger_execution_event.context.job.steps[0].name,
                                   control_image=trigger_execution_event.context.job.steps[0].uses,
                                   asset_name=received_execution.context.asset.asset_name,
                                   asset_type=received_execution.context.asset.asset_type,
                                   vendor=received_execution.context.asset.vendor)
    # created at is set inside the lambda, so trigger event times and execution event times can't be the same
    expected_execution.created_at = received_execution.created_at = ''
    expected_execution.created_at_ts = received_execution.created_at_ts = None
    assert expected_execution == received_execution

    # Assert idempotency
    assert executions_manager.table.scan()['Count'] == 1
    idempotency.assert_idempotency_table_item_count(1)


def test__high_priority_executions(executions_manager, setup):
    event = generate_mock_trigger_execution_events(amount=1, tenant_id='test-tid',
                                                   jit_event_fields={
                                                       # Must be high priority event
                                                       "jit_event_name": JitEventName.PullRequestCreated
                                                   })[0]
    # Setup - Mock the eventbridge
    with mock_eventbridge(bus_name=EXECUTION_EVENT_BUS_NAME) as get_sent_events:
        assert trigger_execution.handler({'detail': event.dict()}, None) is None

    # Assert idempotency
    executions_in_db = executions_manager.table.scan()['Items']
    assert len(executions_in_db) == 1
    idempotency.assert_idempotency_table_item_count(1)
    sent_events = get_sent_events()
    assert len(sent_events) == 1
    assert sent_events[0]['detail-type'] == 'enrich-execution'
    assert sent_events[0]['source'] == 'execution-service'
    assert sent_events[0]['detail'] == {
        'tenant_id': event.jit_event.tenant_id,
        'jit_event_id': event.jit_event.jit_event_id,
        'execution_ids': [executions_in_db[0]['execution_id']]
    }


@responses.activate
@pytest.mark.parametrize(
    "ci_installation, is_success",
    [
        [
            Installation(
                installation_id='installation1',
                is_active=True,
                owner='123456789012',
                app_id='app1',
                created_at='2021-01-01T00:00:00.000Z',
                creator='creator1',
                modified_at='2021-01-01T00:00:00.000Z',
                name='installation1',
                tenant_id=MOCK_TENANT_ID,
                vendor=VendorEnum.GITHUB,
            ),
            True,
        ],
        [
            Installation(
                installation_id='installation1',
                is_active=True,
                owner='123456789012',
                app_id='app1',
                created_at='2021-01-01T00:00:00.000Z',
                creator='creator1',
                modified_at='2021-01-01T00:00:00.000Z',
                name='installation1',
                tenant_id=MOCK_TENANT_ID,
                vendor=VendorEnum.GITLAB,
            ),
            True,
        ],
        [
            Installation(
                installation_id='installation1',
                is_active=False,
                owner='123456789012',
                app_id='app1',
                created_at='2021-01-01T00:00:00.000Z',
                creator='creator1',
                modified_at='2021-01-01T00:00:00.000Z',
                name='installation1',
                tenant_id=MOCK_TENANT_ID,
                vendor=VendorEnum.GITHUB,
            ),
            False,
        ],
    ],
)
def test__high_priority_ci_runner_with_non_ci_vendor_execution(ci_installation, is_success, executions_manager, setup):
    mock_get_internal_token_api()
    mock_get_installations_api(
        [
            Installation(
                installation_id='installation2',
                is_active=True,
                owner='123456789012',
                app_id='app1',
                created_at='2021-01-01T00:00:00.000Z',
                creator='creator1',
                modified_at='2021-01-01T00:00:00.000Z',
                name='installation1',
                tenant_id=MOCK_TENANT_ID,
                vendor=VendorEnum.AWS,
            ),
            ci_installation,
        ]
    )
    execution = generate_mock_executions(1, MOCK_TENANT_ID)[0]
    execution.context.asset.vendor = VendorEnum.AWS
    execution.context.jit_event = ManualExecutionJitEvent(
        tenant_id=MOCK_TENANT_ID,
        jit_event_id=MOCK_JIT_EVENT_ID,
        asset_ids_filter=[execution.context.asset.asset_id],
        plan_item_slug=execution.plan_item_slug,
        priority=ExecutionPriority.HIGH,
    )
    event = TriggerExecutionEvent(
        **{
            **execution.dict(),
            "jit_event": execution.context.jit_event,
            "affected_plan_items": execution.affected_plan_items,
        }
    )

    if is_success:
        with mock_eventbridge(bus_name=EXECUTION_EVENT_BUS_NAME) as get_sent_events:
            trigger_execution.handler({'detail': event.dict()}, None)
        executions_in_db = executions_manager.table.scan()['Items']
        assert len(executions_in_db) == 1
        idempotency.assert_idempotency_table_item_count(1)
        sent_events = get_sent_events()
        assert len(sent_events) == 1
        assert sent_events[0]['detail-type'] == 'enrich-execution'
        assert sent_events[0]['source'] == 'execution-service'
        assert sent_events[0]['detail'] == {
            'tenant_id': event.jit_event.tenant_id,
            'jit_event_id': event.jit_event.jit_event_id,
            'execution_ids': [executions_in_db[0]['execution_id']]
        }
    else:
        with pytest.raises(FailedTriggersExceptions):
            trigger_execution.handler({'detail': event.dict()}, None)


def test__idempotency_on_bulk(mocker, executions_manager, setup):
    events = BulkTriggerExecutionEvent(
        tenant_id='test-tid',
        executions=generate_mock_trigger_execution_events(amount=2, tenant_id='test-tid',
                                                          jit_event_fields={
                                                              # jit_event_name must be not high priority,
                                                              # so it'll be manged by the resource manager
                                                              "jit_event_name": JitEventName.TriggerScheduledTask
                                                          })
    )
    raised = False  # We want to raise the exception only in the first handler call

    def _mocked_manager_create_execution(exec: Execution):
        nonlocal raised

        # Raise only in the first time
        if exec.job_name == 'job-1' and not raised:
            raised = True
            raise Exception('Custom exception')

    mocked_manager_create_execution = mocker.patch(
        target='src.handlers.trigger_execution.ExecutionsManager.create_execution',
        side_effect=_mocked_manager_create_execution,
    )

    # First call, we except an exception to be raised on the 2nd event in the bulk
    with pytest.raises(Exception) as e:
        assert trigger_execution.handler({'detail': events.dict()}, None) is None
        assert 'Custom exception' in str(e)

    # Second call, we except only the 2nd event to be processed and to successfully finish
    assert trigger_execution.handler({'detail': events.dict()}, None) is None

    # Assert idempotency items exists
    idempotency.assert_idempotency_table_item_count(2)

    # First call from the 1st event, second call from the 2nd event, and the third call also from the 2nd event
    # (as we failed it in the first time with the mocked create_execution)
    assert mocked_manager_create_execution.call_count == 3


def test__error_handling(mocker, executions_manager, setup):
    events = BulkTriggerExecutionEvent(
        tenant_id='test-tid',
        executions=generate_mock_trigger_execution_events(amount=3, tenant_id='test-tid'),
    )
    events.executions[0].context.job.steps = []  # corrupted event
    events.executions[1].context.job.job_name = "this should raise"  # unexpected exception
    original_create_execution = executions_manager.create_execution

    def mock_create_execution(execution: Execution) -> Execution:
        if execution.job_name == "this should raise":
            raise Exception
        return original_create_execution(execution)

    mocker.patch.object(ExecutionsManager, 'create_execution', side_effect=mock_create_execution)

    def assert_put_event(execution_event: str, detail_type: str) -> None:
        event = TriggerExecutionFailedUpdateEvent(**json.loads(execution_event))
        trigger_event = events.executions[0]
        assert event.tenant_id == trigger_event.context.jit_event.tenant_id
        assert event.jit_event_id == trigger_event.context.jit_event.jit_event_id
        assert event.vendor == trigger_event.context.asset.vendor
        assert event.workflow_slug == trigger_event.context.workflow.slug
        assert event.job_name == trigger_event.context.job.job_name
        assert event.status == ExecutionStatus.FAILED
        assert event.asset_id == trigger_event.context.asset.asset_id
        assert event.jit_event_name == trigger_event.context.jit_event.jit_event_name

    events_client_mock = mocker.patch(
        "src.lib.cores.execution_events.send_execution_event", side_effect=assert_put_event
    )

    with pytest.raises(FailedTriggersExceptions) as exc:
        assert trigger_execution.handler({'detail': events.dict()}, None) is None
    exception = exc.value
    assert exception.failed_trigger_execution_events == [events.executions[1]]

    # Assert idempotency
    assert executions_manager.table.scan()['Count'] == 1
    idempotency.assert_idempotency_table_item_count(2)

    # Assert error handling
    assert events_client_mock.call_count == 1


def test__trigger_execution__multiple_execution_ids(mocker, executions_manager, setup):
    """
    Test case where 'trigger-execution' submits multiple executions to EventBridge in a single invocation,
    and 'dispatch-execution' lambda is wakes up once and handles (dispatches) all executions.

    1. Create a mock event with 3 different executions under the same 'tenant_id' and 'jit_event_id'
    2. Mock EventBridge to capture the dispatched events
    3. Invoke trigger_execution.handler with the event
    4. Invoke dispatch_execution.handler as it is triggered by the EventBridge event
    5. Assert that the handler dispatched all 3 executions, as they were all part of the same event.

    """
    events = BulkTriggerExecutionEvent(
        tenant_id=MOCK_TENANT_ID,
        executions=generate_mock_trigger_execution_events(
            amount=3,
            tenant_id=MOCK_TENANT_ID,
            jit_event_fields={
                "jit_event_id": "a27c47cb-f362-42af-9a92-984ffb3225b1",
                "asset_id": MOCK_ASSET_ID,
            }
        ),
    )

    with mock_eventbridge(bus_name=EXECUTION_EVENT_BUS_NAME) as get_sent_events:
        assert trigger_execution.handler({'detail': events.dict()}, None) is None

    sent_events = get_sent_events()

    mock_get_asset_by_id(asset_id=MOCK_ASSET_ID)
    mock_get_internal_token_api()
    mock_github_service_dispatch()
    mock_idempotent_decorator(
        mocker=mocker,
        module_to_reload=dispatch_execution,
        decorator_name="idempotent",
    )

    # Patch dispatch_execution to count calls
    dispatch_execution_mock = mocker.patch('src.handlers.dispatch_execution.dispatch_executions')

    # dispatch-execution's handler is invoked due to event submission to EventBridge
    execution_identifiers = sent_events[0]['detail']
    dispatch_execution.handler({"detail": execution_identifiers}, None)

    # Assert that all executions were dispatched at once
    assert dispatch_execution_mock.call_count == 1

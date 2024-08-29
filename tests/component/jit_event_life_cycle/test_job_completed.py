import json

import freezegun
import pytest
from jit_utils.event_models import JitEvent
from jit_utils.models.controls import ControlType
from jit_utils.models.execution import ExecutionStatus
from jit_utils.models.execution_context import Runner
from jit_utils.models.trigger.jit_event_life_cycle import JitEventStatus, JitEventLifeCycleEntity
from test_utils.aws import idempotency
from test_utils.aws.mock_eventbridge import mock_eventbridge

from src.lib.constants import JIT_EVENT_LIFE_CYCLE_EVENT_BUS_NAME, COMPLETED_JIT_EVENT_LIFE_CYCLE_EVENT_DETAIL_TYPE
from src.lib.models.jit_event_life_cycle import JitEventDBEntity, JitEventAssetDBEntity
from tests.component.conftest import setup_jit_event_life_cycle_in_db, FREEZE_TIME


def _setup_jit_event_life_cycle_asset_in_db(jit_event_life_cycle_manager, jit_event_mock, total_jobs):
    manager = jit_event_life_cycle_manager
    response = manager.create_jit_event_asset(
        tenant_id=jit_event_mock.tenant_id,
        jit_event_id=jit_event_mock.jit_event_id,
        asset_id=jit_event_mock.asset_id,
        total_jobs=total_jobs,
    )
    return response


@pytest.fixture
def job_completed_event(jit_event_mock) -> dict:
    return {
        'id': 'test-id',  # idempotency key
        'detail-type': 'test-detail-type',
        'detail': {
            'asset_id': jit_event_mock.asset_id,
            'jit_event_id': jit_event_mock.jit_event_id,
            'tenant_id': jit_event_mock.tenant_id,
            'control_type': ControlType.DETECTION,
            'execution_id': 'test-execution-id',
            'plan_item_slug': 'test-plan-item-slug',
            'workflow_slug': 'test-workflow-slug',
            'job_name': 'enrichment',
            'control_image': 'test-control-image',
            'jit_event_name': 'test-jit-event-name',
            'created_at': '2021-01-01T00:00:00.000000+00:00',
            'job_runner': Runner.GITHUB_ACTIONS,
            'plan_slug': 'test-plan-slug',
        }
    }


@pytest.fixture
def enrichment_watchdog_timeout_event(jit_event_mock: JitEvent) -> dict:
    return {
        'id': 'test-id',  # idempotency key
        'detail-type': 'test-detail-type',
        'detail': {
            'asset_id': jit_event_mock.asset_id,
            'jit_event_id': jit_event_mock.jit_event_id,
            'tenant_id': jit_event_mock.tenant_id,
            'control_type': ControlType.ENRICHMENT,
            'status': ExecutionStatus.WATCHDOG_TIMEOUT,
            'execution_id': 'test-execution-id',
            'plan_item_slug': 'test-plan-item-slug',
            'workflow_slug': 'test-workflow-slug',
            'job_name': 'enrichment',
            'control_image': 'test-control-image',
            'jit_event_name': 'test-jit-event-name',
            'created_at': '2021-01-01T00:00:00.000000+00:00',
            'job_runner': Runner.GITHUB_ACTIONS,
            'plan_slug': 'test-plan-slug',
        }
    }


@freezegun.freeze_time(FREEZE_TIME)
@pytest.mark.parametrize(
    "total_assets, total_jobs, expected_total_assets, expected_total_jobs",
    [
     (1, 1, 0, 0),  # last job and asset completed, cycle finished
     (1, 2, 1, 1),  # 1 job completed, some jobs remaining, cycle ongoing
     (1, 0, 0, 0)  # safeguard against negative values, cycle finished
    ]
    )
def test_handler(
        mocker,
        total_assets,
        total_jobs,
        expected_total_assets,
        expected_total_jobs,
        jit_event_life_cycle_manager,
        jit_event_mock,
        job_completed_event,
):
    """
    Test the handler function for successful completion of a jit event life cycle.

    Setup:
    - Mock dependencies and initialize database state using the following fixtures:
        - jit_event_life_cycle_manager: Manages jit event life cycle in the database.
        - jit_event_mock: Mock data for a jit event.
        - job_completed_event: Mocked job completion event data.
        - jit_event_life_cycle_table: DynamoDB table fixture for jit event life cycle.
    - The test simulates different scenarios based on 'total_assets' and 'total_jobs' parameters.
    - Mocks the 'idempotency' decorator.

    Test:
    - The `job_completed.handler` function is invoked with mocked event data.
    - It processes the completion of jit events and updates jit event and asset entities in the database.
    - The function also sends an event to the event bridge if the jit event life cycle is completed.

    Assert:
    - Validate that the jit event's remaining assets and jobs are updated in the database as expected.
    - Check if the appropriate event is sent to the event bridge, indicating the jit event's completion status.
    - The test covers cases where the jit event is completed, ongoing, and safeguards against negative values.

    Expected Outcome:
    - The database reflects the updated state of jit events and assets based on the test scenarios.
    - Event bridge receives an event only when the jit event life cycle is completed.
    """
    # must be mocked this way for the idempotency decorator to work properly
    from src.handlers import job_completed
    idempotency.mock_idempotent_decorator(
        mocker=mocker,
        module_to_reload=job_completed,
    )

    # Arrange
    test_event = job_completed_event
    expected_jit_event_mock, expected_jit_event_db_mock = setup_jit_event_life_cycle_in_db(
        jit_event_life_cycle_manager=jit_event_life_cycle_manager,
        jit_event_mock=jit_event_mock,
        total_assets=total_assets,
    )
    expected_jit_event_asset_mock = _setup_jit_event_life_cycle_asset_in_db(
        jit_event_life_cycle_manager=jit_event_life_cycle_manager,
        jit_event_mock=jit_event_mock,
        total_jobs=total_jobs,
    )

    # Act
    with mock_eventbridge(bus_name=[JIT_EVENT_LIFE_CYCLE_EVENT_BUS_NAME]) as get_events:
        job_completed.handler(test_event, None)
        # Check DB for expected state
        response = jit_event_life_cycle_manager.table.scan()
        assert len(response["Items"]) == 2

        # assert Jit Event
        jit_event_db_entity = JitEventDBEntity(**response["Items"][0])

        if expected_total_assets == 0 and expected_total_jobs == 0:
            expected_jit_event_db_mock.status = JitEventStatus.COMPLETED
        else:
            expected_jit_event_db_mock.status = JitEventStatus.STARTED

        expected_jit_event_db_mock.remaining_assets = expected_total_assets

        assert jit_event_db_entity == expected_jit_event_db_mock

        # assert Jit Event Asset
        jit_event_asset_db_entity = JitEventAssetDBEntity(**response["Items"][1])
        expected_jit_event_asset_mock.remaining_jobs = expected_total_jobs
        assert jit_event_asset_db_entity == expected_jit_event_asset_mock

        # assert Event Bridge Event
        events = get_events[JIT_EVENT_LIFE_CYCLE_EVENT_BUS_NAME]()
        if expected_total_assets == 0 and expected_total_jobs == 0:
            assert events[0]["detail-type"] == COMPLETED_JIT_EVENT_LIFE_CYCLE_EVENT_DETAIL_TYPE

            expected_event = JitEventLifeCycleEntity(**expected_jit_event_db_mock.dict())
            expected_event.modified_at = jit_event_db_entity.modified_at
            assert events[0]["detail"] == json.loads(expected_event.json())
        else:
            assert len(events) == 0


@freezegun.freeze_time(FREEZE_TIME)
def test_handler__with_failed_enrichment(
        mocker,
        jit_event_life_cycle_manager,
        jit_event_mock,
        enrichment_watchdog_timeout_event,
):
    """
    Test the handler function when enrichment fails asset completes in jit event life cycle.

    Setup:
    - Mock dependencies and initialize database state using the following fixtures:
        - jit_event_life_cycle_manager: Manages jit event life cycle in the database.
        - jit_event_mock: Mock data for a jit event.
        - enrichment_watchdog_timeout_event: Mocked job completion event data.
        - jit_event_life_cycle_table: DynamoDB table fixture for jit event life cycle.
    - Mocks the 'idempotency' decorator.

    Test:
    - The `job_completed.handler` function is invoked with mocked event data.
    - It processes the completion of jit events and updates jit event and asset entities in the database.
    - The function also sends an event to the event bridge that the jit event life cycle is completed.

    Assert:
    - Validate that the jit event's remaining assets and jobs are updated in the database as expected.
    - Check if the appropriate event is sent to the event bridge, indicating the jit event's completion status.
    - The test covers case where enrichment fails and asset run completes.

    Expected Outcome:
    - The database reflects the updated state of jit events and assets based on the test scenarios.
    - Event bridge receives an event only when the jit event life cycle is completed.
    """
    # must be mocked this way for the idempotency decorator to work properly
    from src.handlers import job_completed
    idempotency.mock_idempotent_decorator(
        mocker=mocker,
        module_to_reload=job_completed,
    )

    # Arrange
    test_event = enrichment_watchdog_timeout_event
    expected_jit_event_mock, expected_jit_event_db_mock = setup_jit_event_life_cycle_in_db(
        jit_event_life_cycle_manager=jit_event_life_cycle_manager,
        jit_event_mock=jit_event_mock,
        total_assets=1,
    )
    expected_jit_event_asset_mock = _setup_jit_event_life_cycle_asset_in_db(
        jit_event_life_cycle_manager=jit_event_life_cycle_manager,
        jit_event_mock=jit_event_mock,
        total_jobs=0,
    )

    # Act
    with mock_eventbridge(bus_name=[JIT_EVENT_LIFE_CYCLE_EVENT_BUS_NAME]) as get_events:
        job_completed.handler(test_event, None)
        # Check DB for expected state
        response = jit_event_life_cycle_manager.table.scan()
        assert len(response["Items"]) == 2

        # assert Jit Event
        jit_event_db_entity = JitEventDBEntity(**response["Items"][0])
        expected_jit_event_db_mock.remaining_assets = 0
        expected_jit_event_db_mock.status = JitEventStatus.COMPLETED
        assert jit_event_db_entity == expected_jit_event_db_mock

        # assert Jit Event Asset
        jit_event_asset_db_entity = JitEventAssetDBEntity(**response["Items"][1])
        expected_jit_event_asset_mock.remaining_jobs = 0
        assert jit_event_asset_db_entity == expected_jit_event_asset_mock

        # assert Event Bridge Event
        events = get_events[JIT_EVENT_LIFE_CYCLE_EVENT_BUS_NAME]()
        assert len(events) == 1
        expected_event = JitEventLifeCycleEntity(**expected_jit_event_db_mock.dict())
        expected_event.modified_at = jit_event_db_entity.modified_at
        assert events[0]["detail"] == json.loads(expected_event.json())
        assert events[0]["detail-type"] == COMPLETED_JIT_EVENT_LIFE_CYCLE_EVENT_DETAIL_TYPE

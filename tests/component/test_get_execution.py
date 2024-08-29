import json
from typing import List, Optional, Dict

from jit_utils.models.execution import Execution, ExecutionStatus

from src.handlers.get_executions import handler
from tests.component.fixtures import get_handler_event
from tests.conftest import convert_execution_to_execution_entity
from tests.mocks.execution_mocks import generate_mock_executions
from tests.mocks.tenant_mocks import MOCK_TENANT_ID


def seed_data(executions_table,
              events_amount: int = 10,
              jit_event_id: Optional[Dict] = None,
              job_name: str = 'job',
              status: ExecutionStatus = None,
              plan_item_slug: str = None):
    mock_executions = generate_mock_executions(events_amount, MOCK_TENANT_ID, single_jit_event_id=jit_event_id,
                                               job_name=job_name, status=status, plan_item_slug=plan_item_slug)
    mock_executions_entities = [convert_execution_to_execution_entity(mock) for mock in mock_executions]
    for execution in mock_executions_entities:
        executions_table.put_item(Item=execution.dict(exclude_none=True))

    return mock_executions


def build_event(status: str = None,
                plan_item_slug: str = None,
                limit: str = None,
                start_key: str = None,
                jit_event_id: str = None,
                asset_id: str = None,
                job_name: str = None,
                tenant_id: str = None,
                execution_id: str = None):
    query_params = {
        'status': status,
        'plan_item_slug': plan_item_slug,
        'limit': limit,
        'start_key': start_key,
        'jit_event_id': jit_event_id,
        'asset_id': asset_id,
        'job_name': job_name,
        'tenant_id': tenant_id,
        "execution_id": execution_id
    }
    query_params = {k: v for k, v in query_params.items() if v is not None}
    return get_handler_event(tenant_id=MOCK_TENANT_ID, query_string_parameters=query_params)


def compare_response_data_with_expected(expected: List[Execution], response):
    assert response['statusCode'] == 200
    response_content = json.loads(response['body'])
    assert response_content['metadata'] == {'count': 10, 'last_key': None}
    response_data = response_content['data']
    assert len(expected) == len(response_data)
    response_data_as_entities = [Execution(**record) for record in response_data]
    sorted_expected = sorted(expected, key=lambda x: x.execution_id)
    sorted_response_data = sorted(response_data_as_entities, key=lambda x: x.execution_id)
    assert sorted_expected == sorted_response_data


def test_get_executions__by_jit_event_id(executions_manager):
    # Setup
    jit_event_id = 'jit_event_id'
    mock_executions = seed_data(events_amount=10, executions_table=executions_manager.table, jit_event_id=jit_event_id)
    seed_data(events_amount=10, executions_table=executions_manager.table, jit_event_id='different_jit_event')

    # Test
    event = build_event(jit_event_id=jit_event_id)
    response = handler(event, None)

    # Assert
    compare_response_data_with_expected(mock_executions, response)


def test_get_executions__by_jit_event_id_and_job_name(executions_manager):
    # Setup
    jit_event_id = 'jit_event_id'
    job_name = 'job_name'
    mock_executions = seed_data(events_amount=10, executions_table=executions_manager.table,
                                jit_event_id=jit_event_id, job_name=job_name)
    seed_data(events_amount=10, executions_table=executions_manager.table, jit_event_id=jit_event_id,
              job_name='different_job_name')

    # Test
    event = build_event(jit_event_id=jit_event_id, job_name=job_name)
    response = handler(event, None)

    # Assert
    compare_response_data_with_expected(mock_executions, response)


def test_get_executions__by_status(executions_manager):
    mock_executions = seed_data(events_amount=10, executions_table=executions_manager.table,
                                status=ExecutionStatus.COMPLETED)
    seed_data(events_amount=10, executions_table=executions_manager.table, status=ExecutionStatus.FAILED)

    # Test
    event = build_event(status=ExecutionStatus.COMPLETED)
    response = handler(event, None)

    # Assert
    compare_response_data_with_expected(mock_executions, response)


def test_get_executions__by_plan_item_slug(executions_manager):
    mock_executions = seed_data(events_amount=10, executions_table=executions_manager.table,
                                plan_item_slug='plan_item_slug-123')
    seed_data(events_amount=10, executions_table=executions_manager.table, plan_item_slug='plan_item_slug-321')

    # Test
    event = build_event(plan_item_slug='plan_item_slug-123')
    response = handler(event, None)

    # Assert
    compare_response_data_with_expected(mock_executions, response)

import json
from typing import Optional

from jit_utils.models.trigger.jit_event_life_cycle import JitEventLifeCycleEntity

from src.handlers.get_jit_event import handler
from tests.component.conftest import setup_jit_event_life_cycle_in_db
from tests.component.utils.build_api_handler_event import build_api_handler_event


def build_event(tenant_id: str, jit_event_id: Optional[str]):
    return build_api_handler_event(tenant_id=tenant_id, path_parameters={'jit_event_id': jit_event_id})


def test_get_jit_event__happy_flow(jit_event_life_cycle_manager, jit_event_mock):
    """
    Test that we can get a Jit Event from the DB.
    Setup:
        - Create a Jit Event in the DB.
    Test:
        - Call the handler with the Jit Event ID and tenant ID.
    Verify:
        - The handler returns the Jit Event.
        - Status code is 200.
    """
    _, jit_event = setup_jit_event_life_cycle_in_db(
        jit_event_life_cycle_manager=jit_event_life_cycle_manager,
        jit_event_mock=jit_event_mock,
        total_assets=2,
    )
    tenant_id = jit_event.tenant_id
    event = build_event(tenant_id=tenant_id, jit_event_id=jit_event.jit_event_id)
    response = handler(event, None)

    assert response['statusCode'] == 200
    assert JitEventLifeCycleEntity(**json.loads(response['body'])) == JitEventLifeCycleEntity(**jit_event.dict())


def test_get_jit_event__wrong_jit_event_id(jit_event_life_cycle_manager, jit_event_mock):
    """
    Test handling of a wrong Jit Event ID.
    Setup:
        - Create a Jit Event in the DB.
    Test:
        - Call the handler with a wrong Jit Event ID and correct tenant ID.
    Verify:
        - The handler returns an error.
        - Status code is 404.
    """
    _, jit_event = setup_jit_event_life_cycle_in_db(
        jit_event_life_cycle_manager=jit_event_life_cycle_manager,
        jit_event_mock=jit_event_mock,
        total_assets=2,
    )
    tenant_id = jit_event.tenant_id
    event = build_event(tenant_id=tenant_id, jit_event_id='wrong_jit_event_id')
    response = handler(event, None)

    assert response['statusCode'] == 404
    assert json.loads(response['body']) == {
        'error': 'NOT_FOUND',
        'message': f"Jit Event not found for tenant_id='{tenant_id}', "
                   "jit_event_id='wrong_jit_event_id'",
    }


def test_get_jit_event__jit_event_belongs_to_different_tenant(jit_event_life_cycle_manager, jit_event_mock):
    """
    Test handling of a Jit Event that belongs to a different tenant.
    Setup:
        - Create a Jit Event in the DB.
    Test:
        - Call the handler with a different Tenant ID and correct Jit Event ID.
    Verify:
        - The handler returns an error.
        - Status code is 404.
    """
    _, jit_event = setup_jit_event_life_cycle_in_db(
        jit_event_life_cycle_manager=jit_event_life_cycle_manager,
        jit_event_mock=jit_event_mock,
        total_assets=2,
    )
    event = build_event(tenant_id='different_tenant_id', jit_event_id=jit_event.jit_event_id)
    response = handler(event, None)

    assert response['statusCode'] == 404
    assert json.loads(response['body']) == {
        'error': 'NOT_FOUND',
        'message': f"Jit Event not found for tenant_id='different_tenant_id', "
                   f"jit_event_id='{jit_event.jit_event_id}'",
    }


def test_get_jit_event__jit_event_id_not_passed(jit_event_life_cycle_manager, jit_event_mock):
    """
    Test handling of case when jit_event_id is not passed in path parameters.
    Setup:
        - Create a Jit Event in the DB.
    Test:
        - Call the handler with a wrong Tenant ID and without jit_event_id.
    Verify:
        - The handler returns an error.
        - Status code is 400.
    """
    _, jit_event = setup_jit_event_life_cycle_in_db(
        jit_event_life_cycle_manager=jit_event_life_cycle_manager,
        jit_event_mock=jit_event_mock,
        total_assets=2,
    )
    tenant_id = jit_event.tenant_id
    event = build_event(tenant_id=tenant_id, jit_event_id=None)
    response = handler(event, None)

    assert response['statusCode'] == 400
    assert json.loads(response['body']) == {
        'error': 'BAD_REQUEST',
        'message': "jit_event_id is required in path parameters"
    }

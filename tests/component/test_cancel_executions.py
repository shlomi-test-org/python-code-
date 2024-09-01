import uuid
from typing import List
from typing import Union

import responses
from jit_utils.jit_clients.plan_service.client import PlanService
from jit_utils.jit_clients.plan_service.endpoints import PLAN_SERVICE_GET_FULL_PLAN_CONTENT
from jit_utils.models.plan.template import PlanItemTemplateWithWorkflowsTemplates
from pydantic_factories import ModelFactory
from test_utils.aws import idempotency

import src
from src.lib.constants import JIT_PLAN_SLUG
from src.lib.cores.cancel_event_handler.asset_removed_handler import AssetRemovedEvent
from src.lib.cores.cancel_event_handler.asset_removed_handler import MinimalAsset
from src.lib.cores.cancel_event_handler.cancel_event_handler import CancelEventHandler
from src.lib.cores.cancel_event_handler.plan_item_deactivated_handler import PlanItemDeactivatedEvent
from src.lib.data.executions_manager import ExecutionsManager
from src.lib.endpoints import AUTH_SERVICE_GENERATE_LAMBDA_API_TOKEN
from jit_utils.models.execution import Execution
from tests.conftest import convert_execution_to_execution_entity
from tests.mocks.execution_mocks import generate_mock_executions
from tests.mocks.tenant_mocks import MOCK_TENANT_ID


class PlanItemTemplateWithWorkflowsTemplatesFactory(ModelFactory):
    __model__ = PlanItemTemplateWithWorkflowsTemplates


def get_asset_removed_events(count: int) -> List[AssetRemovedEvent]:
    return [
        AssetRemovedEvent(
            **dict(
                body=MinimalAsset(
                    tenant_id=MOCK_TENANT_ID,
                    asset_id=str(uuid.uuid4())
                )
            )
        ) for _ in range(0, count)
    ]


def get_plan_item_deactivated_events() -> List[PlanItemDeactivatedEvent]:
    return [
        PlanItemDeactivatedEvent(
            tenant_id=MOCK_TENANT_ID,
            plan_slug="jit-plan",
            plan_item_slug="plan_item_slug_1",
            is_active=False,
        ),
        PlanItemDeactivatedEvent(
            tenant_id=MOCK_TENANT_ID,
            plan_slug="jit-plan",
            plan_item_slug="plan_item_slug_2",
            is_active=False,
        ),
    ]


def create_test_executions(
        executions_manager: ExecutionsManager, events: List[Union[AssetRemovedEvent, PlanItemDeactivatedEvent]]
) -> List[Execution]:
    # creating executions in the DB with some slugs that are relevant
    mock_executions = generate_mock_executions(len(events) * 3, MOCK_TENANT_ID, plan_item_slug="plan_item_slug_3")
    mock_executions[-1].plan_item_slug = "plan_item_slug_4"
    # mark some plan_item_slugs that are deactivated in the test
    for i in range(0, len(events)):
        if isinstance(events[i], AssetRemovedEvent):
            mock_executions[i].asset_id = events[i].body.asset_id
            mock_executions[i + len(events)].asset_id = events[i].body.asset_id
        else:
            mock_executions[i].plan_item_slug = events[i].plan_item_slug
            mock_executions[i].affected_plan_items = list({events[i].plan_item_slug, "plan_item_slug_1"})
            mock_executions[i + len(events)].plan_item_slug = events[i].plan_item_slug

    mock_executions_entities = [convert_execution_to_execution_entity(mock) for mock in mock_executions]
    with executions_manager.table.batch_writer() as batch:
        for mock_executions_entity in mock_executions_entities:
            mock_executions_entity_dict = mock_executions_entity.dict(exclude_none=True)
            batch.put_item(Item=mock_executions_entity_dict)

    return mock_executions


def test_handle_cancel_event__bad_detail_type(executions_manager, mocker):
    idempotency.create_idempotency_table()
    from src.handlers.cancel_executions import handler

    get_cancel_event_handler_spy = mocker.spy(src.handlers.cancel_executions, "get_cancel_event_handler")

    mock_event_bridge_event = {
        "detail-type": "bad-detail-type",
        "detail": {},
        "id": str(uuid.uuid4()),
    }
    handler(mock_event_bridge_event, None)

    assert get_cancel_event_handler_spy.call_count == 0


def test_handle_cancel_event__bad_detail(executions_manager, mocker):
    idempotency.create_idempotency_table()
    from src.handlers.cancel_executions import handler

    get_cancel_event_handler_spy = mocker.spy(src.handlers.cancel_executions, "get_cancel_event_handler")
    handle_spy = mocker.spy(CancelEventHandler, "handle")

    mock_event_bridge_event = {
        "detail-type": "asset-not-covered",
        "detail": {},
        "id": str(uuid.uuid4()),
    }
    handler(mock_event_bridge_event, None)

    assert get_cancel_event_handler_spy.call_count == 1
    assert handle_spy.call_count == 0


def test_handle_cancel_event__asset_not_covered(executions_manager, mocker):
    idempotency.create_idempotency_table()
    from src.handlers.cancel_executions import handler

    assets_removed_count = 3

    asset_removed_events = get_asset_removed_events(assets_removed_count)
    create_test_executions(executions_manager, asset_removed_events)
    mock_send_task_completion_event = mocker.patch(
        "src.lib.cores.cancel_event_handler.cancel_event_handler.send_task_completion_event"
    )
    handle_spy = mocker.spy(CancelEventHandler, "handle")

    for event in asset_removed_events:
        mock_event_bridge_event = {
            "detail-type": "asset-not-covered",
            "detail": event.dict(),
            "id": str(uuid.uuid4()),
        }
        handler(mock_event_bridge_event, None)

    # assert results
    assert mock_send_task_completion_event.call_count == 2 * len(asset_removed_events)
    assert handle_spy.call_count == assets_removed_count

    # assert idempotency
    handler(mock_event_bridge_event, None)
    assert mock_send_task_completion_event.call_count == 2 * len(asset_removed_events)
    assert handle_spy.call_count == assets_removed_count


@responses.activate
def test_handle_cancel_event__plan_items_is_active(executions_manager, mocker):
    idempotency.create_idempotency_table()
    from src.handlers.cancel_executions import handler

    plan_item_deactivated_events = get_plan_item_deactivated_events()
    create_test_executions(executions_manager, plan_item_deactivated_events)
    mock_send_task_completion_event = mocker.patch(
        "src.lib.cores.cancel_event_handler.cancel_event_handler.send_task_completion_event"
    )
    handle_spy = mocker.spy(CancelEventHandler, "handle")
    responses.add(
        method=responses.POST,
        url=AUTH_SERVICE_GENERATE_LAMBDA_API_TOKEN.format(
            authentication_service="http://authentication-service"
        ),
        json="token",
    )
    responses.add(
        method=responses.GET,
        url=PLAN_SERVICE_GET_FULL_PLAN_CONTENT.format(
            plan_service=f"http://{PlanService.SERVICE_NAME}",
            plan_slug=JIT_PLAN_SLUG,
        ),
        json={
            "items": {
                "plan_item_slug_3": PlanItemTemplateWithWorkflowsTemplatesFactory.build().dict(),
                "plan_item_slug_4": PlanItemTemplateWithWorkflowsTemplatesFactory.build().dict(),
            }
        },
    )

    for event in plan_item_deactivated_events:
        mock_event_bridge_event = {
            "detail-type": "plan-items-is-active",
            "detail": event.dict(),
            "id": str(uuid.uuid4()),
        }
        handler(mock_event_bridge_event, None)

    # assert results
    executions_to_cancel_count = 4
    assert mock_send_task_completion_event.call_count == executions_to_cancel_count * len(plan_item_deactivated_events)
    assert handle_spy.call_count == 2

    # assert idempotency
    handler(mock_event_bridge_event, None)
    assert mock_send_task_completion_event.call_count == executions_to_cancel_count * len(plan_item_deactivated_events)
    assert handle_spy.call_count == 2

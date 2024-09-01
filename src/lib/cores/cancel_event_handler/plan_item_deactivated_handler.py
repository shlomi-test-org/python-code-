from typing import Dict
from typing import List

from jit_utils.event_models import JitEventName
from jit_utils.jit_clients.authentication_service.client import AuthenticationService
from jit_utils.jit_clients.plan_service.client import PlanService
from jit_utils.logger import logger
from jit_utils.models.execution import ExecutionStatus
from pydantic import BaseModel

from src.lib.constants import JIT_PLAN_SLUG
from src.lib.cores.cancel_event_handler.cancel_event_handler import CancelEventHandler
from src.lib.cores.executions_core import get_all_executions_by_filter
from src.lib.models.execution_models import Execution, ControlType
from src.lib.models.execution_models import GetExecutionsFilters


class PlanItemDeactivatedEvent(BaseModel):
    tenant_id: str
    plan_slug: str
    plan_item_slug: str
    is_active: bool


class PlanItemDeactivatedHandler(CancelEventHandler[PlanItemDeactivatedEvent]):
    def get_executions_to_cancel(self) -> List[Execution]:
        """
        This logic will start collecting 2 types of executions to cancel:
        1. pending executions from a workflow that are part of a plan item, that is not active anymore
        2. pending enrichment executions that were trigger as part of a plan item activation, that is not active anymore

        Note:
            this logic won't find enrichment executions that weren't part of plan item activation due to limitations of
            the enrichment execution creation (no connection to a plan_item_slug)
        """
        filters = GetExecutionsFilters(status=ExecutionStatus.PENDING)
        pending_executions = get_all_executions_by_filter(self.tenant_id, filters)
        if not pending_executions:
            logger.info(f"No pending executions found for tenant_id={self.tenant_id}, skipping event")
            return []

        active_plan_item_slugs = self._get_active_plan_item_slugs()
        return [
            execution
            for execution
            in pending_executions
            if PlanItemDeactivatedHandler._should_cancel_execution(active_plan_item_slugs, execution)
        ]

    @staticmethod
    def _should_cancel_execution(active_plan_item_slugs: List[str], execution: Execution) -> bool:
        if execution.control_type == ControlType.ENRICHMENT:
            if PlanItemDeactivatedHandler._should_cancel_enrichment_execution(active_plan_item_slugs, execution):
                # enrichment execution that was created from a plan item activation, and all plan items are inactive
                return True
        else:
            execution_plan_items = set(execution.affected_plan_items)
            execution_plan_items.add(execution.plan_item_slug)  # TODO: need to remove
            activated_plan_items_in_execution = [
                plan_item for plan_item in execution_plan_items if plan_item in active_plan_item_slugs
            ]
            if not activated_plan_items_in_execution:
                # execution from a workflow that is part of a deactivated plan item
                return True

        return False

    def _get_active_plan_item_slugs(self) -> List[str]:
        api_token = AuthenticationService().get_api_token(tenant_id=self.tenant_id)
        full_plan = PlanService().get_full_plan(api_token, JIT_PLAN_SLUG)
        return [plan_item_slug for plan_item_slug, plan_item in full_plan.items.items()]

    @staticmethod
    def _should_cancel_enrichment_execution(activated_plan_item_slugs: List[str], execution: Execution) -> bool:
        """
        This execution is enrichment, we should check if the jit event is ItemActivated and if so, check if all
        the activated plan item slugs are still relevant
        """
        return (
                execution.context.jit_event.jit_event_name == JitEventName.ItemActivated and
                not set(execution.context.jit_event.activated_plan_item_slugs) & set(activated_plan_item_slugs)
        )

    def parse_event_body(self, event_body: Dict) -> PlanItemDeactivatedEvent:
        return PlanItemDeactivatedEvent(**event_body)

    @property
    def tenant_id(self) -> str:
        return self._event_body.tenant_id

    def get_error_message(self) -> str:
        return "Item deactivated"

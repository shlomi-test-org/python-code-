from typing import List, Optional

from jit_utils.event_models import JitEvent
from jit_utils.jit_clients.authentication_service.client import AuthenticationService
from jit_utils.jit_clients.plan_service.client import PlanService
from jit_utils.jit_clients.tenant_service.client import TenantService
from jit_utils.logger import alert, logger
from jit_utils.models.plan.plan_file import FullPlanContent
from jit_utils.models.plan.template import PlanItemTemplateWithWorkflowsTemplates
from jit_utils.models.tenant.entities import Installation

from src.lib.clients.event_bridge_client import send_jit_event_processing_event
from src.lib.constants import JIT_PLAN_SLUG
from src.lib.cores.jit_event_handlers.job_filters import JobsProcessor
from src.lib.cores.jit_event_handlers.scm_validation import has_valid_scm_installation
from src.lib.cores.jit_event_handlers.workflow_filters import WorkflowsProcessor
from src.lib.exceptions import HandleJitEventException
from src.lib.models.trigger import WorkflowTemplateWrapper, JobTemplateWrapper, JitEventProcessingResources, \
    JitEventProcessingEventBridgeDetailType


class JitEventResourcesProcessor:
    # Cache installations to avoid fetching them multiple times.
    _installations: Optional[List[Installation]] = None

    def __init__(self, jit_event: JitEvent):
        self.jit_event = jit_event
        self.tenant_id = jit_event.tenant_id
        self.api_token = AuthenticationService().get_api_token(self.tenant_id)

    def fetch_resources(self) -> JitEventProcessingResources:
        plan = PlanService().get_full_plan(api_token=self.api_token, plan_slug=JIT_PLAN_SLUG)
        plan_items = self._filter_plan_items(plan)
        workflows = self._parse_workflows_and_filter(plan_items)
        jobs = self._parse_jobs_and_filter(workflows)
        return JitEventProcessingResources(
            jit_event=self.jit_event,
            installations=self._get_installations(),
            jobs=jobs,
            plan_depends_on_workflows=plan.depends_on
        )

    def _get_installations(self) -> List[Installation]:
        """
        Fetches all installations relevant to the current tenant.

        Returns:
            A list of Installation objects.
        """

        if self._installations is not None:
            return self._installations

        logger.info(f"Fetching installations for tenant {self.tenant_id}")
        installations = TenantService().get_installations(tenant_id=self.tenant_id, api_token=self.api_token)
        if not has_valid_scm_installation(installations):
            raise HandleJitEventException(message="Tenant does not have a valid SCM Installation")

        self._installations = installations
        return installations

    def _filter_plan_items(self, plan: FullPlanContent) -> List[PlanItemTemplateWithWorkflowsTemplates]:
        """
        Filters plan items for the jit event based on the plan item slugs trigger filter attribute.

        Returns:
            A list of PlanItemTemplateWithWorkflowsTemplates objects.
        """
        filter_slugs = self.jit_event.trigger_filter_attributes.plan_item_slugs
        plan_items = list(plan.items.values())
        if not filter_slugs:
            logger.info("No plan item slugs were provided for filtering. Proceed all plan items.")
            return plan_items

        filtered_plan_items = []
        for plan_item in plan_items:
            # If filtering is not required or the plan item's slug is in the filter list, add it to the filtered list.
            if plan_item.item_template.slug in filter_slugs:
                filtered_plan_items.append(plan_item)

        logger.info(f"After filtering plan items, we remained with: {len(filtered_plan_items)} plan items")
        return filtered_plan_items

    def _parse_workflows_and_filter(
            self,
            plan_items: List[PlanItemTemplateWithWorkflowsTemplates],
    ) -> List[WorkflowTemplateWrapper]:
        """
        Extracts and filters workflows from the plan items based on the current JIT event.

        Returns:
            A list of WorkflowTemplateWrapper objects.
        """
        return WorkflowsProcessor(self.jit_event).process_and_filter_workflows(plan_items)

    def _parse_jobs_and_filter(self, workflows: List[WorkflowTemplateWrapper]) -> List[JobTemplateWrapper]:
        """
        Extracts and filters jobs from the workflows based on the current JIT event.

        Returns:
            A list of JobTemplateWrapper objects.
        """
        return JobsProcessor(self.jit_event, self._get_installations()).process_and_filter_jobs(workflows)

    def send_resources_ready_event(self, resources: JitEventProcessingResources) -> None:
        """
        Sends a resource ready event to the jit event bus.
        """
        logger.info(f"Sending resources ready event for jit event {self.jit_event}")

        detail_type = None
        if resources.jit_event.trigger_filter_attributes.asset_ids:
            logger.info(f"Asset ids: {resources.jit_event.trigger_filter_attributes.asset_ids}")
            detail_type = JitEventProcessingEventBridgeDetailType.RUN_JIT_EVENT_BY_ASSET_IDS
        elif resources.jit_event.trigger_filter_attributes.asset_envs:
            logger.info(f"Asset envs: {resources.jit_event.trigger_filter_attributes.asset_envs}")
            detail_type = JitEventProcessingEventBridgeDetailType.RUN_JIT_EVENT_BY_DEPLOYMENT_ENV
        elif resources.jit_event.trigger_filter_attributes.plan_item_slugs:
            logger.info(f"Plan item slugs: {resources.jit_event.trigger_filter_attributes.plan_item_slugs}")
            detail_type = JitEventProcessingEventBridgeDetailType.RUN_JIT_EVENT_BY_ASSET_TYPES

        if detail_type:
            send_jit_event_processing_event(detail_type, resources.json())
        else:
            alert(message="Could not determine the detail type for the event. Skipping sending the event.",
                  alert_type="Jit Event Resources Processor Unknown Detail Type")

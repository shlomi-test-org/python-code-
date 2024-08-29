from itertools import chain
from typing import List

import yaml
from jit_utils.event_models import JitEvent
from jit_utils.logger import logger
from jit_utils.models.plan.template import PlanItemTemplateWithWorkflowsTemplates

from src.lib.constants import CONTENT, TRIGGER
from src.lib.cores.jit_event_handlers.trigger_filter import TriggerFilter
from src.lib.models.trigger import WorkflowTemplateWrapper


class WorkflowSlugsTriggerFilter(TriggerFilter[WorkflowTemplateWrapper]):
    def filter(self, elements: List[WorkflowTemplateWrapper]) -> List[WorkflowTemplateWrapper]:
        if not self.trigger_filters.workflow_slugs:
            return elements

        return [
            workflow
            for workflow in elements
            if workflow.workflow_slug in self.trigger_filters.workflow_slugs
        ]


class WorkflowTriggersTriggerFilter(TriggerFilter[WorkflowTemplateWrapper]):
    def filter(self, elements: List[WorkflowTemplateWrapper]) -> List[WorkflowTemplateWrapper]:
        if not self.trigger_filters.triggers:
            return elements

        filtered_workflows = []
        for workflow in elements:
            parsed_content_section = yaml.safe_load(workflow.raw_workflow_template.get(CONTENT, "")) or {}
            trigger_from_parsed_content = parsed_content_section.get(TRIGGER, {})
            trigger_from_jit_object = workflow.raw_workflow_template.get(TRIGGER, {})
            triggers_section = trigger_from_jit_object or trigger_from_parsed_content
            logger.info(f"triggers_section: {triggers_section}")
            # TODO: Fix bad chaining of non triggers to triggers for filtering
            #  (https://app.shortcut.com/jit/story/18641/trigger-service-handle-jit-event-leftovers)
            template_filters = set(chain(*triggers_section.values()))

            if self.trigger_filters.triggers.intersection(template_filters):
                filtered_workflows.append(workflow)
        return filtered_workflows


class WorkflowsProcessor:
    def __init__(self, jit_event: JitEvent):
        self.jit_event = jit_event
        self.slugs_filter = WorkflowSlugsTriggerFilter(jit_event)
        self.triggers_filter = WorkflowTriggersTriggerFilter(jit_event)

    def process_and_filter_workflows(
            self,
            plan_items: List[PlanItemTemplateWithWorkflowsTemplates],
    ) -> List[WorkflowTemplateWrapper]:
        workflows = []
        for plan_item in plan_items:
            logger.info(f"Processing plan item: {plan_item.item_template.slug}")
            for workflow_template in plan_item.workflow_templates:
                wrapper = WorkflowTemplateWrapper(
                    plan_item_slug=plan_item.item_template.slug,
                    workflow_slug=workflow_template.slug,
                    workflow_name=workflow_template.name,
                    depends_on_slugs=workflow_template.depends_on,
                    raw_workflow_template=workflow_template.dict(),
                )
                if self.is_workflow_relevant(wrapper):
                    workflows.append(wrapper)
        logger.info(f"After processing and filtering, remained with: {len(workflows)} workflows")
        return workflows

    def is_workflow_relevant(self, workflow: WorkflowTemplateWrapper) -> bool:
        logger.info(f"Checking if workflow {workflow.workflow_slug} is relevant")
        # check if workflow passes the slugs filter
        if not self.slugs_filter.filter([workflow]):
            return False
        # check if workflow passes the triggers filter
        if not self.triggers_filter.filter([workflow]):
            return False
        logger.info(f"Workflow {workflow.workflow_slug} is relevant")
        return True

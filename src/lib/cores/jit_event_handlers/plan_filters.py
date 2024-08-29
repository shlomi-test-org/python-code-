from typing import List

from jit_utils.models.plan.template import PlanItemTemplateWithWorkflowsTemplates

from src.lib.cores.jit_event_handlers.trigger_filter import TriggerFilter


class PlanItemsTriggerFilter(TriggerFilter[PlanItemTemplateWithWorkflowsTemplates]):
    def filter(
            self, elements: List[PlanItemTemplateWithWorkflowsTemplates]
    ) -> List[PlanItemTemplateWithWorkflowsTemplates]:
        if not self.trigger_filters.plan_item_slugs:
            return elements

        return [
            plan_item
            for plan_item in elements
            if plan_item.item_template.slug in self.trigger_filters.plan_item_slugs
        ]

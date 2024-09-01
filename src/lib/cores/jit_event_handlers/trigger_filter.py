from abc import ABC, abstractmethod
from typing import TypeVar, Generic, List

from jit_utils.event_models import JitEvent
from jit_utils.event_models.common import TriggerFilterAttributes
from jit_utils.models.asset.entities import Asset
from jit_utils.models.plan.template import PlanItemTemplateWithWorkflowsTemplates

from src.lib.models.trigger import WorkflowTemplateWrapper, JobTemplateWrapper

TriggerFilterTypes = TypeVar("TriggerFilterTypes",
                             Asset,
                             PlanItemTemplateWithWorkflowsTemplates,
                             WorkflowTemplateWrapper,
                             JobTemplateWrapper)


class TriggerFilter(ABC, Generic[TriggerFilterTypes]):
    def __init__(self, jit_event: JitEvent):
        self.jit_event = jit_event
        self.tenant_id = jit_event.tenant_id
        self.trigger_filters: TriggerFilterAttributes = jit_event.trigger_filter_attributes

    @abstractmethod
    def filter(self, items_to_filter: List[TriggerFilterTypes]) -> List[TriggerFilterTypes]:
        raise NotImplementedError

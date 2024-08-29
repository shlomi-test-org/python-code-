from enum import Enum
from typing import Dict
from typing import List, Any, Optional, Union

import yaml
from jit_utils.event_models import JitEventTypes, CodeRelatedJitEvent
from jit_utils.event_models.common import TriggerFilterAttributes
from jit_utils.event_models.event_trigger_scheme import WorkflowTriggerScheme, JobTriggerScheme
from jit_utils.event_models.trigger_event import TriggerExecutionEvent
from jit_utils.jit_event_names import JitEventName
from jit_utils.logger import logger
from jit_utils.models.execution_context import RepoEnrichmentResult
from jit_utils.models.tenant.entities import Installation
from pydantic import BaseModel, validator, Extra

from src.lib.constants import STEPS, TAGS, SECURITY_TOOL, RUNNER, CONTENT, JOBS
from src.lib.models.asset import Asset
from src.lib.utils import get_old_runner_format


class RawJobTemplate(BaseModel):
    steps: List[Dict[str, Any]]
    tags: List[str]
    security_tool: str
    runner: str


class JobTemplateWrapper(BaseModel):
    plan_item_slug: str
    workflow_slug: str
    workflow_name: str
    job_name: str
    workflow_template: Dict
    raw_job_template: Dict
    depends_on_slugs: List[str] = []

    @property
    def security_tool(self) -> str:
        try:
            return self.raw_job_template.get(STEPS, [])[0].get(TAGS, {}).get(SECURITY_TOOL, '')
        except IndexError:
            return ''

    def workflow_trigger_scheme(self) -> WorkflowTriggerScheme:
        return WorkflowTriggerScheme(
            workflow_slug=self.workflow_slug,
            workflow_name=self.workflow_name,
            asset_trigger_schemes={},
            plan_item_slug=self.plan_item_slug
        )

    def get_runner(self) -> str:
        return get_old_runner_format(self.raw_job_template.get(RUNNER, ''))

    def job_trigger_scheme(self) -> JobTriggerScheme:
        return JobTriggerScheme(
            job_name=self.job_name,
            runner=self.get_runner(),
            security_tool=self.security_tool
        )


class WorkflowTemplateWrapper(BaseModel):
    plan_item_slug: str
    workflow_slug: str
    workflow_name: str
    depends_on_slugs: List[str] = []
    raw_workflow_template: Dict

    @property
    def jobs(self) -> Dict[str, Dict]:
        """
        Returns a dictionary of jobs in the workflow template.
        If the workflow has no content, an exception is raised - workflow template file should not be empty.
        If the workflow template has no jobs, an empty dictionary is returned.
        """
        content = yaml.safe_load(self.raw_workflow_template[CONTENT])
        if not content:
            raise ValueError(f"Workflow {self.workflow_slug} has no content")

        return content[JOBS]


class WorkflowTemplate(BaseModel):
    slug: str
    name: str
    depends_on: List[str] = []
    content: str
    params: Optional[Dict] = None
    plan_item_template_slug: Optional[str] = None
    asset_types: Optional[List[str]] = None

    class Config:
        extra = Extra.ignore


EnrichedData = Dict[str, List]  # Required in the prepare-for-execution lambda
ModeledEnrichedData = Union[RepoEnrichmentResult]


class PrepareForExecutionEvent(BaseModel):
    """
    PrepareForExecutionEvent is a model for event received from handle-jit-event.
    """
    jit_event: JitEventTypes
    trigger_filter_attributes: TriggerFilterAttributes
    asset: Asset  # Required in the prepare-for-execution lambda
    installations: List[Installation]
    filtered_jobs: List[JobTemplateWrapper]
    should_enrich: bool = False
    depends_on_workflows_templates: List[WorkflowTemplate] = []
    enriched_data: EnrichedData = {}

    @validator("enriched_data", pre=True)
    def validate_enriched_data(cls, v: Dict) -> Dict:
        """
        Remove epsagon tracing from step function result to avoid serialization issues
        """
        if "Epsagon" in v:
            v.pop("Epsagon")
        return v

    @property
    def relevant_installation(self) -> Optional[Installation]:
        for installation in self.installations:
            if self.asset.vendor == installation.vendor and self.asset.owner == installation.owner:
                logger.info(f"Found relevant {installation=} for the event")
                return installation
        logger.info(f"No installation for the event, vendor={self.asset.vendor}, owner={self.asset.owner}")
        return None


class PrepareForExecutionEventWithEnrichedData(BaseModel):
    prepare_for_execution_event: PrepareForExecutionEvent
    enriched_data: EnrichedData = {}

    @validator("enriched_data", pre=True)
    def validate_enriched_data(cls, v: Dict) -> Dict:
        """
        Remove epsagon tracing from step function result to avoid serialization issues
        """
        if "Epsagon" in v:
            v.pop("Epsagon")
        return v


class EnrichAsyncResponse(BaseModel):
    prepare_for_execution_event: PrepareForExecutionEvent
    trigger_enrich_execution: TriggerExecutionEvent


class JitEventProcessingResources(BaseModel):
    jit_event: JitEventTypes
    installations: List[Installation]
    jobs: List[JobTemplateWrapper]
    plan_depends_on_workflows: Dict[str, WorkflowTemplate]

    def __init__(self, **data) -> None:  # type: ignore
        super().__init__(**data)
        # In case of a merge default branch event, we don't want to keep the PR details.
        if (isinstance(self.jit_event, CodeRelatedJitEvent) and
                self.jit_event.jit_event_name == JitEventName.MergeDefaultBranch):
            self.jit_event.pull_request_number = None
            self.jit_event.pull_request_title = None
            self.jit_event.commits.head_sha = None
            self.jit_event.commits.base_sha = ""


class JitEventProcessingEventBridgeDetailType(str, Enum):
    RUN_JIT_EVENT_BY_ASSET_IDS = "run-jit-event-on-assets-by-ids"
    RUN_JIT_EVENT_BY_ASSET_TYPES = "run-jit-event-on-assets-by-types"
    RUN_JIT_EVENT_BY_DEPLOYMENT_ENV = "run-jit-event-on-assets-by-deployment-env"


class JitEventAssetsOrchestratorStatus(str, Enum):
    SUCCESS = "success"
    FILTERED_ALL_ASSETS = "all assets were filtered from the event"

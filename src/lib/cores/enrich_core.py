from typing import List

from jit_utils.event_models import JitEvent
from jit_utils.event_models.common import TriggerFilterAttributes
from jit_utils.event_models.trigger_event import TriggerExecutionEvent
from jit_utils.logger import logger

from src.lib.constants import (
    PLACEHOLDER_PLAN_ITEM_SLUG,
)
from src.lib.cores.handle_jit_event_core_utils.workflows_templates_filters import filter_jobs
from src.lib.cores.prepare_for_execution_core import create_trigger_events
from src.lib.models.trigger import (
    PrepareForExecutionEvent,
    JobTemplateWrapper,
    WorkflowTemplateWrapper,
    WorkflowTemplate,
)


def generate_trigger_execution_events(
        prepare_for_execution_event: PrepareForExecutionEvent
) -> List[TriggerExecutionEvent]:
    trigger_enrich_execution_events = []
    for depends_on_workflow_template in prepare_for_execution_event.depends_on_workflows_templates:
        prepare_for_enrich_execution_event = _generate_enrich_prepare_for_execution_event(
            prepare_for_execution_event, depends_on_workflow_template
        )
        logger.info(f"Generated {prepare_for_enrich_execution_event=}")
        trigger_events = create_trigger_events(prepare_for_enrich_execution_event)
        trigger_enrich_execution_events.extend(trigger_events)
    logger.info(f"Generated {trigger_enrich_execution_events=}")

    return trigger_enrich_execution_events


def _generate_enrich_prepare_for_execution_event(
        original_prepare_for_execution_event: PrepareForExecutionEvent,
        depends_on_workflow_template: WorkflowTemplate,
) -> PrepareForExecutionEvent:
    filtered_jobs: List[JobTemplateWrapper] = _get_filtered_jobs_from_filtered_workflows(
        filtered_workflows=[
            WorkflowTemplateWrapper(
                plan_item_slug=PLACEHOLDER_PLAN_ITEM_SLUG,
                workflow_slug=depends_on_workflow_template.slug,
                workflow_name=depends_on_workflow_template.name,
                raw_workflow_template=depends_on_workflow_template.dict(),
            )
        ],
        jit_event=original_prepare_for_execution_event.jit_event,
        trigger_filter_attributes=original_prepare_for_execution_event.trigger_filter_attributes,
    )
    return PrepareForExecutionEvent(
        jit_event=original_prepare_for_execution_event.jit_event,
        trigger_filter_attributes=original_prepare_for_execution_event.trigger_filter_attributes,
        asset=original_prepare_for_execution_event.asset,
        installations=original_prepare_for_execution_event.installations,
        filtered_jobs=filtered_jobs,
    )


def _get_filtered_jobs_from_filtered_workflows(
        filtered_workflows: List[WorkflowTemplateWrapper],
        jit_event: JitEvent,
        trigger_filter_attributes: TriggerFilterAttributes,
) -> List[JobTemplateWrapper]:
    filtered_jobs = []
    for filtered_workflow in filtered_workflows:
        workflow_filtered_jobs = filter_jobs(
            filtered_workflow.jobs, trigger_filter_attributes, jit_event
        )
        for job_name, raw_job_template in workflow_filtered_jobs.items():
            filtered_jobs.append(
                JobTemplateWrapper(
                    plan_item_slug=filtered_workflow.plan_item_slug,
                    workflow_slug=filtered_workflow.workflow_slug,
                    workflow_name=filtered_workflow.workflow_name,
                    job_name=job_name,
                    depends_on_slugs=filtered_workflow.depends_on_slugs,
                    workflow_template=filtered_workflow.raw_workflow_template,
                    raw_job_template=raw_job_template,
                )
            )

    return filtered_jobs

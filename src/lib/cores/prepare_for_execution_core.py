import re
from datetime import datetime
from typing import Dict, List, Tuple, Optional

from jit_utils.aws_clients.events import EventBridgeClient
from jit_utils.event_models import JitEventName, JitEvent, JitEventTypes
from jit_utils.event_models.event_trigger_scheme import EventTriggerScheme, AssetTriggerScheme
from jit_utils.event_models.trigger_event import (
    BulkTriggerExecutionEvent,
    TriggerExecutionEvent,
    TriggerScheme,
    BulkTriggerSchemeEvent,
)
from jit_utils.jit_clients.plan_service.client import PlanService
from jit_utils.logger import logger
from jit_utils.models.execution import ControlType
from jit_utils.models.execution_context import (
    Centralized,
    WorkflowJob,
    RunnerConfig,
    ExecutionContext,
    ExecutionContextWorkflow,
)
from jit_utils.models.tenant.entities import Installation
from jit_utils.utils.plan_utils.evaluate_workflow_dynamic_variables import evaluate_interpolations
from jit_utils.jit_event_names import PR_RELATED_JIT_EVENTS
from pydantic import parse_obj_as

from src.lib.clients import PlanService as PlanServiceOld
from src.lib.constants import (
    TRIGGER_EXECUTION_BUS_NAME,
    TRIGGER_EXECUTION_DETAIL_TYPE_TRIGGER_EVENT,
    TRIGGER_MAX_BULK_SIZE,
    TRIGGER_SERVICE,
    TRIGGER_EXECUTION_DETAIL_TYPE_TRIGGER_SCHEME,
    ASSET_TYPE,
    YAML_IF_CONDITION,
    STEPS,
    INTEGRATIONS,
    RUNNER,
    JIT_PLAN_SLUG,
)
from src.lib.cores.jit_event_life_cycle.jit_event_life_cycle_handler import JitEventLifeCycleHandler
from src.lib.cores.prepare_for_execution_core_utils.source_asset_extraction import extract_source_asset_from_event
from src.lib.data.enrichment_results_table import EnrichmentResultsManager
from src.lib.exceptions import WorkflowJobNotInFilteredJobsException
from src.lib.models.asset import Asset
from src.lib.models.enrichment_results import BaseEnrichmentResultsItem
from src.lib.models.trigger import JobTemplateWrapper, EnrichedData, ModeledEnrichedData
from src.lib.models.trigger import PrepareForExecutionEvent
from src.lib.utils import get_old_runner_format, get_tenant_api_token


def prepare_for_execution_core(event: PrepareForExecutionEvent) -> List[TriggerExecutionEvent]:
    """
    Prepare for execution core.
    This function does a second filtering for the jobs and then for the assets.
    When Enrichment control runs a full scan, store the enriched data in the EnrichmentResults table.
    Then, it calls the _prepare_for_execution which build and push the trigger_scheme events and the
    TriggerExecution events.
    :param event: the event to which we should prepare the list of TriggerExecutionEvents
    """
    if event.enriched_data:
        logger.info(f"Enriched data is available, using it for filtering: {event.enriched_data}")
        event.filtered_jobs = _filter_jobs_by_enriched_data(event.filtered_jobs, event.enriched_data)

        # Store the enriched data ONLY IF FileContent enrichment was executed on the whole repository.
        # TODO: For now, we still do this for the MERGE_TO_MAIN event, this should be change once handling this event (change PR_RELATED_JIT_EVENTS to JIT_EVENTS_WITH_DIFF_BASED_ENRICHMENT)  # noqa
        if event.should_enrich and event.jit_event.jit_event_name not in PR_RELATED_JIT_EVENTS:
            item = BaseEnrichmentResultsItem(
                tenant_id=event.asset.tenant_id,
                vendor=event.asset.vendor,
                owner=event.asset.owner,
                repo=event.asset.asset_name,
                enrichment_results=event.enriched_data,
                jit_event_id=event.jit_event.jit_event_id,
                jit_event_name=event.jit_event.jit_event_name,
            )
            EnrichmentResultsManager().create_results_for_repository(item)

    event.filtered_jobs = _dedup_jobs(event.filtered_jobs)

    logger.info(f"Received {len(event.filtered_jobs)} Filtered jobs: {event.filtered_jobs}")
    if not event.filtered_jobs:

        trigger_execution_events = []
    else:
        _send_pipeline_events(prepare_for_execution_event=event)
        trigger_execution_events = create_trigger_events(prepare_for_execution_event=event)

    number_of_jobs_to_trigger = len(trigger_execution_events)
    logger.info(f"Number of jobs to trigger: {number_of_jobs_to_trigger}")
    JitEventLifeCycleHandler().filtered_jobs_to_execute(
        tenant_id=event.jit_event.tenant_id,
        jit_event_id=event.jit_event.jit_event_id,
        asset_id=event.asset.asset_id,
        total_jobs=number_of_jobs_to_trigger,
    )

    return trigger_execution_events


def _get_filtered_assets(
        assets: List[Asset], filtered_jobs: List[JobTemplateWrapper]
) -> List[Asset]:
    """
    Filter assets by the trigger filter attributes
    This array doesn't contain duplicates
    """
    filtered_assets = []
    for filtered_job in filtered_jobs:
        for asset in assets:
            if asset.asset_type == filtered_job.raw_job_template[ASSET_TYPE]:
                filtered_assets.append(asset)

    if not filtered_assets:
        return []
    # remove duplication - same asset_id
    filtered_assets_dedupe = list({asset.asset_id: asset for asset in filtered_assets}.values())
    return filtered_assets_dedupe


def create_trigger_events(prepare_for_execution_event: PrepareForExecutionEvent) -> List[TriggerExecutionEvent]:
    trigger_execution_events = [
        _create_trigger_execution_event(prepare_for_execution_event, job)
        for job in prepare_for_execution_event.filtered_jobs
    ]

    return trigger_execution_events


def _send_pipeline_events(prepare_for_execution_event: PrepareForExecutionEvent) -> None:
    # we should send trigger scheme event (to create pipelines)
    event_trigger_scheme_for_pipeline = _get_event_trigger_scheme(
        prepare_for_execution_event.filtered_jobs,
        prepare_for_execution_event.asset,
        prepare_for_execution_event.relevant_installation,
    )
    amount_of_jobs = event_trigger_scheme_for_pipeline.amount_of_triggered_jobs
    logger.info(f"Amount of jobs in scheme for pipeline: {amount_of_jobs}")
    _send_trigger_scheme_events(
        prepare_for_execution_event.jit_event,
        event_trigger_scheme_for_pipeline,
        [prepare_for_execution_event.asset],
    ) if (amount_of_jobs > 0) else []


def _dedup_jobs(jobs: List[JobTemplateWrapper]) -> List[JobTemplateWrapper]:
    collected_jobs = set()
    filtered_jobs = []
    logger.info(f"Dedupping list of jobs={[f'{job.workflow_slug}.{job.job_name}' for job in jobs]}")
    for job in jobs:
        if (job.workflow_slug, job.job_name) in collected_jobs:
            logger.info(f"{job.workflow_slug}.{job.job_name} already collected, dedupping")
            continue
        filtered_jobs.append(job)
        collected_jobs.add((job.workflow_slug, job.job_name))

    logger.info(f"{filtered_jobs=}")
    return filtered_jobs


def _filter_jobs_by_enriched_data(
        jobs: List[JobTemplateWrapper],
        enriched_data: EnrichedData,
) -> List[JobTemplateWrapper]:
    filtered_jobs = []
    for job in jobs:
        if _should_run_job_by_enriched_data(job.raw_job_template, enriched_data):
            filtered_jobs.append(job)
    return filtered_jobs


def _should_run_job_by_enriched_data(raw_job_template: Dict, enriched_data: EnrichedData) -> bool:
    """
    This function checks if the job should run by the enriched data.
    1. The job has a filter attribute
    2. The filter attribute exists is in the enriched data
    3. One of the filter attribute values is in the enriched data corresponding value
    """

    conditions = raw_job_template.get(YAML_IF_CONDITION)

    if not conditions or not isinstance(conditions, Dict):
        logger.info(f"conditions are empty or not a dict: {conditions}, running job")
        return True

    # Relevant only when the PrepareForExecutionEvent was initiated without enriched_data which resulted in an empty
    # dict. When enrichment runs in the CI, it won't be an empty dict, But rather a dict of keys such as languages, etc.
    if not enriched_data:
        logger.info("Enriched Data is empty, running job")
        return True

    for key in conditions:
        if key in enriched_data:
            conditions_set = set(conditions[key])
            enriched_data_set = set(enriched_data[key])
            common = conditions_set.intersection(enriched_data_set)
            if len(common) > 0:
                # if there is at least one common value, we don't filter out the job since condition is met
                return True

    return False


def parse_condition(condition: str) -> Optional[Tuple[str, str]]:
    """
    Parse the condition to a tuple of (filter_name, filter_value)
    """
    validate_condition_regex = r"'([A-Za-z0-9_]*)' *in *\$\{\{ *event\.metadata\.([A-Za-z0-9_]*) *\}\}"
    pattern = re.compile(validate_condition_regex, re.IGNORECASE)
    if not (match := pattern.match(condition)):
        logger.error(f"Condition {condition} is not valid")
        return None
    # The field ref is in the form of ${{event.metadata.field_name}} so we need to remove the brackets and
    # the event.metadata part
    required_tag = match.group(1).strip()
    filter_name = match.group(2).strip()
    return required_tag, filter_name


def _get_event_trigger_scheme(
        filtered_jobs: List[JobTemplateWrapper],
        asset: Asset,
        installation: Optional[Installation],
) -> EventTriggerScheme:
    logger.info(f"Creating trigger scheme for job names {[job.job_name for job in filtered_jobs]}")
    event_trigger_scheme = EventTriggerScheme(workflow_trigger_schemes={})
    for filtered_job in filtered_jobs:
        if _get_control_type(filtered_job.job_name) in [ControlType.BACKGROUND, ControlType.ENRICHMENT]:
            logger.info(f"job={filtered_job.job_name} so be filtered from trigger scheme - skipping")
            continue

        if filtered_job.workflow_slug not in event_trigger_scheme.workflow_trigger_schemes:
            workflow_trigger_scheme = filtered_job.workflow_trigger_scheme()
            event_trigger_scheme.workflow_trigger_schemes[filtered_job.workflow_slug] = workflow_trigger_scheme

        workflow_trigger_scheme = event_trigger_scheme.workflow_trigger_schemes[filtered_job.workflow_slug]
        if asset.asset_id not in workflow_trigger_scheme.asset_trigger_schemes:
            asset_trigger_scheme = _create_asset_trigger_scheme(asset, installation)
            workflow_trigger_scheme.asset_trigger_schemes[asset.asset_id] = asset_trigger_scheme

        asset_trigger_scheme = workflow_trigger_scheme.asset_trigger_schemes[asset.asset_id]
        asset_trigger_scheme.job_trigger_schemes[filtered_job.job_name] = filtered_job.job_trigger_scheme()

    return event_trigger_scheme


def _split_event_trigger_scheme_by_asset(
        event_trigger_scheme: EventTriggerScheme, assets: List[Asset]
) -> List[EventTriggerScheme]:
    event_trigger_scheme_by_asset: Dict[str, EventTriggerScheme] = {}
    logger.info(f"Splitting trigger scheme by asset {assets=}")
    for asset in assets:
        event_trigger_scheme_by_asset[asset.asset_id] = EventTriggerScheme(
            workflow_trigger_schemes={}
        )
        for (
                workflow_slug,
                workflow_trigger_scheme,
        ) in event_trigger_scheme.workflow_trigger_schemes.items():
            if asset.asset_id in workflow_trigger_scheme.asset_trigger_schemes:
                workflows_of_asset = workflow_trigger_scheme.copy(
                    exclude={"asset_trigger_schemes"}
                )
                workflows_of_asset.asset_trigger_schemes = {
                    asset.asset_id: workflow_trigger_scheme.asset_trigger_schemes[
                        asset.asset_id
                    ]
                }
                event_trigger_scheme_by_asset[asset.asset_id].workflow_trigger_schemes[
                    workflow_slug
                ] = workflows_of_asset

    return list(event_trigger_scheme_by_asset.values())


def _create_asset_trigger_scheme(asset: Asset, installation: Optional[Installation]) -> AssetTriggerScheme:
    asset_trigger_scheme = AssetTriggerScheme(
        asset_id=asset.asset_id,
        asset_name=asset.asset_name,
        asset_type=asset.asset_type,
        vendor=asset.vendor,
        owner=asset.owner,
        environment=asset.environment,
        installation_id=installation.installation_id if installation else None,
        job_trigger_schemes={},
    )
    return asset_trigger_scheme


def send_trigger_scheme_event(bulk_trigger_schemes: BulkTriggerSchemeEvent) -> None:
    logger.info("Sending bulk trigger schemes event")
    EventBridgeClient().put_event(
        source=TRIGGER_SERVICE,
        bus_name=TRIGGER_EXECUTION_BUS_NAME,
        detail_type=TRIGGER_EXECUTION_DETAIL_TYPE_TRIGGER_SCHEME,
        detail=bulk_trigger_schemes.json(),
    )


def _get_centralized_repo_files_metadata(
        jit_event: JitEventTypes
) -> Centralized:
    centralized_repo_files_metadata = PlanServiceOld().get_centralized_repo_files_metadata(
        jit_event.tenant_id
    )

    return Centralized(centralized_repo_files_location=centralized_repo_files_metadata.centralized_repo_files_location,
                       ci_workflow_files_path=centralized_repo_files_metadata.ci_workflow_files_path)


def _get_control_type(job_name: str) -> ControlType:
    """
    THIS IS A TEMPORARY SOLUTION!
    Currently, we have no way to know the control type before the control is starting to run (since it's declared in the
    control level).
    We need to know the type on early stages, so that's why we pushed this *BAD* solution, until we have a better
    mechanism to track controls properties.
    """
    enrichment_job_name = "enrich"
    if enrichment_job_name in job_name:
        return ControlType.ENRICHMENT

    remediation_job_name = "remediation"
    if remediation_job_name in job_name:
        return ControlType.REMEDIATION

    background_job_names = ["sbom", "reporter", "software-bill-of-materials", "analyze", "pull-issues", "push-findings"]
    if any(name in job_name.lower() for name in background_job_names):
        return ControlType.BACKGROUND
    return ControlType.DETECTION


def _create_trigger_execution_event(
        prepare_for_execution_event: PrepareForExecutionEvent,
        job: JobTemplateWrapper,
) -> TriggerExecutionEvent:
    logger.info("creating context")
    scopes = PlanService().get_plan_items_scopes(
        api_token=get_tenant_api_token(prepare_for_execution_event.jit_event.tenant_id),
        workflow_slug=job.workflow_slug,
        job_name=job.job_name,
    )
    execution_context = create_execution_context(
        asset=prepare_for_execution_event.asset,
        installation=prepare_for_execution_event.relevant_installation,
        workflow=ExecutionContextWorkflow(**job.workflow_template),
        job_name=job.job_name,
        job_template=job.raw_job_template,
        jit_event=prepare_for_execution_event.jit_event,
        enrichment_result=prepare_for_execution_event.enriched_data,
    )
    logger.info(f"context created, {execution_context}")
    job_template = job.raw_job_template
    trigger_execution_event = TriggerExecutionEvent(
        context=execution_context,
        plan_slug=JIT_PLAN_SLUG,
        plan_item_slug=job.plan_item_slug,
        affected_plan_items=[scope.plan_item_slug for scope in scopes],
        workflow_slug=job.workflow_slug,
        job_name=job.job_name,
        steps=job_template[STEPS],
        created_at=datetime.utcnow().isoformat(),
        job_runner=get_old_runner_format(job_template[RUNNER]),
        jit_event=prepare_for_execution_event.jit_event,
        control_type=_get_control_type(job.job_name),
    )

    logger.info(f"Created trigger execution event: {trigger_execution_event}")
    return trigger_execution_event


def _get_job(filtered_jobs: List[JobTemplateWrapper], workflow_slug: str, job_name: str) -> JobTemplateWrapper:
    for job in filtered_jobs:
        if job.workflow_slug == workflow_slug and job.job_name == job_name:
            return job
    raise WorkflowJobNotInFilteredJobsException(filtered_jobs, workflow_slug, job_name)


def get_runner_config(job_template: dict) -> RunnerConfig:
    runner = job_template[RUNNER]
    try:
        return RunnerConfig(**runner)
    except TypeError:
        # For supporting runners which are just a string (old flow before context)
        return RunnerConfig(type=runner)


def create_execution_context(
        asset: Asset,
        installation: Optional[Installation],
        workflow: ExecutionContextWorkflow,
        job_name: str,
        job_template: Dict,
        jit_event: JitEventTypes,
        enrichment_result: Dict,
) -> ExecutionContext:
    api_token = get_tenant_api_token(jit_event.tenant_id)

    tenant_id = jit_event.tenant_id
    config_file_content = PlanServiceOld().get_configuration_file_for_tenant(api_token=api_token, tenant_id=tenant_id)
    integration_file_content = PlanServiceOld().get_integration_file_for_tenant(
        api_token=api_token, tenant_id=tenant_id
    )

    initial_context = ExecutionContext(
        jit_event=jit_event,
        asset=asset,
        installation=installation,
        config=config_file_content,
        integration=integration_file_content,
        job=WorkflowJob(
            runner=get_runner_config(job_template),
            job_name=job_name,
            condition=job_template.get(YAML_IF_CONDITION),
            integrations=job_template.get(INTEGRATIONS),
            steps=job_template[STEPS],
        ),
        centralized=get_centralized_data(jit_event),
        workflow=workflow,
        enrichment_result=parse_obj_as(ModeledEnrichedData, enrichment_result) if enrichment_result else None,
    )

    return ExecutionContext(**evaluate_interpolations(initial_context, {}, initial_context.dict()))  # type: ignore


def get_centralized_data(jit_event: JitEventTypes) -> Centralized:
    if not jit_event.dict().get("centralized_repo_files_location"):
        # To handle ItemActivatedJitEvent that does not have the centralized metadata keys.
        return _get_centralized_repo_files_metadata(jit_event)

    return Centralized(
        centralized_repo_files_location=jit_event.centralized_repo_files_location,  # type: ignore
        ci_workflow_files_path=jit_event.ci_workflow_files_path,  # type: ignore
    )


def _send_trigger_scheme_events(
        jit_event: JitEvent,
        event_trigger_scheme: EventTriggerScheme,
        filtered_assets: List[Asset],
) -> List[BulkTriggerSchemeEvent]:
    if jit_event.jit_event_name not in [
        JitEventName.NonProductionDeployment,
        JitEventName.ProductionDeployment,
    ]:
        logger.info(
            f"Sending multiple trigger scheme events for {jit_event.jit_event_name}"
        )
        event_trigger_schemes_to_send = _split_event_trigger_scheme_by_asset(
            event_trigger_scheme, filtered_assets
        )
    else:
        event_trigger_schemes_to_send = [event_trigger_scheme]
    # build trigger scheme events
    trigger_scheme_events = [
        TriggerScheme(
            jit_event=jit_event,
            event_execution_scheme=event_trigger_scheme,
            source_asset=extract_source_asset_from_event(jit_event),
        )
        for event_trigger_scheme in event_trigger_schemes_to_send
    ]
    return _send_trigger_scheme_bulk_events(jit_event, trigger_scheme_events)


def send_trigger_execution_events(
        tenant_id: str,
        jit_event_name: JitEventName,
        trigger_execution_events: List[TriggerExecutionEvent],
) -> None:
    job_names_to_trigger = {event.job_name for event in trigger_execution_events}
    logger.info(
        f"Sending trigger execution events, amount={len(trigger_execution_events)}, {job_names_to_trigger=}"
    )

    for i in range(0, len(trigger_execution_events), TRIGGER_MAX_BULK_SIZE):
        bulk_events_to_trigger = BulkTriggerExecutionEvent(
            tenant_id=tenant_id,
            jit_event_name=jit_event_name,
            executions=trigger_execution_events[i:i + TRIGGER_MAX_BULK_SIZE],  # fmt: skip
        )

        EventBridgeClient().put_event(
            source=TRIGGER_SERVICE,
            bus_name=TRIGGER_EXECUTION_BUS_NAME,
            detail_type=TRIGGER_EXECUTION_DETAIL_TYPE_TRIGGER_EVENT,
            detail=bulk_events_to_trigger.json(),
        )


def _send_trigger_scheme_bulk_events(
        jit_event: JitEvent, trigger_schemes: List[TriggerScheme]
) -> List[BulkTriggerSchemeEvent]:
    """
    The method sends the event of all the executions to be created consisting of the trigger schemes of each execution.
    """
    logger.info(f"Sending trigger scheme events, amount={len(trigger_schemes)}")
    bulk_trigger_schemes: List[BulkTriggerSchemeEvent] = []
    for i in range(0, len(trigger_schemes), TRIGGER_MAX_BULK_SIZE):
        bulk_events_to_trigger = BulkTriggerSchemeEvent(
            tenant_id=jit_event.tenant_id,
            jit_event_name=jit_event.jit_event_name,
            trigger_schemes=trigger_schemes[i:i + TRIGGER_MAX_BULK_SIZE],  # fmt: skip
        )
        bulk_trigger_schemes.append(bulk_events_to_trigger)
        send_trigger_scheme_event(bulk_events_to_trigger)
    return bulk_trigger_schemes

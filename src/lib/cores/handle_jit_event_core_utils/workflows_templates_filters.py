from collections import defaultdict
from itertools import chain
from typing import List, Dict, Callable, Tuple, Set

import yaml
from jit_utils.event_models import JitEvent, CodeRelatedJitEvent
from jit_utils.logger import logger
from jit_utils.models.asset.entities import Asset
from jit_utils.models.tenant.entities import Installation

from src.lib.constants import SLUG, TRIGGER, TAGS, LANGUAGES, ASSETS_TYPES_WITH_INSTALLATIONS, CONTENT
from src.lib.cores.filter_evaluators.filter_evaluators_manager import FiltersEvaluatorsManager
from jit_utils.event_models.common import TriggerFilterAttributes


def group_active_assets_by_type(assets: List[Asset]) -> Dict[str, List[Asset]]:
    assets_by_type: Dict[str, List[Asset]] = defaultdict(list)
    for asset in assets:
        if asset.is_active and asset.is_covered:
            assets_by_type[asset.asset_type].append(asset)

    return assets_by_type


def filter_assets_by_event_type_and_env(
        triggers: Set[str],
        asset_envs: Set[str],
        assets: List[Asset],
        api_token: str,
        tenant_id: str
) -> List[Asset]:
    """
    Checks if there are evaluators that should react to the given event
    If so, they call the PlanService to get the needed configurations
    And from those configurations, we get the relevant assets.
    Arguments:
        triggers: set of strings, currently we support one trigger at a time
        asset_envs: set of strings, currently we support one trigger at a time
        assets: List of asset models, need to filtered, not all are relevant (potentially)
        api_token: Previously generated token for internal api use
        tenant_id: The user unique tenant_id
    Returns:
        The relevant assets according to trigger and env
    """
    logger.info(f'Filtering existing: {len(assets)} assets according to given: {triggers=} and {asset_envs=}')
    specific_trigger = next(iter(triggers or []), None)  # Currently we support one trigger per event
    specific_env = next(iter(asset_envs or []), None)  # Currently we support one env per event

    if not specific_trigger or not specific_env:
        logger.info("Not received trigger or env, not currently supported")
        return assets

    filtered_assets = FiltersEvaluatorsManager(api_token, tenant_id).filter(specific_trigger, specific_env, assets)
    logger.info(f'Post filtering, we remained with: {len(filtered_assets)} assets')
    return filtered_assets


def filter_assets(
        assets: List[Asset],
        trigger_filter_attributes: TriggerFilterAttributes,
        installations: Dict[Tuple[str, str], Installation],
        api_token: str,
        tenant_id: str
) -> List[Asset]:
    """
    This function filters out an asset if:
    1. asset id is not in the list of trigger_executions_filter.asset_ids (if this list is non-empty)
    2. asset env is not in the list of trigger_executions_filter.asset_envs (if this list is non-empty)
    3. asset requires installation, but does have one.
    """
    asset_ids, asset_envs = trigger_filter_attributes.asset_ids, trigger_filter_attributes.asset_envs
    filtered_assets = []

    for asset in assets:
        if asset_ids and asset.asset_id not in asset_ids:
            continue

        if asset.asset_type in ASSETS_TYPES_WITH_INSTALLATIONS and (asset.vendor, asset.owner) not in installations:
            continue

        filtered_assets.append(asset)

    filtered_assets = filter_assets_by_event_type_and_env(
        triggers=trigger_filter_attributes.triggers,
        asset_envs=asset_envs,
        assets=filtered_assets,
        api_token=api_token,
        tenant_id=tenant_id
    )

    return filtered_assets


def filter_plan(plan: Dict, trigger_filter_attributes: TriggerFilterAttributes) -> Dict:
    """
    This function filters out the plan items that their slugs do not appear in
    trigger_executions_filter.plan_item_slugs (if this list is non-empty).
    """
    logger.info(f"Filter plan according to {trigger_filter_attributes=}")
    if not trigger_filter_attributes.plan_item_slugs:
        return plan

    return {
        plan_item_slug: plan[plan_item_slug]
        for plan_item_slug in trigger_filter_attributes.plan_item_slugs
        if plan_item_slug in plan
    }


def _should_filter_out_by_jit_event_based_on_triggers(
        jit_obj_to_filter: Dict,
        trigger_executions_filter: TriggerFilterAttributes,
        **kwargs: Dict
) -> bool:
    """
    This function will filter out the job iff:
    1. There is a non-empty triggers section in the job itself and there is a non-empty triggers list in the filter
    2. There is no intersection between the triggers in the job and the triggers in the filter
    """

    requested_triggers = trigger_executions_filter.triggers
    if not requested_triggers:
        return False

    parsed_content_section = yaml.safe_load(jit_obj_to_filter.get(CONTENT, "")) or {}
    trigger_from_parsed_content = parsed_content_section.get(TRIGGER, {})
    trigger_from_jit_object = jit_obj_to_filter.get(TRIGGER, {})
    triggers_section = trigger_from_jit_object or trigger_from_parsed_content
    logger.info(f"triggers_section: {triggers_section}")
    template_filters = set(chain(*triggers_section.values()))

    if not template_filters:
        return False

    return not requested_triggers.intersection(template_filters)


def _should_filter_out_job_by_jit_event_based_on_tags(
        jit_obj_to_filter: Dict,
        jit_event: JitEvent,
        **kwargs: Dict
) -> bool:
    """
    This function is only interesting for code related jit events (o.w. will return False).
    If there are tags to the job template, we filter based on the languages.
    We will probably extend this functionality when we support more third part events.
    """

    if not isinstance(jit_event, CodeRelatedJitEvent):
        return False

    if not (tags := jit_obj_to_filter.get(TAGS, {})):
        return False

    if languages := tags.get(LANGUAGES):
        return not set(languages).intersection(set(jit_event.languages))

    return False


def should_filter_out_job_by_jit_event(
        job: Dict,
        jit_event: JitEvent,
        trigger_filter_attributes: TriggerFilterAttributes
) -> bool:
    """
    This function filters out the job iff one of the above job execution filters returns True.
    """
    JOB_EXCLUSION_FILTERS: List[Callable] = [
        _should_filter_out_by_jit_event_based_on_triggers,
    ]

    return any(
        job_exclusion_filter(
            jit_obj_to_filter=job,
            jit_event=jit_event,
            trigger_executions_filter=trigger_filter_attributes
        )
        for job_exclusion_filter in JOB_EXCLUSION_FILTERS
    )


def filter_jobs(
        jobs: Dict[str, Dict],
        trigger_filter_attributes: TriggerFilterAttributes,
        jit_event: JitEvent
) -> Dict[str, Dict]:
    """
    This function filters out the jobs that their job_names does not appear in
    trigger_executions_filter.job_names (if this list is non-empty).

    It also filters out jobs based on the triggers, tags and languages.
    """

    requested_jobs_names = trigger_filter_attributes.job_names
    filtered_jobs_names = requested_jobs_names.intersection(jobs) if requested_jobs_names else set(jobs)

    result_jobs: Dict[str, Dict] = {}
    for job_name in filtered_jobs_names:
        if should_filter_out_job_by_jit_event(jobs[job_name], jit_event, trigger_filter_attributes):
            logger.info(f'Filtering out job {job_name} based on jit event')
            continue

        result_jobs[job_name] = jobs[job_name]

    return result_jobs


def filter_workflows(
        workflows_list: List[Dict],
        trigger_executions_filter: TriggerFilterAttributes,
) -> List[Dict]:
    """
    This function filters out the workflows that their slugs do not appear in
    trigger_executions_filter.workflow_slugs (if this list is non-empty).

    However, there is another possibility that we want to filter out the workflows:
    If there is a section of triggers in the workflow we filter out based on the triggers requested.
    """

    if not trigger_executions_filter.workflow_slugs and not trigger_executions_filter.triggers:
        return workflows_list

    result_workflows: List[Dict] = []
    for workflow in workflows_list:
        if trigger_executions_filter.workflow_slugs and workflow[SLUG] not in trigger_executions_filter.workflow_slugs:
            logger.info(f'Filtering out workflow {workflow[SLUG]} based on workflow slugs')
            continue

        if _should_filter_out_by_jit_event_based_on_triggers(workflow, trigger_executions_filter):
            logger.info(f'Filtering out workflow {workflow[SLUG]} based on triggers')
            continue

        result_workflows.append(workflow)

    return result_workflows

from pathlib import Path
from typing import Dict, List, Tuple, Set

from jit_utils.enrichment.code_enrichment import file_name_enrichment
from jit_utils.enrichment.logics.files import FilenameEnrichmentNotSupported
from jit_utils.event_models import JitEvent, CodeRelatedJitEvent
from jit_utils.event_models.common import TriggerFilterAttributes
from jit_utils.jit_clients.scm_service.client import ScmServiceClient
from jit_utils.jit_clients.tenant_service.client import TenantService
from jit_utils.jit_clients.tenant_service.exceptions import InstallationNotFoundException
from jit_utils.jit_event_names import PR_RELATED_JIT_EVENTS
from jit_utils.logger import logger, alert
from jit_utils.models.asset.entities import Asset
from jit_utils.models.jit_files.jit_config import ResourceManagement
from jit_utils.models.oauth.entities import VendorEnum
from jit_utils.models.tenant.entities import Installation

from src.lib.constants import ASSET_TYPE, JIT_EVENTS_WITH_DIFF_BASED_ENRICHMENT
from src.lib.cores.resource_management_utils import is_asset_excluded_from_plan_item_slug
from src.lib.data.enrichment_results_db_models import EnrichmentResultsItemNotFoundError
from src.lib.data.enrichment_results_table import EnrichmentResultsManager
from src.lib.models.enrichment_results import BaseEnrichmentResultsItem, PrEnrichmentResultsItem
from src.lib.models.trigger import JobTemplateWrapper
from src.lib.models.trigger import PrepareForExecutionEvent


def _filter_assets_based_on_filter_jobs(
        grouped_assets: Dict[str, List[Asset]],  # asset_type -> List[Asset]
        filtered_jobs: List[JobTemplateWrapper],  # List of the jobs that should run
) -> List[Asset]:
    """
    This function filters out assets that haven't any job to run on them -> calculated by asset_type.
    Then, it returns a list of the assets that have at least one job to run on them, deduplicated.
    """
    filtered_assets = {}
    for filtered_job in filtered_jobs:
        asset_type = filtered_job.raw_job_template[ASSET_TYPE]
        relevant_assets = grouped_assets.get(asset_type, [])
        for asset in relevant_assets:
            if asset.asset_id not in filtered_assets:
                filtered_assets[asset.asset_id] = asset
    return list(filtered_assets.values())


def _filter_jobs_based_on_exclusion(
        filtered_jobs: List[JobTemplateWrapper], asset: Asset, resource_management: ResourceManagement
) -> List[JobTemplateWrapper]:
    """
    Filter jobs based on exclusion section in jit-config.yml
    """
    logger.info(f"Filtering jobs based on exclusion {filtered_jobs=} {asset=} {resource_management=}")
    if not resource_management.exclude:  # No jobs to exclude
        return filtered_jobs

    filtered_jobs_after_exclusion = []
    for filtered_job in filtered_jobs:
        if not is_asset_excluded_from_plan_item_slug(asset, filtered_job.plan_item_slug, resource_management):
            filtered_jobs_after_exclusion.append(filtered_job)
    logger.info(f"Filtered jobs after exclusion {filtered_jobs_after_exclusion}")
    return filtered_jobs_after_exclusion


def _build_prepare_for_execution_event_for_asset(
        asset: Asset,
        trigger_filter_attributes: TriggerFilterAttributes,
        jit_event: JitEvent,
        filtered_jobs: List[JobTemplateWrapper],
        installations: List[Installation],
        depends_on_workflows: Dict[str, Dict],
) -> PrepareForExecutionEvent:
    """
    This function builds a PrepareForExecutionEvent for a specific asset.
    As part of the process, it also finds the depends_on workflows for the jobs, and inserts them into the event.
    """
    # First, check if enrichment is needed based on the workflows
    depends_on_slugs = _get_depends_on_slugs_of_jobs(filtered_jobs)
    depends_on_workflows_list = []
    should_enrich = False
    enriched_data = {}
    for slug in depends_on_slugs:
        if not depends_on_workflows.get(slug):
            logger.error(f"Could not find workflow with slug {slug}")
        else:
            depends_on_workflows_list.append(depends_on_workflows[slug])
            should_enrich = True

    # Second, if should_enrich is True, and this is a PR event attempt to do FileContent enrichment based on changed
    # paths in the PR
    if (
            should_enrich and
            isinstance(jit_event, CodeRelatedJitEvent) and
            jit_event.jit_event_name in PR_RELATED_JIT_EVENTS
    ):
        scm_client = ScmServiceClient(vendor=VendorEnum(jit_event.vendor))

        # Attempt to do filename enrichment
        try:
            # Get the paths of all files that were added/modified/changed in the PR
            changed_filenames = scm_client.get_pr_change_list(
                tenant_id=jit_event.tenant_id,
                owner=jit_event.owner,  # type: ignore
                repo=jit_event.original_repository,
                pr_number=int(jit_event.pull_request_number),  # type: ignore
            )
            logger.info(f"Changed filenames: {changed_filenames}")
            enriched_data = file_name_enrichment(filepaths=[Path(p) for p in changed_filenames]).dict()

        except FilenameEnrichmentNotSupported as e:
            # It's ok even if filename enrichment didn't work, as default should_enrich is set to True from before
            # which will lead to File Content Enrichment
            logger.info(f"Filename enrichment didn't work: {e}")
        except Exception as e:
            logger.error(f"Unexpected error while enriching filenames in a PR: {e}")
            alert(f"Unexpected error while enriching filenames in a PR for tenant {jit_event.tenant_id}: {e}")
        else:
            logger.info(f"Filename enrichment worked: {enriched_data}")
            should_enrich = False

            EnrichmentResultsManager().create_results_for_pr(
                item=PrEnrichmentResultsItem(
                    tenant_id=jit_event.tenant_id,
                    vendor=jit_event.vendor,
                    owner=jit_event.owner,
                    repo=jit_event.original_repository,
                    enrichment_results=enriched_data,
                    jit_event_id=jit_event.jit_event_id,
                    jit_event_name=jit_event.jit_event_name,
                    pr_number=int(jit_event.pull_request_number),  # type: ignore
                    head_sha=jit_event.commits.head_sha,  # type: ignore
                )
            )

    if should_enrich and jit_event.jit_event_name not in JIT_EVENTS_WITH_DIFF_BASED_ENRICHMENT:
        try:
            item: BaseEnrichmentResultsItem = EnrichmentResultsManager().get_results_for_repository(
                tenant_id=asset.tenant_id,
                vendor=asset.vendor,
                owner=asset.owner,
                repo=asset.asset_name,
            )
            enriched_data = item.enrichment_results
            should_enrich = False
            logger.info(f"Successfully fetched {enriched_data=}")
        except EnrichmentResultsItemNotFoundError:
            logger.info("Enriched results not found, building PrepareForExecutionEvent with should_enrich=True")

    return PrepareForExecutionEvent(
        trigger_filter_attributes=trigger_filter_attributes,
        jit_event=jit_event,
        filtered_jobs=filtered_jobs,
        asset=asset,
        installations=installations,
        depends_on_workflows_templates=depends_on_workflows_list,
        should_enrich=should_enrich,
        enriched_data=enriched_data,
    )


def _get_depends_on_slugs_of_jobs(jobs: List[JobTemplateWrapper]) -> List[str]:
    depends_on_slugs = set()

    for job in jobs:
        depends_on_slugs.update(job.depends_on_slugs)
    return list(depends_on_slugs)


def _group_jobs_by_asset_type(jobs: List[JobTemplateWrapper]) -> Dict[str, List[JobTemplateWrapper]]:
    """
    This function groups jobs by asset_type.
    """
    grouped_jobs: Dict[str, List[JobTemplateWrapper]] = {}
    for job in jobs:
        asset_type = job.raw_job_template[ASSET_TYPE]
        grouped_jobs.setdefault(asset_type, []).append(job)
    return grouped_jobs


def _get_tenant_installations_grouped_by_vendor_and_owner(
        tenant_id: str, api_token: str, vendors: Set[str]
) -> Dict[Tuple[str, str], Installation]:
    if not vendors:
        return {}

    installations_by_vendor_and_owner = {}
    client = TenantService()
    for vendor in vendors:
        try:
            vendor_installations = client.get_installations_by_vendor(
                vendor=vendor, tenant_id=tenant_id, api_token=api_token
            )
        except InstallationNotFoundException:
            vendor_installations = []
            logger.info(f"Failed to get installations for tenant {tenant_id} vendor {vendor}")
        for installation in vendor_installations:
            installations_by_vendor_and_owner[
                (vendor, installation.owner)
            ] = installation

    return installations_by_vendor_and_owner

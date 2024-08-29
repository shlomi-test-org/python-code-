import os
import sys
from datetime import datetime
from typing import List, Dict

from jit_utils.aws_clients.sfn import SFNClient
from jit_utils.jit_clients.asset_service.client import AssetService
from jit_utils.jit_clients.asset_service.exceptions import (
    AssetNotFoundException,
    RequestValidationException,
    UnhandledException,
)
from jit_utils.jit_clients.authentication_service.client import AuthenticationService
from jit_utils.logger import alert, logger
from jit_utils.logger.logger import add_label
from jit_utils.models.asset.entities import Asset
from jit_utils.models.jit_files.jit_config import ResourceManagement
from pydantic import parse_obj_as

from src.lib.clients import PlanService as OldPlanServiceClient
from src.lib.constants import PAYLOAD_WARNING_THRESHOLD
from src.lib.cores.handle_jit_event_core import (
    _build_prepare_for_execution_event_for_asset,
    _filter_jobs_based_on_exclusion,
    _group_jobs_by_asset_type,
    _filter_assets_based_on_filter_jobs,
)
from src.lib.cores.handle_jit_event_core_utils.workflows_templates_filters import (
    group_active_assets_by_type,
)
from src.lib.cores.jit_event_handlers.asset_filters import (
    AssetWithInstallationTriggerFilter,
    AssetIdsTriggerFilter,
    AssetByTriggersAndEnvTriggerFilter,
)
from src.lib.cores.jit_event_life_cycle.jit_event_life_cycle_handler import (
    JitEventLifeCycleHandler,
)
from src.lib.data.enrichment_results_table import EnrichmentResultsManager
from src.lib.exceptions import HandleJitEventException
from src.lib.models.trigger import (
    JobTemplateWrapper,
    JitEventProcessingResources,
    PrepareForExecutionEvent,
    WorkflowTemplate,
    JitEventAssetsOrchestratorStatus,
)


class JitEventAssetsOrchestrator:
    def __init__(self, jit_event_resources: JitEventProcessingResources):
        self.tenant_id = jit_event_resources.jit_event.tenant_id
        self.api_token = AuthenticationService().get_api_token(self.tenant_id)
        self.jit_event = jit_event_resources.jit_event
        self.installations = jit_event_resources.installations
        self.jobs = jit_event_resources.jobs
        self.plan_depends_on_workflows = jit_event_resources.plan_depends_on_workflows

    def run_jit_event_on_assets(self) -> JitEventAssetsOrchestratorStatus:
        # Bring all tenant assets and filter them
        assets = self._get_all_assets()
        if assets:
            self.execute_scan_on_assets(assets)
            return JitEventAssetsOrchestratorStatus.SUCCESS
        elif self.jit_event.trigger_filter_attributes.asset_ids:
            raise HandleJitEventException(message=f"Got asset_ids {self.jit_event.trigger_filter_attributes.asset_ids} "
                                                  f"but no assets at all")
        return JitEventAssetsOrchestratorStatus.FILTERED_ALL_ASSETS

    def _filter_and_group_assets_by_type(self, assets: List[Asset]) -> Dict[str, List[Asset]]:
        logger.info(f"Sanitizing {len(assets)} assets")
        for asset in assets:
            _remove_high_payload_properties_from_asset(asset)

        filtered_assets = self._filter_assets_to_run_on(assets)
        if not filtered_assets:
            logger.warning("No assets to run for jit event")
            add_label('no_assets_after_filter', '')

        grouped_assets = group_active_assets_by_type(filtered_assets)
        logger.info(f"Grouped assets types {list(grouped_assets)}")
        if not grouped_assets:
            logger.warning("No active/covered assets to run")
            add_label('no_assets_after_group_filter', '')

        return grouped_assets

    def _get_all_assets(self) -> Dict[str, List[Asset]]:
        assets = self._get_assets()
        return self._filter_and_group_assets_by_type(assets)

    def get_assets_by_ids(self) -> Dict[str, List[Asset]]:
        asset_ids = self.jit_event.trigger_filter_attributes.asset_ids
        assets = AssetService().get_assets_by_ids(
            api_token=self.api_token,
            asset_ids=list(asset_ids),
        )
        return self._filter_and_group_assets_by_type(assets)

    def _get_assets(self) -> List[Asset]:
        """
        Fetches all assets relevant to the current tenant.

        Returns:
            A list of Asset objects.

        Raises:
            HandleJitEventException: An exception is raised if no assets are found.
        """
        try:
            assets = parse_obj_as(List[Asset], AssetService().get_all_assets(self.tenant_id, self.api_token))
        except (AssetNotFoundException, RequestValidationException, UnhandledException) as e:
            raise HandleJitEventException(message=str(e))

        logger.info(f"Assets amount fetched: {len(assets)}")
        return assets

    def execute_scan_on_assets(self, assets: Dict[str, List[Asset]]) -> None:
        events = self.generate_prepare_for_execution_event_per_asset(assets, self.jobs, self.plan_depends_on_workflows)
        self.trigger_events(events)

    def _filter_assets_to_run_on(self, assets: List[Asset]) -> List[Asset]:
        """
        Fetches and filters relevant assets for the execution based on the current JIT event.

        It groups active assets by their types and raises an exception if no relevant assets are found.

        Returns:
            A dictionary with asset types as keys and a list of assets as values.

        Raises:
            HandleJitEventException: An exception is raised if no relevant assets are found.
        """

        filtered_assets = AssetWithInstallationTriggerFilter(self.jit_event,
                                                             self.api_token,
                                                             self.installations).filter(assets)
        filtered_assets = AssetIdsTriggerFilter(self.jit_event).filter(filtered_assets)
        filtered_assets = AssetByTriggersAndEnvTriggerFilter(self.jit_event, self.api_token).filter(filtered_assets)
        logger.info(f"Assets amount after filtering: {len(filtered_assets)}")
        return filtered_assets

    def generate_prepare_for_execution_event_per_asset(
            self,
            assets: Dict[str, List[Asset]],
            jobs: List[JobTemplateWrapper],
            plan_depends_on: Dict[str, WorkflowTemplate],
    ) -> List[PrepareForExecutionEvent]:
        """
        Given a dictionary of assets and a list of job templates, this function generates a list of execution events
        prepared for these jobs on the provided assets.

        This function works through several steps:
            1. It checks if the jit security check should be opened for the jobs.
            2. Filters assets based on the jobs that need to be run.
            3. Groups the filtered jobs by asset type.
            4. Iterates over each asset, filters jobs based on exclusion conditions, and creates
               a PrepareForExecutionEvent for each asset.
            5. If there are no jobs to run or if an exception occurs, it appropriately handles the
               situation and may raise a HandleJitEventException.

        Args:
            assets (Dict[str, List[Asset]]): Dictionary mapping asset types to a list of asset objects.
                Each asset object corresponds to a system or resource where jobs should be executed.

            jobs (List[JobTemplateWrapper]): List of job templates. Each JobTemplateWrapper represents
                a job that needs to be run, along with the necessary metadata (e.g., workflow details,
                dependencies, job parameters).

            plan_depends_on (Dict[str, WorkflowTemplate]): Dictionary mapping workflow template slugs to
                WorkflowTemplate objects. Each WorkflowTemplate object represents a workflow template
                that the jobs depend on.

        Returns:
            List[PrepareForExecutionEvent]: A list of PrepareForExecutionEvent objects.
                Each PrepareForExecutionEvent represents an instance of a job ready to be executed on
                a specific asset, along with necessary context such as trigger filter attributes,
                the JIT event itself, and job and asset details.

        Raises:
            HandleJitEventException: An exception is raised if the preparations for executions fail.
                This could be due to an error in generating execution events for the jobs on the
                provided assets.
    """
        prepare_for_execution_executions_events: List[PrepareForExecutionEvent] = []

        # TODO: remove filtering and grouping of assets by jobs and use list of Assets only.
        #  https://app.shortcut.com/jit/story/18641/trigger-service-handle-jit-event-leftovers
        filtered_assets = _filter_assets_based_on_filter_jobs(assets, jobs)
        logger.info(f"Filtered assets by asset type and filtered jobs {filtered_assets=}")
        grouped_filtered_jobs_by_asset_type = _group_jobs_by_asset_type(jobs)
        resource_management_section = _get_resource_management_section(self.api_token, self.tenant_id)

        latest_enrichment_results = EnrichmentResultsManager().get_results_for_repositories_batch(filtered_assets)
        try:
            for asset in filtered_assets:
                logger.info(f"asset: {asset}")
                filtered_jobs = grouped_filtered_jobs_by_asset_type[asset.asset_type]
                # Exclude certain jobs from running on this asset if resource is excluded
                filtered_jobs_after_exclusion = _filter_jobs_based_on_exclusion(
                    filtered_jobs, asset, resource_management_section
                )
                if not filtered_jobs_after_exclusion:
                    continue

                prepare_for_execution = _build_prepare_for_execution_event_for_asset(
                    asset=asset,
                    trigger_filter_attributes=self.jit_event.trigger_filter_attributes,
                    jit_event=self.jit_event,
                    # There must be jobs, otherwise the asset was filtered out
                    filtered_jobs=filtered_jobs_after_exclusion,
                    installations=self.installations,
                    depends_on_workflows={key: value.dict() for key, value in plan_depends_on.items()}
                )
                prepare_for_execution_executions_events.append(prepare_for_execution)
        except Exception as handle_jit_event_exception:
            # Closing jit-security check in case of exception
            logger.error(f"Failed to handle {self.jit_event=} and start enrichment due to {handle_jit_event_exception}")
            raise HandleJitEventException(message="Failed to prepare executions")

        # update jit event life cycle with the total assets to run on
        JitEventLifeCycleHandler().filtered_assets_to_scan(
            tenant_id=self.tenant_id,
            jit_event_id=self.jit_event.jit_event_id,
            total_assets=len(prepare_for_execution_executions_events),
        )
        return prepare_for_execution_executions_events

    def trigger_events(self, events: List[PrepareForExecutionEvent]) -> None:
        """
        Triggers the prepared execution events using a State Machine.

        Args:
            events: A list of PrepareForExecutionEvent objects to be triggered.
        """
        sfn_client = SFNClient()
        state_machine_arn = os.getenv("ENRICHMENT_STATE_MACHINE_ARN", "")
        for event in events:
            event_json = event.json()
            event_size = sys.getsizeof(event_json)
            if event_size > PAYLOAD_WARNING_THRESHOLD:
                alert(f"Step Function Payload is {event_size}, investigate if re-occurring")
            sfn_client.start_execution(
                state_machine_arn=state_machine_arn,
                input=event_json,
                name=f"{self.jit_event.jit_event_name}-{self.jit_event.jit_event_id}-{datetime.now().timestamp()}",
                trace_header="enrichment step function",
                filter_attributes={"should_enrich": event.should_enrich}  # used in 'Has Enricher?' step
            )


def _remove_high_payload_properties_from_asset(asset: Asset) -> Asset:
    """
    This function sanitizes the asset for the step function.
    it removes asset's tags due to high payloads.
    """
    asset.tags = []
    return asset


def _get_resource_management_section(api_token: str, tenant_id: str) -> ResourceManagement:
    """
    Fetches the resource management section from the tenant's configuration file.

    Returns:
        A ResourceManagement object containing the parsed resource management section.
    """
    # Fetch the configuration from the plan-service and parse the resource_management section
    config_file_content = OldPlanServiceClient().get_configuration_file_for_tenant(api_token=api_token,
                                                                                   tenant_id=tenant_id)
    resource_management_section = ResourceManagement(**(config_file_content.get("resource_management", {})))
    logger.info(f"resource_management_section: {resource_management_section}")
    return resource_management_section

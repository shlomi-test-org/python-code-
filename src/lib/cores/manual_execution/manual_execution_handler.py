from __future__ import annotations

import uuid
from collections import defaultdict
from itertools import chain
from typing import Dict, List, Optional, Set, Tuple, Union

import yaml
from jit_utils.aws_clients.events import EventBridgeClient
from jit_utils.event_models import JitEventName, ManualExecutionJitEvent
from jit_utils.jit_clients.asset_service.client import AssetService
from jit_utils.jit_clients.authentication_service.client import AuthenticationService
from jit_utils.jit_clients.plan_service.client import PlanService
from jit_utils.logger import logger
from jit_utils.models.asset.entities import Asset
from jit_utils.models.plan.plan_file import FullPlanContent
from jit_utils.models.plan.template import WorkflowTemplate
from jit_utils.models.trigger.requests import AssetTriggerFilters, AssetTriggerId, ManualExecutionRequest

from src.lib.constants import (
    JIT_PLAN_SLUG,
    TRIGGER_EXECUTION_BUS_NAME,
    TRIGGER_EXECUTION_DETAIL_TYPE_HANDLE_EVENT,
    TRIGGER_SERVICE,
)
from src.lib.cores.manual_execution.exceptions import (
    AssetConflictException,
    AssetNotExistsException,
    AssetWithNoWorkflowException,
    EmptyPlanItemSlug,
    InactivePlanItemException,
    NoAssetsException,
    NoManualWorkflowsForPlanItemException,
)


class ManualExecutionHandler:
    def __init__(
            self,
            tenant_id: str,
            asset_ids: List[str],
            plan_item_slug: str,
            priority: Optional[int] = None,
    ):
        self.tenant_id = tenant_id
        self.asset_ids = asset_ids
        self.plan_item_slug = plan_item_slug
        self.priority = priority

    @classmethod
    def _get_relevant_assets(
            cls, tenant_id: str, api_token: str, assets_filter: Union[List[AssetTriggerFilters], List[AssetTriggerId]]
    ) -> List[Asset]:
        """
        Get all the tenant's assets and filter them by the filters in the request.
        """
        assets_by_name, assets_by_id = cls._gel_all_assets(tenant_id, api_token)
        relevant_assets = cls._filter_assets(assets_by_name, assets_by_id, assets_filter)

        return relevant_assets

    @classmethod
    def _gel_all_assets(cls, tenant_id: str, api_token: str) -> Tuple[Dict[str, List[Asset]], Dict[str, List[Asset]]]:
        """
        Get all the tenant's assets and prepare a mapping for all assets by name/id, so we can easily filter over them
        """
        assets_by_name: Dict[str, List[Asset]] = defaultdict(list)
        assets_by_id: Dict[str, List[Asset]] = defaultdict(list)

        all_assets = AssetService().get_all_assets(tenant_id=tenant_id, api_token=api_token)

        for asset in all_assets:
            assets_by_name[asset.asset_name].append(asset)
            assets_by_id[asset.asset_id].append(asset)

        return assets_by_name, assets_by_id

    @classmethod
    def _filter_assets(
            cls, assets_by_name: Dict[str, List[Asset]], assets_by_id: Dict[str, List[Asset]],
            assets_filter: Union[List[AssetTriggerFilters], List[AssetTriggerId]]
    ) -> List[Asset]:
        """
        Given all the assets and the filters in the request, filter the assets and return only the relevant ones.
        """
        relevant_assets = []

        for asset_filter in assets_filter:
            filtered_assets = []
            if isinstance(asset_filter, AssetTriggerFilters):
                filtered_assets = cls._get_relevant_assets_by_filters(assets_by_name=assets_by_name,
                                                                      asset_filters=asset_filter)
            elif isinstance(asset_filter, AssetTriggerId):
                filtered_assets = cls._get_relevant_assets_by_id(assets_by_id=assets_by_id, asset_id=asset_filter)

            relevant_assets.extend(filtered_assets)

        return relevant_assets

    @classmethod
    def _get_relevant_assets_by_filters(
            cls, assets_by_name: Dict[str, List[Asset]], asset_filters: AssetTriggerFilters
    ) -> List[Asset]:
        """
        Filtering input assets by the asset_filters.
        Will look for asset with name as in the filters.
        Since there can be more than 1 asset with the same name, in such conflict we will try to use the type filter
        if in the request. If the type not in the request we will raise an error to ask the user for type specification.
        """
        assets = assets_by_name.get(asset_filters.name, [])
        if not assets:
            # a requested asset wasn't found! raise an error
            raise AssetNotExistsException(asset_name=asset_filters.name)

        if len(assets) == 1:
            if asset_filters.type and assets[0].asset_type is not asset_filters.type:
                # found exactly 1 asset for the requested name but with the wrong type! raise an error
                raise AssetNotExistsException(asset_name=asset_filters.name, asset_type=asset_filters.type)
            # found exactly 1 asset for the requested key - valid case
            return [assets[0]]

        if not asset_filters.type:
            # the requested name has more than 1 asset, and we can't decide which one since type is not specified!
            # raise an error
            raise AssetConflictException(asset_name=asset_filters.name)

        # the requested name has more than 1 asset, but we got type in the request, so we can decide which one -
        # valid case
        filtered_assets = [asset for asset in assets if asset.asset_type == asset_filters.type]
        if not filtered_assets:
            # a requested asset for the type wasn't found! raise an error
            raise AssetNotExistsException(asset_name=asset_filters.name, asset_type=asset_filters.type)
        return filtered_assets

    @classmethod
    def _get_relevant_assets_by_id(cls, assets_by_id: Dict[str, List[Asset]], asset_id: AssetTriggerId) -> List[Asset]:
        """
        Get all the assets with the requested id
        """
        assets = assets_by_id.get(asset_id.id, [])
        if not assets:
            # a requested asset wasn't found! raise an error
            raise AssetNotExistsException(asset_id=asset_id.id)

        if len(assets) == 1:
            # found exactly 1 asset for the requested key - valid case
            return [assets[0]]

        # the requested id has more than 1 asset, and we can't decide which one!
        # raise an error
        raise AssetConflictException(asset_id=asset_id.id)

    @classmethod
    def _validate_plan_item_active(cls, plan: FullPlanContent, plan_item_slug: str) -> None:
        active_plan_items = [plan_item_slug for plan_item_slug, plan_item in plan.items.items()]
        if plan_item_slug not in active_plan_items:
            raise InactivePlanItemException(plan_item_slug=plan_item_slug)

    @classmethod
    def _validate_manual_workflows(cls, plan: FullPlanContent, plan_item_slug: str) -> None:
        manual_workflows = cls._extract_relevant_manual_workflows(plan=plan, plan_item_slug=plan_item_slug)
        if not manual_workflows:
            raise NoManualWorkflowsForPlanItemException()

    @classmethod
    def _validate_all_assets_can_be_triggered(
            cls, assets: List[Asset], plan: FullPlanContent, plan_item_slug: str
    ) -> None:
        manual_workflows = cls._extract_relevant_manual_workflows(plan=plan, plan_item_slug=plan_item_slug)
        asset_types_in_workflows = []
        for workflow in manual_workflows:
            asset_types_in_workflows.extend(workflow.asset_types or [])
        assets_with_no_workflows = [
            asset.asset_name
            for asset in assets
            if asset.asset_type not in asset_types_in_workflows
        ]
        if assets_with_no_workflows:
            # we found 1 or more assets that has no manual workflow in the plan item that can trigger them
            raise AssetWithNoWorkflowException(plan_item_slug=plan_item_slug, asset_names=assets_with_no_workflows)

    @classmethod
    def _extract_relevant_manual_workflows(cls, plan: FullPlanContent, plan_item_slug: str) -> List[WorkflowTemplate]:
        return [
            workflow
            for workflow in plan.items[plan_item_slug].workflow_templates
            if JitEventName.ManualExecution in ManualExecutionHandler._extract_triggers_from_workflow(workflow)
        ]

    @classmethod
    def _extract_triggers_from_workflow(cls, workflow: WorkflowTemplate) -> Set[str]:
        triggers = yaml.safe_load(workflow.content)["trigger"]
        workflow_triggers = set(chain(*triggers.values()))
        return workflow_triggers

    @classmethod
    def _validate(cls, assets: List[Asset], plan: FullPlanContent, plan_item_slug: str) -> None:
        """
        This function is going to validate that each of the asset in the assets has at least 1 workflow to execute
        for the given plan item.

        A specific exception that describes the validation error will be raised with a detailed message.
        """
        ManualExecutionHandler._validate_plan_item_active(plan=plan, plan_item_slug=plan_item_slug)
        ManualExecutionHandler._validate_manual_workflows(plan=plan, plan_item_slug=plan_item_slug)
        ManualExecutionHandler._validate_all_assets_can_be_triggered(
            assets=assets,
            plan=plan,
            plan_item_slug=plan_item_slug,
        )

    @classmethod
    def fromManualExecutionRequest(cls, tenant_id: str, request: ManualExecutionRequest) -> ManualExecutionHandler:
        """
        This function will try to create a ManualExecutionHandler object using assets applicable from the request.
        :raises:
            EmptyPlanItemSlug: plan item slug is an empty string
            NoAssetsException: assets in the request is an empty list
            AssetNotExistsException: didn't find one of the asset based in the request data
            AssetNameConflictException: found more than 1 asset with the same name as requested but can decide which one
            InactivePlanItemException: the requested plan item does not exist, or is inactive for the tenant
            NoManualWorkflowsForPlanItemException: the requested plan item has no workflow with manual trigger
            AssetWithNoWorkflowException: the requested plan item has no workflow that can run a requested asset
        """
        if not request.plan_item_slug:
            # plan_item_slug can't be an empty string
            raise EmptyPlanItemSlug()
        if not request.assets:
            # assets can't be an empty list
            raise NoAssetsException()

        # prepare relevant data
        api_token = AuthenticationService().get_api_token(tenant_id=tenant_id)
        assets = cls._get_relevant_assets(tenant_id=tenant_id, api_token=api_token, assets_filter=request.assets)
        plan = PlanService().get_full_plan(plan_slug=JIT_PLAN_SLUG, api_token=api_token)

        # validate plan item and assets in the request can successfully trigger executions
        cls._validate(assets=assets, plan=plan, plan_item_slug=request.plan_item_slug)

        return ManualExecutionHandler(
            tenant_id=tenant_id,
            asset_ids=[asset.asset_id for asset in assets],
            plan_item_slug=request.plan_item_slug,
            priority=request.priority,
        )

    def trigger(self) -> str:
        """
        This function will trigger a jit event that will initiate triggering of the user requested executions.

        :returns:
            jit_event_id of the triggered jit event
        """
        jit_event = ManualExecutionJitEvent(
            tenant_id=self.tenant_id,
            jit_event_id=str(uuid.uuid4()),
            asset_ids_filter=self.asset_ids,
            plan_item_slug=self.plan_item_slug,
            priority=self.priority,
        )

        events_client = EventBridgeClient()
        events_client.put_event(
            source=TRIGGER_SERVICE,
            bus_name=TRIGGER_EXECUTION_BUS_NAME,
            detail_type=TRIGGER_EXECUTION_DETAIL_TYPE_HANDLE_EVENT,
            detail=jit_event.json()
        )
        logger.info(f"Successfully triggered the manual execution with jit_event_id={jit_event.jit_event_id}")
        return jit_event.jit_event_id

from typing import List, Dict

from jit_utils.event_models import JitEvent
from jit_utils.logger import logger
from jit_utils.models.asset.entities import Asset
from jit_utils.models.tenant.entities import Installation

from src.lib.constants import ASSETS_TYPES_WITH_INSTALLATIONS
from src.lib.cores.filter_evaluators.filter_evaluators_manager import FiltersEvaluatorsManager
from src.lib.cores.jit_event_handlers.trigger_filter import TriggerFilter


class AssetIdsTriggerFilter(TriggerFilter[Asset]):
    def filter(self, assets: List[Asset]) -> List[Asset]:
        if not self.trigger_filters.asset_ids:
            return assets

        return [asset for asset in assets if asset.asset_id in self.trigger_filters.asset_ids]


class AssetWithInstallationTriggerFilter(TriggerFilter[Asset]):
    def __init__(self, jit_event: JitEvent, api_token: str, installations: List[Installation]):
        super().__init__(jit_event)
        self.api_token = api_token
        self.installations = installations

    def installations_map(self) -> Dict[str, Dict[str, Installation]]:
        installations = self.installations
        installations_map: Dict = {}
        for installation in installations:
            if installation.vendor not in installations_map:
                installations_map[installation.vendor] = {}
            installations_map[installation.vendor][installation.owner] = installation
        return installations_map

    def filter(self, assets: List[Asset]) -> List[Asset]:
        filtered = []
        installations_map = self.installations_map()
        for asset in assets:
            if asset.asset_type not in ASSETS_TYPES_WITH_INSTALLATIONS:
                filtered.append(asset)
            elif asset.vendor in installations_map and asset.owner in installations_map[asset.vendor]:
                filtered.append(asset)
            else:
                logger.info("Asset should have installation but doesn't - filtering")
        return filtered


class AssetByTriggersAndEnvTriggerFilter(TriggerFilter[Asset]):
    def __init__(self, jit_event: JitEvent, api_token: str):
        super().__init__(jit_event)
        self.api_token = api_token

    def filter(self, assets: List[Asset]) -> List[Asset]:
        if not self.trigger_filters.triggers or not self.trigger_filters.asset_envs:
            return assets

        logger.info(
            f"Filtering existing: {len(assets)} assets according to given: "
            f"triggers={self.trigger_filters.triggers} and asset_envs={self.trigger_filters.asset_envs}"
        )
        specific_trigger = list(self.trigger_filters.triggers)[0]  # Currently we support one trigger per event
        specific_env = list(self.trigger_filters.asset_envs)[0]  # Currently we support one env per event

        filtered_assets = FiltersEvaluatorsManager(self.api_token, self.tenant_id).filter(
            specific_trigger, specific_env, assets)
        logger.info(f"Post filtering, we remained with: {len(filtered_assets)} assets")
        return filtered_assets

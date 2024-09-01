from enum import StrEnum
from typing import Dict

from src.lib.cores.cancel_event_handler.asset_removed_handler import AssetRemovedHandler
from src.lib.cores.cancel_event_handler.cancel_event_handler import CancelEventHandler
from src.lib.cores.cancel_event_handler.plan_item_deactivated_handler import PlanItemDeactivatedHandler


class CancelEventTypes(StrEnum):
    AssetNotCovered = "asset-not-covered"
    PlanItemsDeactivated = "plan-items-is-active"


def get_cancel_event_handler(cancel_event_type: CancelEventTypes, event_body: Dict) -> CancelEventHandler:
    handlers_mapping = {
        CancelEventTypes.AssetNotCovered: AssetRemovedHandler,
        CancelEventTypes.PlanItemsDeactivated: PlanItemDeactivatedHandler,
    }

    return handlers_mapping[cancel_event_type](event_body)

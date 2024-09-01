from typing import List

from jit_utils.models.asset.entities import Asset

from src.lib.cores.jit_event_handlers.trigger_filter import TriggerFilter, TriggerFilterTypes
from tests.common import AssetFactory, ManualExecutionJitEventFactory


def test_filter_with_logic():
    class AssetTriggerFilter(TriggerFilter[Asset]):
        def filter(self, items_to_filter: List[TriggerFilterTypes]) -> List[TriggerFilterTypes]:
            return [items_to_filter[0]]

    event = ManualExecutionJitEventFactory.build()
    trigger_filter = AssetTriggerFilter(event)
    items = [AssetFactory.build(), AssetFactory.build()]
    result = trigger_filter.filter(items)
    assert result == [items[0]]

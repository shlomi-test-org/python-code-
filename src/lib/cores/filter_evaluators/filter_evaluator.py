from abc import ABC
from typing import List, Dict

from jit_utils.models.asset.entities import Asset


class FilterEvaluator(ABC):
    def should_filter(self, trigger_type: str) -> bool:
        raise NotImplementedError

    def filter(
            self, trigger_type: str, tag: str, assets: List[Asset], api_token: str, tenant_id: str
    ) -> Dict[str, Asset]:
        raise NotImplementedError

    def get_name(self) -> str:
        raise NotImplementedError

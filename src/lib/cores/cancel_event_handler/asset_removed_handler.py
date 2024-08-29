from typing import Dict
from typing import List

from jit_utils.logger import logger
from jit_utils.models.execution import ExecutionStatus
from pydantic import BaseModel

from src.lib.cores.cancel_event_handler.cancel_event_handler import CancelEventHandler
from src.lib.cores.executions_core import get_all_executions_by_filter
from jit_utils.models.execution import Execution
from src.lib.models.execution_models import GetExecutionsFilters


class MinimalAsset(BaseModel):
    tenant_id: str
    asset_id: str


class AssetRemovedEvent(BaseModel):
    body: MinimalAsset


class AssetRemovedHandler(CancelEventHandler[AssetRemovedEvent]):
    def get_executions_to_cancel(self) -> List[Execution]:
        filters = GetExecutionsFilters(status=ExecutionStatus.PENDING, asset_id=self._event_body.body.asset_id)
        executions_to_cancel = get_all_executions_by_filter(tenant_id=self.tenant_id, filters=filters)
        logger.info(f"Found {len(executions_to_cancel)} executions to cancel")
        return executions_to_cancel

    def parse_event_body(self, event_body: Dict) -> AssetRemovedEvent:
        return AssetRemovedEvent(**event_body)

    @property
    def tenant_id(self) -> str:
        return self._event_body.body.tenant_id

    def get_error_message(self) -> str:
        return "Asset not covered"

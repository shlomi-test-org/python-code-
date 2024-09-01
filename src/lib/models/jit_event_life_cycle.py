import time
from datetime import datetime
from typing import Optional, Any

from jit_utils.event_models import JitEvent
from jit_utils.models.trigger.jit_event_life_cycle import JitEventStatus, JitEventLifeCycleEntity
from pydantic import BaseModel

from src.lib.constants import JIT_EVENT_TTL


class BaseDBEntity(BaseModel):
    tenant_id: str
    jit_event_id: str
    created_at: str
    modified_at: Optional[str] = None
    ttl: int  # TTL field as Unix timestamp for dynamo to expire the record

    def __init__(self, **data: Any) -> None:
        # Set default created_at and ttl if not provided
        if 'created_at' not in data:
            current_time = datetime.utcnow()
            data['created_at'] = current_time.isoformat()
            data['ttl'] = int(time.mktime(current_time.timetuple())) + JIT_EVENT_TTL  # week
        super().__init__(**data)


class JitEventDBEntity(BaseDBEntity, JitEventLifeCycleEntity):
    def __init__(self, **data: Any) -> None:
        # Default status to CREATING if not provided
        if 'status' not in data:
            data['status'] = JitEventStatus.CREATING
        super().__init__(**data)

    @classmethod
    def from_jit_event(cls, jit_event: JitEvent, status: Optional[JitEventStatus] = None) -> 'JitEventDBEntity':
        return cls(
            tenant_id=jit_event.tenant_id,
            jit_event_id=jit_event.jit_event_id,
            status=status,
            jit_event_name=jit_event.jit_event_name,
            plan_item_slugs=list(jit_event.trigger_filter_attributes.plan_item_slugs),
            jit_event=jit_event,
        )


class JitEventAssetDBEntity(BaseDBEntity):
    asset_id: str  # SK = jit_event_id + asset_id
    total_jobs: int
    remaining_jobs: int  # counter to zero

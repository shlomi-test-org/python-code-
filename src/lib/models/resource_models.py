from typing import Optional
from pydantic import BaseModel

from jit_utils.models.execution import ResourceType

from src.lib.constants import MAX_RESOURCES_IN_USE


class Resource(BaseModel):
    tenant_id: str
    resource_type: ResourceType
    resources_in_use: int = 0
    max_resources_in_use: int = MAX_RESOURCES_IN_USE

    class Config:
        use_enum_values = True


class ResourceInUse(BaseModel):
    tenant_id: str
    resource_type: ResourceType
    jit_event_id: str
    execution_id: str
    created_at: str
    created_at_ts: Optional[int]

    class Config:
        use_enum_values = True


class ResourceEntity(Resource):
    PK: str
    SK: str

    class Config:
        use_enum_values = True


class ResourceInUseEntity(ResourceInUse):
    PK: str
    SK: str
    GSI1PK: str
    GSI1SK: str

    class Config:
        use_enum_values = True

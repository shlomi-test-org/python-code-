from typing import Any, Optional

from pydantic import BaseModel, Extra

from jit_utils.models.execution_priority import ExecutionPriority


class BaseMetadata(BaseModel):
    tenant_id: str

    class Config:
        extra = Extra.ignore
        validate_assignment = True


class BaseData(BaseModel):
    class Config:
        extra = Extra.ignore
        validate_assignment = True


class BaseMetric(BaseModel):
    metric_name: str
    metadata: BaseMetadata
    data: BaseData


class ExecutionUpdateMetric(BaseMetric):
    class ExecutionUpdateMetadata(BaseMetadata):
        env_name: str
        event_id: str
        event_name: str
        tenant_id: str
        entity_type: str
        plan_item_slug: str
        workflow_slug: str
        job_name: str
        control_name: Optional[str]
        control_image: Optional[str]
        job_runner: str
        plan_slug: str
        asset_type: Optional[str]
        asset_name: Optional[str]
        asset_id: str
        vendor: Optional[str]
        priority: int = ExecutionPriority.LOW
        control_type: Optional[str]
        execution_timeout: Optional[str]

    class ExecutionUpdateData(BaseData):
        execution_id: str
        created_at: str
        created_at_ts: Optional[int]
        dispatched_at: Optional[str]
        dispatched_at_ts: Optional[int]
        registered_at: Optional[str]
        registered_at_ts: Optional[int]
        completed_at: Optional[str]
        completed_at_ts: Optional[int]
        run_id: Optional[str]
        status: Optional[str]
        has_findings: Optional[bool]
        status_details: Optional[Any]
        error_body: Optional[str]
        upload_findings_status: Optional[str]
        control_status: Optional[str]
        execution_timeout: Optional[str]

    metric_name = "execution_update"
    metadata: ExecutionUpdateMetadata
    data: ExecutionUpdateData

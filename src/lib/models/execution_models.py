from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pydantic import BaseModel, validator
from typing import Any, Callable, Dict, List, Optional

from jit_utils.event_models.trigger_event import TriggerExecutionEvent
from jit_utils.lambda_decorators.status_code_wrapper import api_request
from jit_utils.models.execution import BaseExecutionIdentifiers, BackgroundJobOutput, Execution, ExecutionStatus, \
    ExecutionError
from jit_utils.models.controls import ControlType

from src.lib.cores.fargate.constants import SILENT_INVOCATION_SUPPORTED_CONTROL_NAMES


class ExecutionValidationIdentifies(BaseExecutionIdentifiers):
    target_asset_name: Optional[str]


class Commits(BaseModel):
    base_sha: Optional[str]
    head_sha: Optional[str]


STATUSES_WITH_TIMEOUT = [ExecutionStatus.DISPATCHING, ExecutionStatus.DISPATCHED, ExecutionStatus.RUNNING]


class ControlStatusDetails(BaseModel):
    message: str
    url: Optional[str]
    url_text: Optional[str]


class UpdateAttributes(BaseModel):
    """
    Request to complete a job
    """
    status: Optional[ExecutionStatus]
    has_findings: Optional[bool]
    status_details: Optional[ControlStatusDetails]
    error_body: Optional[str]
    completed_at: Optional[str]
    completed_at_ts: Optional[int]
    registered_at: Optional[str]
    registered_at_ts: Optional[int]
    dispatched_at: Optional[str]
    dispatched_at_ts: Optional[int]
    control_name: Optional[str]
    vendor: Optional[str]
    control_type: Optional[ControlType]
    run_id: Optional[str]
    execution_timeout: Optional[str]
    stderr: Optional[str]  # only completed request may return stderr
    retry_count: Optional[int]

    class Config:
        use_enum_values = True


class GetExecutionsFilters(BaseModel):
    """
    Request to get a list of executions
    """
    status: Optional[ExecutionStatus]
    plan_item_slug: Optional[str]
    limit: int = 25
    start_key: Dict[str, str] = {}
    jit_event_id: Optional[str]
    asset_id: Optional[str]
    job_name: Optional[str]

    class Config:
        use_enum_values = True


class GetExecutionByIdFilters(BaseModel):
    jit_event_id: str
    execution_id: str


class UpdateRequest(UpdateAttributes, BaseExecutionIdentifiers):
    """
    Request to complete a job
    """
    original_request: Optional[Dict[str, Any]]
    job_output: Optional[BackgroundJobOutput]  # the output of the execution job, returns on background executions
    errors: List[ExecutionError] = []

    class Config:
        use_enum_values = True


@api_request
class VendorJobIDUpdateRequest(BaseExecutionIdentifiers):
    """
    Request to update execution with vendor job ID
    """
    vendor_job_id: str


class ExecutionWithVendorLogs(Execution):
    vendor_logs_url: Optional[str]


class GetExecutionsResponseMetadata(BaseModel):
    count: int
    last_key: str


class GetExecutionsResponse(BaseModel):
    data: List[Execution]
    metadata: GetExecutionsResponseMetadata


class GetExecutionDataResponse(BaseModel):
    data: ExecutionData


class ExecutionEntity(Execution):
    PK: str
    SK: str
    GSI2PK: Optional[str]
    GSI2SK: Optional[str]
    GSI3PK: Optional[str]
    GSI3SK: Optional[str]
    GSI4PK: Optional[str]
    GSI4SK: Optional[str]
    GSI5PK: Optional[str]
    GSI5SK: Optional[str]
    GSI6PK: Optional[str]
    GSI6SK: Optional[str]
    GSI7PK_TENANT_JIT_EVENT_ID: Optional[str]
    GSI7SK_CREATED_AT: Optional[str]
    GSI8PK_TENANT_ID_STATUS: Optional[str]
    GSI8SK_ASSET_ID_CREATED_AT: Optional[str]
    GSI9PK_TENANT_ID: Optional[str]
    GSI9SK_JIT_EVENT_ID_JOB_NAME_CREATED_AT: Optional[str]
    ttl: Optional[int]

    class Config:
        use_enum_values = True


class ExecutionDispatchUpdateEvent(BaseExecutionIdentifiers):
    # ideally we should have this identifier when we dispatch an execution.
    # GitHub don't support the run_id at the dispatch state.
    run_id: Optional[str]


class StatusUpdateConflictError(BaseModel):
    message: str
    from_status: ExecutionStatus
    to_status: ExecutionStatus


class FailedTriggersEvent(BaseModel):
    failure_message: str
    failed_triggers: List[TriggerExecutionEvent]


class ExecutionData(BaseExecutionIdentifiers):
    execution_data_json: str
    created_at: str
    retrieved_at: Optional[int]

    @property
    def retrieved_at_dt(self) -> datetime:
        return datetime.fromtimestamp(self.retrieved_at)


class ExecutionDataEntity(ExecutionData):
    PK: str
    SK: str


class SilentInvocationRequest(BaseModel):
    id: str
    tenant_id: str
    job_definition: str
    job_name: Optional[str] = None  # Will be calculated if not provided, Asset name & date/time will be added anyway
    control_name: str
    asset_types: Optional[List[str]] = None  # If not provided, will run on all asset types
    env: Optional[Dict[str, str]] = None
    command: Optional[List[str]] = None
    is_dry_run: bool = True

    @validator('control_name')
    def validate_control_name(cls, v, values):
        if v not in SILENT_INVOCATION_SUPPORTED_CONTROL_NAMES:
            raise ValueError(f'Control name "{v}" is not supported')

        if v not in values['job_definition']:
            raise ValueError(f'Control name {v} is not part of job definition {values["job_definition"]}')
        return v


class SilentInvocationControlConfig(BaseModel):
    asset_types: List[str]
    preparation_function: Optional[Callable] = None
    asset_filtering_function: Optional[Callable] = None


class MultipleExecutionsIdentifiers(BaseModel):
    """
    This model represents a group of executions that share the same 'tenant_id' and 'jit_event_id'.
    It is used to send identifiers of multiple executions to the executions event bus in a single put event operation.
    The event is then consumed by the 'dispatch-execution' lambda to dispatch multiple executions at once.
    """
    tenant_id: str
    jit_event_id: str
    execution_ids: List[str]

    @classmethod
    def group_by_jit_event_id(
        cls,
        executions: List[Execution],
    ) -> List[MultipleExecutionsIdentifiers]:
        """
        This method takes a list of Execution instances and groups them by their 'jit_event_id' and 'tenant_id'.
        The grouping is done to gather executions that can be dispatched concurrently into a single event.

        Returns:
            List[MultipleExecutionsIdentifiers]: A list of MultipleExecutionsIdentifiers instances,
            where each instance represents a group of executions that belong to the same tenant and jit event.
        """
        grouped_executions = defaultdict(list)

        for execution in executions:
            grouped_executions[(execution.tenant_id, execution.jit_event_id)].append(execution.execution_id)

        execution_identifiers_grouped_by_jit_event_id = []
        for (tenant_id, jit_event_id), execution_ids in grouped_executions.items():
            execution_identifiers_grouped_by_jit_event_id.append(
                cls(
                    tenant_id=tenant_id,
                    jit_event_id=jit_event_id,
                    execution_ids=execution_ids,
                )
            )

        return execution_identifiers_grouped_by_jit_event_id

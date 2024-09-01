# This file will be deleted when we will stop receiving the data from the Wrofkflow service
from enum import StrEnum
from typing import Optional

from pydantic import BaseModel


class WorkflowStatus(StrEnum):
    QUEUED = 'queued'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    EXECUTION_FAILURE = 'execution_failure'


class Conclusion(StrEnum):
    IN_PROGRESS = "in_progress"
    SUCCESS = 'success'
    FAILURE = 'failure'


class ControlStatusDetails(BaseModel):
    message: str
    url: Optional[str]
    url_text: Optional[str]


class JobModel(BaseModel):
    tenant_id: str
    plan_slug: str
    plan_item_slug: str
    vendor: str
    app_id: Optional[str]
    installation_id: Optional[str]
    workflow_suite_id: str
    workflow_id: str
    job_name: str  # name of the job. unique per workflow suite
    conclusion: Optional[Conclusion] = Conclusion.IN_PROGRESS
    status: Optional[WorkflowStatus] = WorkflowStatus.IN_PROGRESS
    status_details: Optional[ControlStatusDetails] = None
    findings_uploaded: bool = False
    created_at: str
    updated_at: str

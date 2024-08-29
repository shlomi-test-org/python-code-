from datetime import datetime
from enum import StrEnum
from typing import Optional

from src.lib.models.execution_models import BaseExecutionIdentifiers


class CPUArchitecture(StrEnum):
    x86_64 = "x86_64"
    arm64 = "arm64"


class ECSTaskData(BaseExecutionIdentifiers):
    cpu_architecture: CPUArchitecture
    region: str
    start_time: datetime
    event_time: datetime
    duration_seconds: int
    billable_duration_minutes: float
    vcpu: float
    memory_gb: float
    storage_gb: float
    billable_storage_gb: float
    is_linux: bool
    exit_code: Optional[int]
    container_image: Optional[str]
    image_digest: Optional[str]

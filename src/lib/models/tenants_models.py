from enum import StrEnum
from typing import Dict
from typing import Optional

from pydantic.main import BaseModel


class TenantCreated(BaseModel):
    """
    Event sent when a tenant is created.
    """
    tenant_id: str


class InstallationStatus(StrEnum):
    CONNECTED = "connected"
    WARNING = "warning"
    PENDING = "pending"
    ERROR = "error"


class PartialUpdateInstallation(BaseModel):
    status: Optional[InstallationStatus]
    status_details: Optional[Dict]


class PartialUpdateInstallationRequest(PartialUpdateInstallation):
    tenant_id: str
    installation_id: str
    vendor: str

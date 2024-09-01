from typing import List

from pydantic import BaseModel


class DeploymentPreferences(BaseModel):
    _type: str = "deployment"

    environments: List[str] = []


class TenantPreferences(BaseModel):
    deployment: DeploymentPreferences = DeploymentPreferences()

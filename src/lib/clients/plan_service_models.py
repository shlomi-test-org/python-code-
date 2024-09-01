import re
from typing import List, Optional

from pydantic import validator, fields
from pydantic.main import BaseModel, Extra


class ApplicationConfiguration(BaseModel):
    type: str
    application_name: str

    class Config:
        extra = Extra.allow


class AwsApplicationConfiguration(ApplicationConfiguration):
    account_ids: Optional[List[str]]

    @validator("account_ids")
    def list_of_ids(cls, v: List[str], field: fields.ModelField) -> List[str]:
        if len(v) == 0:
            raise ValueError("account_ids cannot be empty")

        for account_id in v:
            if re.match(r"^\d{12}$", account_id) is None:
                raise ValueError(f"{field.name} must consist of 12 digits only")

        return v

    class Config:
        extra = Extra.ignore


class PlanItemConfiguration(BaseModel):
    plan_item_slug: str

    class Config:
        extra = Extra.allow


class JitCentralizedRepoFilesMetadataResponse(BaseModel):
    centralized_repo_files_location: str
    ci_workflow_files_path: List[str]

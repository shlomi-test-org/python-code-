from pydantic.main import BaseModel


class DeleteTenantDataRequest(BaseModel):
    tenant_id: str

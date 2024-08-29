from pydantic import BaseModel


class CancelWorkflowRunRequest(BaseModel):
    """
    The request to cancel a workflow run
    """
    app_id: str
    installation_id: str
    owner: str
    run_id: int
    vendor: str
    repo: str

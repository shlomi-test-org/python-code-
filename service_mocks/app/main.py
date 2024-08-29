from http import HTTPStatus
from typing import List, Dict
from typing import Optional

from fastapi import FastAPI, Header, HTTPException

from jit_utils.models.execution import Execution

from src.lib.models.execution_models import UpdateRequest

from tests.mocks.execution_mocks import generate_mock_executions

app = FastAPI(title="execution-service")


@app.get("/", status_code=HTTPStatus.OK, response_model=List[Execution])
def get_executions(
        amount: int = 25,
        Tenant: Optional[str] = Header(None),
        status: Optional[str] = None,
        plan_item_slug: Optional[str] = None,
):
    if not Tenant:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Tenant header is required")
    return generate_mock_executions(amount, Tenant, status, plan_item_slug)


@app.get("/execution", status_code=HTTPStatus.OK, response_model=Execution)
def get_execution_by_id(Tenant: Optional[str] = Header(None), jit_event_id: str = None, execution_id: str = None):
    if not Tenant:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Tenant header is required")
    execution = generate_mock_executions(1, Tenant)[0]
    execution.jit_event_id = jit_event_id
    execution.execution_id = execution_id
    return execution


@app.post("/register", status_code=HTTPStatus.OK, response_model=UpdateRequest)
def register(
        update_request: UpdateRequest,
        Tenant: Optional[str] = Header(None),
):
    if not Tenant:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Tenant header is required")
    return update_request


@app.post("/completed", status_code=HTTPStatus.OK, response_model=UpdateRequest)
def complete(
        update_request: UpdateRequest,
        Tenant: Optional[str] = Header(None),
):
    if not Tenant:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Tenant header is required")
    return update_request


@app.get('/health', status_code=HTTPStatus.OK, response_model=Dict[str, str])
def get_health():
    return {"status": "UP"}

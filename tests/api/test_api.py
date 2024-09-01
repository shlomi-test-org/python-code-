from http import HTTPStatus

from fastapi.testclient import TestClient

from service_mocks.app.main import app
from src.lib.models.execution_models import ExecutionStatus
from tests.mocks.execution_mocks import generate_mock_executions
from tests.mocks.execution_mocks import MOCK_PLAN_ITEM_SLUG
from tests.mocks.execution_mocks import MOCK_TENANT_ID
from tests.mocks.execution_mocks import MOCK_UPDATE_REQUEST

client = TestClient(app)


def test_get_executions_by_tenant_id_and_status():
    response = client.get("/", params={"status": ExecutionStatus.COMPLETED.value},
                          headers={"Authorization": "Bearer test", "Tenant": MOCK_TENANT_ID})

    assert response.status_code == HTTPStatus.OK
    executions = response.json()
    assert len(executions) == 25
    for execution in executions:
        assert execution["status"] == ExecutionStatus.COMPLETED.value
        assert execution["tenant_id"] == MOCK_TENANT_ID


def test_get_executions_by_tenant_id_and_amount():
    response = client.get("/", params={"amount": 10},
                          headers={"Authorization": "Bearer test", "Tenant": MOCK_TENANT_ID})

    assert response.status_code == HTTPStatus.OK
    executions = response.json()
    assert len(executions) == 10
    for execution in executions:
        assert execution["tenant_id"] == MOCK_TENANT_ID


def test_get_executions_by_tenant_id_and_status_and_amount():
    response = client.get("/", params={"status": ExecutionStatus.COMPLETED.value,
                                       "amount": 10},
                          headers={"Authorization": "Bearer test", "Tenant": MOCK_TENANT_ID})

    assert response.status_code == HTTPStatus.OK
    executions = response.json()
    assert len(executions) == 10
    for execution in executions:
        assert execution["status"] == ExecutionStatus.COMPLETED.value
        assert execution["tenant_id"] == MOCK_TENANT_ID


def test_get_executions_by_tenant_id_and_plan_item_slug():
    response = client.get("/", params={"plan_item_slug": MOCK_PLAN_ITEM_SLUG},
                          headers={"Authorization": "Bearer test", "Tenant": MOCK_TENANT_ID})

    assert response.status_code == HTTPStatus.OK
    executions = response.json()
    assert len(executions) == 25
    for execution in executions:
        assert execution["plan_item_slug"] == MOCK_PLAN_ITEM_SLUG
        assert execution["tenant_id"] == MOCK_TENANT_ID


def test_get_executions_by_tenant_id_and_plan_item_slug_and_status():
    response = client.get("/", params={"plan_item_slug": MOCK_PLAN_ITEM_SLUG,
                                       "status": ExecutionStatus.COMPLETED.value},
                          headers={"Authorization": "Bearer test", "Tenant": MOCK_TENANT_ID})

    assert response.status_code == HTTPStatus.OK
    executions = response.json()
    assert len(executions) == 25
    for execution in executions:
        assert execution["status"] == ExecutionStatus.COMPLETED.value
        assert execution["plan_item_slug"] == MOCK_PLAN_ITEM_SLUG
        assert execution["tenant_id"] == MOCK_TENANT_ID


def test_get_executions_by_tenant_id_and_jit_event_id_and_execution_id():
    response = client.get('/execution', params={'jit_event_id': '123', 'execution_id': '456'},
                          headers={'Authorization': 'Bearer test', 'Tenant': MOCK_TENANT_ID})

    assert response.status_code == HTTPStatus.OK
    execution = response.json()
    assert execution['jit_event_id'] == '123'
    assert execution['execution_id'] == '456'
    assert execution['tenant_id'] == MOCK_TENANT_ID


def test_get_executions_without_tenant_id():
    response = client.get("/",
                          headers={"Authorization": "Bearer test"})

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json() == {'detail': 'Tenant header is required'}


def test_register_execution():
    mock_execution = generate_mock_executions(1, MOCK_TENANT_ID)[0]
    response = client.post("/register",
                           json=mock_execution.dict(),
                           headers={"Authorization": "Bearer test", "Tenant": MOCK_TENANT_ID})

    assert response.status_code == HTTPStatus.OK


def test_register_execution_without_tenant_id():
    mock_execution = generate_mock_executions(1, MOCK_TENANT_ID)[0]
    response = client.post("/register",
                           json=mock_execution.dict())

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json() == {'detail': 'Tenant header is required'}


def test_register_execution_invalid_execution():
    response = client.post("/register",
                           headers={"Authorization": "Bearer test", "Tenant": MOCK_TENANT_ID})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_complete_execution():
    response = client.post("/completed",
                           json=MOCK_UPDATE_REQUEST.dict(),
                           headers={"Authorization": "Bearer test", "Tenant": MOCK_TENANT_ID})

    assert response.status_code == HTTPStatus.OK


def test_complete_execution_without_tenant_id():
    response = client.post("/completed",
                           json=MOCK_UPDATE_REQUEST.dict())

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json() == {'detail': 'Tenant header is required'}


def test_complete_execution_invalid_execution():
    response = client.post("/completed",
                           headers={"Authorization": "Bearer test", "Tenant": MOCK_TENANT_ID})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_get_health():
    response = client.get("/health",
                          headers={"Authorization": "Bearer test", "Tenant": MOCK_TENANT_ID})

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"status": "UP"}

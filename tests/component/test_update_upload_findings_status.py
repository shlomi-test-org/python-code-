import uuid

import pytest
from jit_utils.models.findings.events import UploadFindingsStatusEvent, UploadFindingsStatus
from test_utils.aws import idempotency

import src
from src.lib.models.execution_models import ExecutionStatus
from tests.component.fixtures import _prepare_execution_to_update


def _setup_test():
    idempotency.create_idempotency_table()
    from src.handlers import handle_update_upload_findings_status

    tenant_id = str(uuid.uuid4())
    jit_event_id = str(uuid.uuid4())
    execution_id = str(uuid.uuid4())

    mock_event_bridge_event = {
        "detail": UploadFindingsStatusEvent(
            tenant_id=tenant_id,
            jit_event_id=jit_event_id,
            execution_id=execution_id,
            status=UploadFindingsStatus.COMPLETED,
            new_findings_count=0,
            existing_findings_count=0,
            created_at="2021-01-01T00:00:00Z",
            fail_on_findings=False,
        ).dict(),
        "id": str(uuid.uuid4()),
    }

    return tenant_id, jit_event_id, execution_id, mock_event_bridge_event, handle_update_upload_findings_status


def test_update_upload_findings_status_handler__happy_flow(executions_manager):
    """
    Test the update_upload_findings_status_handler function with a successful flow.
    Setup:
        1) Generate api event with fail on findings set to False.
        2) Store execution with has_findings set to True.
    Test:
        1) Call the update_upload_findings_status_handler function with the generated event.
    Assert:
        1) Verify that the updated execution response matches the expected execution response.
        2) Verify that the updated execution has the has_findings attribute set to False.
        3) Verify that the updated execution has the upload_findings_status attribute set to COMPLETED.
        4) Verify that the updated execution has the affected_plan_items attribute set to ["item-0", "item-1"].
    """
    tenant_id, jit_event_id, execution_id, mock_event_bridge_event, handle_update_upload_findings_status = _setup_test()

    exepected_execution = _prepare_execution_to_update(
        executions_manager, tenant_id, jit_event_id, execution_id, ExecutionStatus.RUNNING, has_findings=True
    )
    handle_update_upload_findings_status.handler(mock_event_bridge_event, None)
    updated_execution = executions_manager.get_execution_by_jit_event_id_and_execution_id(
        tenant_id=tenant_id,
        jit_event_id=jit_event_id,
        execution_id=execution_id,
    )
    exepected_execution.upload_findings_status = UploadFindingsStatus.COMPLETED
    exepected_execution.affected_plan_items = ["item-0", "item-1"]
    exepected_execution.has_findings = False
    assert updated_execution == exepected_execution


def test_update_upload_findings_status_handler__failed_to_udate(executions_manager):
    tenant_id, jit_event_id, execution_id, mock_event_bridge_event, handle_update_upload_findings_status = _setup_test()

    _prepare_execution_to_update(
        executions_manager, tenant_id, jit_event_id, execution_id, ExecutionStatus.DISPATCHED
    )
    with pytest.raises(executions_manager.client.exceptions.ConditionalCheckFailedException):
        handle_update_upload_findings_status.handler(mock_event_bridge_event, None)


def test_update_upload_findings_status_handler__idempotency(mocker, executions_manager):
    tenant_id, jit_event_id, execution_id, mock_event_bridge_event, handle_update_upload_findings_status = _setup_test()

    _prepare_execution_to_update(
        executions_manager, tenant_id, jit_event_id, execution_id, ExecutionStatus.RUNNING
    )
    spy = mocker.spy(src.handlers.handle_update_upload_findings_status, "update_upload_findings_status")
    handle_update_upload_findings_status.handler(mock_event_bridge_event, None)
    handle_update_upload_findings_status.handler(mock_event_bridge_event, None)

    assert spy.call_count == 1

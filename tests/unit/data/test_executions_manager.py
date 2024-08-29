import json
import uuid
from typing import List, Optional
from datetime import datetime, timedelta

import pytest
from botocore.exceptions import ClientError

from jit_utils.models.controls import ControlType
from jit_utils.models.execution_context import Runner
from jit_utils.models.findings.events import UploadFindingsStatus
from jit_utils.models.execution_priority import ExecutionPriority
from jit_utils.models.execution import Execution, ExecutionError, ExecutionErrorType

from src.lib.data.executions_manager import ExecutionsManager
from src.lib.constants import GSI2PK, GSI4PK, GSI5PK, GSI7PK_TENANT_JIT_EVENT_ID, GSI7SK_CREATED_AT, PK, SK
from src.lib.models.execution_models import (
    ExecutionData, ExecutionDataEntity, ExecutionEntity,
    ExecutionStatus, MultipleExecutionsIdentifiers, UpdateRequest,
)
from src.lib.exceptions import ExecutionDataNotFoundException, MultipleCompletesExceptions, StatusTransitionException

from tests.factories import ExecutionFactory
from tests.mocks.execution_mocks import (
    MOCK_EXECUTION_CONTEXT_CODE_EXECUTION, generate_mock_executions, MOCK_EXECUTION,
    MOCK_EXECUTION_DATA, MOCK_TENANT_ID, MOCK_UPDATE_REQUEST
)


def assert_db_item_length(executions_manager, expected_length: int):
    items = executions_manager.table.scan()["Items"]
    assert len(items) == expected_length


def get_key(**kwargs):
    return '#'.join(f'{key.upper()}#{str(value).lower()}' for key, value in kwargs.items())


def convert_execution_to_execution_entity(execution: Execution) -> ExecutionEntity:
    gsi1sk = gsi2sk = gsi3sk = gsi4sk = gsi7sk_created_at = execution.created_at
    pk = gsi1pk = get_key(tenant=execution.tenant_id)
    sk = get_key(jit_event=execution.jit_event_id, run=execution.execution_id)
    gsi2pk = get_key(tenant=execution.tenant_id, status=execution.status)
    gsi3pk = get_key(tenant=execution.tenant_id, plan_item=execution.plan_item_slug)
    gsi4pk = get_key(tenant=execution.tenant_id, plan_item=execution.plan_item_slug,
                     status=execution.status)
    gsi5pk = get_key(tenant=execution.tenant_id, runner=execution.job_runner, status=execution.status)
    gsi5sk = get_key(priority=execution.priority.value, created_at=execution.created_at)
    gsi7pk_tenant_jit_event_id = get_key(tenant=execution.tenant_id, jit_event=execution.jit_event_id)
    return ExecutionEntity(
        PK=pk,
        SK=sk,
        GSI1PK=gsi1pk,
        GSI1SK=gsi1sk,
        GSI2PK=gsi2pk,
        GSI2SK=gsi2sk,
        GSI3PK=gsi3pk,
        GSI3SK=gsi3sk,
        GSI4PK=gsi4pk,
        GSI4SK=gsi4sk,
        GSI5PK=gsi5pk,
        GSI5SK=gsi5sk,
        GSI7PK_TENANT_JIT_EVENT_ID=gsi7pk_tenant_jit_event_id,
        GSI7SK_CREATED_AT=gsi7sk_created_at,
        **execution.dict(exclude_none=True)
    )


def write_executions_to_db(executions_manager, mock_executions):
    with executions_manager.table.batch_writer() as batch:
        for execution in mock_executions:
            executions_record = convert_execution_to_execution_entity(execution)
            batch.put_item(Item=executions_record.dict(exclude_none=True))
    return mock_executions


@pytest.fixture(scope="function")
def mock_executions(executions_manager):
    """
    Fixture that creates a mock execution and returns it
    """
    mock_executions = generate_mock_executions(20, MOCK_TENANT_ID)
    return write_executions_to_db(executions_manager, mock_executions)


@pytest.fixture(scope="function")
def mock_executions_same_jit_event(executions_manager):
    """
    Fixture that creates a mock execution and returns it
    """
    jit_event_id = str(uuid.uuid4())
    mock_executions = generate_mock_executions(20, MOCK_TENANT_ID, single_jit_event_id=jit_event_id)
    return write_executions_to_db(executions_manager, mock_executions), jit_event_id


def test_create_execution(executions_manager):
    """
    Test the creation of an execution
    """
    assert_db_item_length(executions_manager, 0)
    mock_execution = generate_mock_executions(1, MOCK_TENANT_ID)[0]
    executions_manager.create_execution(mock_execution)
    items = executions_manager.table.scan()["Items"]
    assert len(items) == 1
    assert Execution(**items[0]) == mock_execution


def test_create_execution__with_task_token(executions_manager):
    """
    Test the creation of an execution with task token
    """
    assert_db_item_length(executions_manager, 0)
    mock_task_token = "mock_task_token"
    mock_execution_with_task_token = generate_mock_executions(1, MOCK_TENANT_ID)[0]
    mock_execution_with_task_token.additional_attributes = {"task_token": mock_task_token}
    executions_manager.create_execution(mock_execution_with_task_token)
    items = executions_manager.table.scan()["Items"]
    assert len(items) == 1
    assert Execution(**items[0]) == mock_execution_with_task_token


def test_update_execution(executions_manager):
    """
    Test the update of an execution
    """
    assert_db_item_length(executions_manager, 0)
    execution = MOCK_EXECUTION.copy()
    execution.status = ExecutionStatus.RUNNING
    executions_manager.create_execution(execution)
    items = executions_manager.table.scan()["Items"]
    assert len(items) == 1
    assert Execution(**items[0]) == execution
    executions_manager.update_execution(MOCK_UPDATE_REQUEST, execution.plan_item_slug, execution.job_runner)
    items = executions_manager.table.scan()["Items"]
    assert len(items) == 1
    assert Execution(**items[0]) == Execution(
        **{**execution.dict(), **MOCK_UPDATE_REQUEST.dict(exclude_none=True)})


@pytest.mark.parametrize("execution_timeout, should_raise", [
    (None, True),
    ("2022-10-10T10:32:12", False),
])
def test_generate_update_execution_query__status_condition_succeeded(
        executions_manager, execution_timeout, should_raise
):
    """
    Test the generate_update_execution_query when the status condition succeeds
    """
    status: ExecutionStatus = ExecutionStatus.DISPATCHING
    assert_db_item_length(executions_manager, 0)
    mock_execution = generate_mock_executions(1, MOCK_TENANT_ID, ExecutionStatus.PENDING)[0]
    executions_manager.create_execution(mock_execution)
    items = executions_manager.table.scan()["Items"]
    assert len(items) == 1
    assert Execution(**items[0]) == mock_execution

    update_request = UpdateRequest(
        tenant_id=mock_execution.tenant_id,
        jit_event_id=mock_execution.jit_event_id,
        execution_id=mock_execution.execution_id,
        status=status,
        execution_timeout=execution_timeout,
    )

    if should_raise:
        with pytest.raises(ValueError):
            executions_manager.generate_update_execution_query(
                update_request, mock_execution.plan_item_slug, mock_execution.job_runner
            )
    else:
        update_execution_query = executions_manager.generate_update_execution_query(
            update_request, mock_execution.plan_item_slug, mock_execution.job_runner
        )
        executions_manager.execute_transaction([update_execution_query])
        items = executions_manager.table.scan()["Items"]
        assert len(items) == 1
        assert Execution(**items[0]).status == status


def test_generate_update_execution_query__status_condition_failed(executions_manager):
    """
    Test the update of an execution status when the status condition fails
    """
    status: ExecutionStatus = ExecutionStatus.DISPATCHING

    assert_db_item_length(executions_manager, 0)
    mock_execution = generate_mock_executions(1, MOCK_TENANT_ID, status)[0]
    executions_manager.create_execution(mock_execution)
    items = executions_manager.table.scan()["Items"]
    assert len(items) == 1
    assert Execution(**items[0]) == mock_execution

    update_request = UpdateRequest(
        tenant_id=mock_execution.tenant_id,
        jit_event_id=mock_execution.jit_event_id,
        execution_id=mock_execution.execution_id,
        status=status,
        execution_timeout="2022-19-12T12:13:23",
    )

    update_execution_query = executions_manager.generate_update_execution_query(update_request,
                                                                                mock_execution.plan_item_slug,
                                                                                mock_execution.job_runner)
    with pytest.raises(Exception):
        executions_manager.execute_transaction([update_execution_query])


def test_update_update_findings_upload_status__execution_not_exists(executions_manager):
    """
    Test the update upload findings status of an execution when execution not exists
    """
    assert_db_item_length(executions_manager, 0)

    with pytest.raises(Exception):
        executions_manager.update_findings_upload_status(
            MOCK_EXECUTION.tenant_id,
            MOCK_EXECUTION.jit_event_id,
            MOCK_EXECUTION.execution_id,
            UploadFindingsStatus.COMPLETED,
            plan_items_with_findings=['plan_item_1'],
            has_findings=True,
        )


def test_update_update_findings_upload_status__execution_exists_but_not_in_running_state(executions_manager):
    """
    Test the update upload findings status of an execution when execution exists but not in running state
    """
    assert_db_item_length(executions_manager, 0)
    mock_execution = generate_mock_executions(1, MOCK_TENANT_ID, ExecutionStatus.PENDING)[0]
    executions_manager.create_execution(mock_execution)
    items = executions_manager.table.scan()["Items"]
    assert len(items) == 1
    assert Execution(**items[0]) == mock_execution

    with pytest.raises(Exception):
        executions_manager.update_findings_upload_status(
            MOCK_EXECUTION.tenant_id,
            MOCK_EXECUTION.jit_event_id,
            MOCK_EXECUTION.execution_id,
            UploadFindingsStatus.COMPLETED,
            plan_items_with_findings=['plan_item_1'],
            has_findings=True,
        )


def test_update_update_findings_upload_status__execution_exists(executions_manager):
    """
    Test the update upload findings status of an execution when execution exists
    """
    assert_db_item_length(executions_manager, 0)
    mock_execution = generate_mock_executions(
        executions_amount=1, tenant_id=MOCK_TENANT_ID, status=ExecutionStatus.RUNNING,
        affected_plan_items=["plan_item_1", "plan_item_2"]
    )[0]
    mock_execution.has_findings = True
    executions_manager.create_execution(mock_execution)
    items = executions_manager.table.scan()["Items"]
    assert len(items) == 1
    assert Execution(**items[0]) == mock_execution

    execution = executions_manager.update_findings_upload_status(
        mock_execution.tenant_id,
        mock_execution.jit_event_id,
        mock_execution.execution_id,
        UploadFindingsStatus.COMPLETED,
        plan_items_with_findings=['plan_item_1'],
        has_findings=False,
    )
    assert execution == Execution(
        **{
            **mock_execution.dict(),
            "upload_findings_status": UploadFindingsStatus.COMPLETED,
            'affected_plan_items': ["plan_item_1", "plan_item_2"],
            'plan_items_with_findings': ['plan_item_1'],
            'has_findings': False,
        }
    )


def test_update_control_status__execution_not_exists(executions_manager):
    """
    Test the update control status of an execution when execution not exists
    """
    assert_db_item_length(executions_manager, 0)

    with pytest.raises(Exception, match=r".*ConditionalCheckFailedException.*"):
        executions_manager.update_control_completed_data(
            MOCK_EXECUTION.tenant_id,
            MOCK_EXECUTION.jit_event_id,
            MOCK_EXECUTION.execution_id,
            ExecutionStatus.COMPLETED,
            True,
            None,
            job_output={"test1": ["test2"]},
            stderr='some stderr output',
            errors=[ExecutionError(error_body="error message", error_type=ExecutionErrorType.CONTROL_ERROR)],
        )


def test_update_control_status__execution_exists_but_in_pending_state(executions_manager):
    """
    Test the update control status of an execution when execution exists but not in running state
    """
    assert_db_item_length(executions_manager, 0)
    mock_execution = generate_mock_executions(1, MOCK_TENANT_ID, ExecutionStatus.PENDING)[0]
    executions_manager.create_execution(mock_execution)
    items = executions_manager.table.scan()["Items"]
    assert len(items) == 1
    assert Execution(**items[0]) == mock_execution

    with pytest.raises(Exception, match=r".*ConditionalCheckFailedException.*"):
        executions_manager.update_control_completed_data(
            MOCK_EXECUTION.tenant_id,
            MOCK_EXECUTION.jit_event_id,
            MOCK_EXECUTION.execution_id,
            ExecutionStatus.COMPLETED,
            True,
            None,
            job_output={"test1": ["test2"]},
            stderr='some stderr output',
            errors=[ExecutionError(error_body="error message", error_type=ExecutionErrorType.CONTROL_ERROR)],
        )


@pytest.mark.parametrize('error_body', [None, 'error-123'])
@pytest.mark.parametrize('has_findings', [True, False])
@pytest.mark.parametrize('job_output', [None, {"test1": ["test2"]}])
@pytest.mark.parametrize('stderr', [None, 'some stderr output'])
@pytest.mark.parametrize('current_has_findings', [None, True, False])
@pytest.mark.parametrize('current_status', [
    ExecutionStatus.RUNNING, ExecutionStatus.DISPATCHING, ExecutionStatus.DISPATCHED
])
@pytest.mark.parametrize('errors', [
    [],
    [ExecutionError(error_body="error message", error_type=ExecutionErrorType.CONTROL_ERROR),
     ExecutionError(error_body="error message", error_type=ExecutionErrorType.USER_INPUT_ERROR)]
])
def test_update_control_status__execution_exists(
        executions_manager,
        has_findings,
        error_body,
        job_output,
        current_status,
        current_has_findings,
        stderr,
        errors,

):
    """
    Test the update control status of an execution when execution exists
    """
    assert_db_item_length(executions_manager, 0)
    mock_execution = generate_mock_executions(1, MOCK_TENANT_ID, current_status)[0]
    mock_execution.has_findings = current_has_findings
    executions_manager.create_execution(mock_execution)
    items = executions_manager.table.scan()["Items"]
    assert len(items) == 1
    assert Execution(**items[0]) == mock_execution

    execution = executions_manager.update_control_completed_data(
        mock_execution.tenant_id,
        mock_execution.jit_event_id,
        mock_execution.execution_id,
        ExecutionStatus.COMPLETED,
        has_findings,
        error_body,
        job_output,
        stderr,
        errors,
    )
    if current_has_findings is None:
        expected_has_findings = has_findings
    else:
        expected_has_findings = current_has_findings
    assert execution == Execution(
        **{
            **mock_execution.dict(),
            "control_status": ExecutionStatus.COMPLETED,
            "has_findings": expected_has_findings,
            "error_body": error_body,
            "job_output": job_output,
            "control_type": ControlType.DETECTION,
            "stderr": stderr,
            "errors": errors,
        },
    )


def test_get_execution_by_jit_event_id_and_execution_id(executions_manager):
    """
    Test the retrieval of an execution by its JIT event ID and run ID
    """
    assert_db_item_length(executions_manager, 0)
    executions_manager.create_execution(MOCK_EXECUTION)
    items = executions_manager.table.scan()["Items"]
    assert len(items) == 1
    assert Execution(**items[0]) == MOCK_EXECUTION
    execution = executions_manager.get_execution_by_jit_event_id_and_execution_id(MOCK_EXECUTION.tenant_id,
                                                                                  MOCK_EXECUTION.jit_event_id,
                                                                                  MOCK_EXECUTION.execution_id)
    assert execution == MOCK_EXECUTION


def test_get_execution_by_jit_event_id_and_execution_id_not_found(executions_manager):
    """
    Test the retrieval of an execution by its JIT event ID and run ID when it is not found
    """
    assert_db_item_length(executions_manager, 0)
    execution = executions_manager.get_execution_by_jit_event_id_and_execution_id(MOCK_EXECUTION.tenant_id,
                                                                                  MOCK_EXECUTION.jit_event_id,
                                                                                  MOCK_EXECUTION.execution_id)
    assert execution is None


def test_get_next_execution_to_run_by_tenant_id_and_runner_and_status__time_factor(executions_manager, mock_executions):
    """
    Test the retrieval of the oldest execution by tenant ID, runner and status
    """
    # The oldest execution is the first one - that's because of the way the fixture creates them
    expected_next_execution = mock_executions[0]
    execution = executions_manager.get_next_execution_to_run(
        expected_next_execution.tenant_id, expected_next_execution.job_runner)
    assert execution == expected_next_execution


def test_get_next_execution_to_run_by_tenant_id_and_runner_and_status__priority_factor(executions_manager,
                                                                                       mock_executions):
    """
    Test the retrieval of the oldest execution by tenant ID, runner and status
    """
    # The oldest execution is the first one - that's because of the way the fixture creates them
    expected_next_execution = Execution(**mock_executions[0].dict())
    expected_next_execution.priority = ExecutionPriority.HIGH.value
    expected_next_execution.created_at = (datetime.fromisoformat(expected_next_execution.created_at) + timedelta(
        seconds=100)).isoformat()
    executions_manager.create_execution(expected_next_execution)

    execution = executions_manager.get_next_execution_to_run(
        expected_next_execution.tenant_id, expected_next_execution.job_runner)
    assert execution == expected_next_execution


@pytest.mark.parametrize("execution_timeout", [
    None,
    "2022-10-11T10:10:11",
])
def test_update_status_dispatched_execution__success(executions_manager, execution_timeout):
    """
    Test the update of an execution
    """
    assert_db_item_length(executions_manager, 0)
    mock_execution = Execution(**{
        **MOCK_EXECUTION.dict(),
        "status": ExecutionStatus.DISPATCHING.value,
        "dispatched_at": None,
        "dispatched_at_ts": None,

    })
    executions_manager.create_execution(mock_execution)
    assert_db_item_length(executions_manager, 1)

    dispatched_at = datetime.utcnow()
    update_request = UpdateRequest(
        tenant_id=mock_execution.tenant_id,
        jit_event_id=mock_execution.jit_event_id,
        execution_id=mock_execution.execution_id,
        status=ExecutionStatus.DISPATCHED,
        dispatched_at=dispatched_at.isoformat(),
        dispatched_at_ts=int(dispatched_at.timestamp()),
        execution_timeout=execution_timeout,
    )

    if not execution_timeout:
        with pytest.raises(ValueError):
            executions_manager.update_execution(
                update_request=update_request,
                plan_item_slug=mock_execution.plan_item_slug,
                job_runner=mock_execution.job_runner,
            )
    else:
        executions_manager.update_execution(
            update_request=update_request,
            plan_item_slug=mock_execution.plan_item_slug,
            job_runner=mock_execution.job_runner,
        )
        items = executions_manager.table.scan()["Items"]
        assert len(items) == 1
        expected_execution = Execution(**{
            **MOCK_EXECUTION.dict(),
            "status": ExecutionStatus.DISPATCHED.value,
            "dispatched_at": dispatched_at.isoformat(),
            "dispatched_at_ts": int(dispatched_at.timestamp()),
            "execution_timeout": execution_timeout,
        })
        assert Execution(**items[0]) == expected_execution
        assert items[0][GSI2PK] == get_key(tenant=mock_execution.tenant_id, status=ExecutionStatus.DISPATCHED.value)
        assert items[0][GSI4PK] == get_key(tenant=mock_execution.tenant_id,
                                           plan_item=mock_execution.plan_item_slug,
                                           status=ExecutionStatus.DISPATCHED.value)
        assert items[0][GSI5PK] == get_key(tenant=mock_execution.tenant_id,
                                           runner=mock_execution.job_runner,
                                           status=ExecutionStatus.DISPATCHED.value)


@pytest.mark.parametrize('old_status, new_status, expected_error', [
    # some status -> DISPATCHED
    (ExecutionStatus.PENDING, ExecutionStatus.DISPATCHED, ClientError),
    (ExecutionStatus.DISPATCHED, ExecutionStatus.DISPATCHED, StatusTransitionException),
    (ExecutionStatus.RUNNING, ExecutionStatus.DISPATCHED, StatusTransitionException),
    (ExecutionStatus.COMPLETED, ExecutionStatus.DISPATCHED, StatusTransitionException),
    (ExecutionStatus.FAILED, ExecutionStatus.DISPATCHED, StatusTransitionException),
    (ExecutionStatus.CONTROL_TIMEOUT, ExecutionStatus.DISPATCHED, StatusTransitionException),
    (ExecutionStatus.WATCHDOG_TIMEOUT, ExecutionStatus.DISPATCHED, StatusTransitionException),
    # some status -> RUNNING
    (ExecutionStatus.PENDING, ExecutionStatus.RUNNING, ClientError),
    (ExecutionStatus.RUNNING, ExecutionStatus.RUNNING, StatusTransitionException),
    (ExecutionStatus.COMPLETED, ExecutionStatus.RUNNING, StatusTransitionException),
    (ExecutionStatus.FAILED, ExecutionStatus.RUNNING, StatusTransitionException),
    (ExecutionStatus.CONTROL_TIMEOUT, ExecutionStatus.RUNNING, StatusTransitionException),
    (ExecutionStatus.WATCHDOG_TIMEOUT, ExecutionStatus.RUNNING, StatusTransitionException),
    # non PENDING status -> CANCELED
    (ExecutionStatus.DISPATCHED, ExecutionStatus.CANCELED, ClientError),
    (ExecutionStatus.RUNNING, ExecutionStatus.CANCELED, ClientError),
    (ExecutionStatus.COMPLETED, ExecutionStatus.CANCELED, MultipleCompletesExceptions),
    (ExecutionStatus.FAILED, ExecutionStatus.CANCELED, MultipleCompletesExceptions),
    (ExecutionStatus.CONTROL_TIMEOUT, ExecutionStatus.CANCELED, MultipleCompletesExceptions),
    (ExecutionStatus.WATCHDOG_TIMEOUT, ExecutionStatus.CANCELED, MultipleCompletesExceptions),
    (ExecutionStatus.CANCELED, ExecutionStatus.CANCELED, MultipleCompletesExceptions),
])
def test_update_status_execution__failure(executions_manager, old_status, new_status, expected_error):
    """
    Test the update of an execution
    """
    assert_db_item_length(executions_manager, 0)
    mock_execution = Execution(**{
        **MOCK_EXECUTION.dict(),
        "status": old_status.value,
        "dispatched_at": None,
        "dispatched_at_ts": None
    })
    executions_manager.create_execution(mock_execution)
    assert_db_item_length(executions_manager, 1)

    dispatched_at = datetime.utcnow()
    update_request = UpdateRequest(
        tenant_id=mock_execution.tenant_id,
        jit_event_id=mock_execution.jit_event_id,
        execution_id=mock_execution.execution_id,
        status=new_status,
        dispatched_at=dispatched_at.isoformat(),
        dispatched_at_ts=int(dispatched_at.timestamp()),
        execution_timeout="2022-10-11T19:13:33",
    )

    # Try to update the execution - this should fail
    with pytest.raises(expected_error):
        executions_manager.update_execution(update_request=update_request,
                                            plan_item_slug=mock_execution.plan_item_slug,
                                            job_runner=mock_execution.job_runner)


def test_update_execution__to_non_execution_timeout_status(executions_manager):
    assert_db_item_length(executions_manager, 0)
    mock_execution = Execution(**{
        **MOCK_EXECUTION.dict(),
        "status": ExecutionStatus.RUNNING.value,
        "execution_timeout": "2022-10-20T10:20:32",
    })
    executions_manager.create_execution(mock_execution)
    assert_db_item_length(executions_manager, 1)

    update_request = UpdateRequest(
        tenant_id=mock_execution.tenant_id,
        jit_event_id=mock_execution.jit_event_id,
        execution_id=mock_execution.execution_id,
        status=ExecutionStatus.COMPLETED,
    )

    updated_execution = executions_manager.update_execution(
        update_request=update_request,
        plan_item_slug=mock_execution.plan_item_slug,
        job_runner=mock_execution.job_runner,
    )

    assert updated_execution


def test_get_executions_by_tenant_id_and_jit_event(executions_manager, mock_executions_same_jit_event):
    """
    Test the retrieval of all executions by tenant ID and JIT event ID
    """
    mock_executions, jit_event_id = mock_executions_same_jit_event
    executions, last_key = executions_manager.get_executions_by_tenant_id_and_jit_event(
        MOCK_EXECUTION.tenant_id,
        jit_event_id,
        limit=len(mock_executions),
        start_key={}
    )

    assert len(executions) == len(mock_executions)
    assert all(execution in mock_executions for execution in executions)
    assert last_key == {}


def test_get_executions_by_tenant_id_and_jit_event_and_limit(executions_manager, mock_executions_same_jit_event):
    """
    Test the retrieval of all executions by tenant ID, JIT event ID, and limit
    """
    mock_executions, jit_event_id = mock_executions_same_jit_event
    executions, last_key = executions_manager.get_executions_by_tenant_id_and_jit_event(
        MOCK_EXECUTION.tenant_id,
        jit_event_id,
        limit=len(mock_executions) - 1,
        start_key={}
    )

    assert len(executions) == len(mock_executions) - 1
    copy_of_mock_executions = mock_executions.copy()
    assert all(execution in copy_of_mock_executions for execution in executions)
    for execution in executions:
        copy_of_mock_executions.remove(execution)

    expected_next_execution = mock_executions[1]
    expected_last_key = {
        PK: get_key(tenant=expected_next_execution.tenant_id),
        SK: get_key(jit_event=expected_next_execution.jit_event_id, run=expected_next_execution.execution_id),
        GSI7PK_TENANT_JIT_EVENT_ID: get_key(tenant=expected_next_execution.tenant_id,
                                            jit_event=expected_next_execution.jit_event_id),
        GSI7SK_CREATED_AT: expected_next_execution.created_at
    }
    assert last_key == expected_last_key


def test_get_executions_by_tenant_id_and_jit_event_and_start_key(executions_manager, mock_executions_same_jit_event):
    """
    Test the retrieval of all executions by tenant ID, JIT event ID, and start key
    """
    mock_executions, jit_event_id = mock_executions_same_jit_event
    expected_next_execution = mock_executions[15]
    start_key = {
        PK: get_key(tenant=expected_next_execution.tenant_id),
        SK: get_key(jit_event=expected_next_execution.jit_event_id, run=expected_next_execution.execution_id)
    }
    executions, last_key = executions_manager.get_executions_by_tenant_id_and_jit_event(
        MOCK_EXECUTION.tenant_id,
        jit_event_id,
        limit=len(mock_executions),
        start_key=start_key
    )
    assert len(executions) == 15
    assert all(execution in mock_executions for execution in executions)


def test_insert_execution_data(executions_manager):
    """
    Test the insertion of execution data
    """
    assert_db_item_length(executions_manager, 0)
    executions_manager.insert_execution_data(MOCK_EXECUTION_DATA)
    assert_db_item_length(executions_manager, 1)
    assert executions_manager.table.scan()["Items"][0] == ExecutionDataEntity(
        **MOCK_EXECUTION_DATA.dict(),
        PK="TENANT#tenant_id#JIT_EVENT#jit_event_id",
        SK="EXECUTION#execution_id#ENTITY#execution_data",
        GSI1PK="TENANT#tenant_id",
        GSI1SK="created_at",
    ).dict(exclude_none=True)


def test_get_execution_data(executions_manager):
    """
    Test the retrieval of execution data
    """
    executions_manager.write_multiple_execution_data([MOCK_EXECUTION_DATA])
    execution_data = executions_manager.get_execution_data(
        tenant_id=MOCK_EXECUTION_DATA.tenant_id,
        jit_event_id=MOCK_EXECUTION_DATA.jit_event_id,
        execution_id=MOCK_EXECUTION_DATA.execution_id,
    )
    assert execution_data == MOCK_EXECUTION_DATA

    with pytest.raises(ExecutionDataNotFoundException):
        executions_manager.get_execution_data(
            tenant_id="not-exist",
            jit_event_id="not-exist",
            execution_id="not-exist",
        )


class TestExecutionsManager:
    CI_HIGH_PRIORITY_EXECUTION = generate_mock_executions(executions_amount=1,
                                                          job_runner=Runner.CI,
                                                          priority=ExecutionPriority.HIGH,
                                                          created_at=datetime.now())[0]
    CI_LOW_PRIORITY_EXECUTION = generate_mock_executions(executions_amount=1,
                                                         job_runner=Runner.CI,
                                                         priority=ExecutionPriority.LOW,
                                                         created_at=datetime.now())[0]
    CI_OLD_LOW_PRIORITY_EXECUTION = generate_mock_executions(executions_amount=1,
                                                             job_runner=Runner.CI,
                                                             priority=ExecutionPriority.LOW,
                                                             created_at=datetime.now() - timedelta(days=1))[0]
    GITHUB_ACTIONS_HIGH_PRIORITY_EXECUTION = generate_mock_executions(executions_amount=1,
                                                                      job_runner=Runner.GITHUB_ACTIONS,
                                                                      priority=ExecutionPriority.HIGH,
                                                                      created_at=datetime.now())[0]
    GITHUB_ACTIONS_LOW_PRIORITY_EXECUTION = generate_mock_executions(executions_amount=1,
                                                                     job_runner=Runner.GITHUB_ACTIONS,
                                                                     priority=ExecutionPriority.LOW,
                                                                     created_at=datetime.now())[0]
    JIT_HIGH_PRIORITY_EXECUTION = generate_mock_executions(executions_amount=1,
                                                           job_runner=Runner.JIT,
                                                           priority=ExecutionPriority.HIGH,
                                                           created_at=datetime.now())[0]
    JIT_LOW_PRIORITY_EXECUTION = generate_mock_executions(executions_amount=1,
                                                          job_runner=Runner.JIT,
                                                          priority=ExecutionPriority.LOW,
                                                          created_at=datetime.now())[0]

    @pytest.mark.parametrize(
        "runner, executions_to_insert, expected_execution",
        [
            pytest.param(Runner.CI, [CI_HIGH_PRIORITY_EXECUTION], CI_HIGH_PRIORITY_EXECUTION,
                         id="CI Runner with only high priority execution"),
            pytest.param(Runner.CI,
                         [CI_LOW_PRIORITY_EXECUTION, CI_HIGH_PRIORITY_EXECUTION],
                         CI_HIGH_PRIORITY_EXECUTION,
                         id="CI Runner with high and low priority executions, choose high priority"),
            pytest.param(Runner.CI,
                         [CI_LOW_PRIORITY_EXECUTION, CI_OLD_LOW_PRIORITY_EXECUTION],
                         CI_OLD_LOW_PRIORITY_EXECUTION,
                         id="CI Runner with old and new executions, choose the oldest"),
            pytest.param(Runner.JIT,
                         [CI_HIGH_PRIORITY_EXECUTION, CI_LOW_PRIORITY_EXECUTION,
                          GITHUB_ACTIONS_HIGH_PRIORITY_EXECUTION, GITHUB_ACTIONS_LOW_PRIORITY_EXECUTION],
                         None,
                         id="Runner not mathing any of the executions"),
            pytest.param(Runner.GITHUB_ACTIONS,
                         [CI_LOW_PRIORITY_EXECUTION],
                         CI_LOW_PRIORITY_EXECUTION,
                         id="GitHub Actions Runner with CI execution, choose it for backward compatibility"),
        ]
    )
    def test_get_next_execution_to_run(self,
                                       executions_manager: ExecutionsManager,
                                       runner: Runner,
                                       executions_to_insert: Optional[List[Execution]],
                                       expected_execution: Optional[Execution]):
        write_executions_to_db(executions_manager, executions_to_insert)

        next_execution = executions_manager.get_next_execution_to_run(
            tenant_id=MOCK_TENANT_ID,
            runner=runner)

        assert next_execution == expected_execution


def _create_and_insert_executions(executions_manager, executions_to_generate: int, executions_to_insert: int):
    """
    Helper function to setup executions for testing.

    Args:
        executions_manager: The executions manager instance.
        executions_to_generate: The total number of executions to create.
        executions_to_insert: The number of executions to insert into the database.

        We might not insert all the executions to test the case where some executions are missing.

    Returns:
        Execution identifiers including all the `execution_id`s, and a list of the Executions that were inserted.
    """
    executions: List[Execution] = []
    for _ in range(executions_to_generate):
        execution = ExecutionFactory().build(
            tenant_id=MOCK_TENANT_ID,
            context=MOCK_EXECUTION_CONTEXT_CODE_EXECUTION,
            asset_id="some_asset_id",
            jit_event_id="123456"
        )
        if len(executions) < executions_to_insert:
            executions_manager.create_execution(execution)
        executions.append(execution)

    multiple_execution_identifiers = MultipleExecutionsIdentifiers.group_by_jit_event_id(executions)[0]
    return multiple_execution_identifiers, executions[:executions_to_insert]


def test_get_executions_for_multiple_identifiers(executions_manager):
    """
    Test the batch retrieval of multiple executions by their identifiers.

    Setup:
        - Create 120 Execution objects to guarantee we cross the max batch get item limit
        - Insert all 120 executions into the database

    Test:
        - Retrieve the executions for the identifiers in the Setup by calling `get_executions_for_multiple_identifiers`

    Assert:
        - Assert that the number of retrieved executions is equal to the number of inserted executions
        - Assert that each retrieved execution_id is in the list of `execution_id`s from the created executions.
    """
    TOTAL_EXECUTIONS_TO_GENERATE = 120
    TOTAL_EXECUTIONS_TO_INSERT = TOTAL_EXECUTIONS_TO_GENERATE

    execution_identifiers, inserted_executions = _create_and_insert_executions(
        executions_manager=executions_manager,
        executions_to_generate=TOTAL_EXECUTIONS_TO_GENERATE,
        executions_to_insert=TOTAL_EXECUTIONS_TO_INSERT
    )

    retrieved_executions = executions_manager.get_executions_for_multiple_identifiers(execution_identifiers)

    assert len(retrieved_executions) == len(inserted_executions)

    for retrieved_execution in retrieved_executions:
        assert retrieved_execution.execution_id in [execution.execution_id for execution in inserted_executions]


def test_get_executions_for_multiple_identifiers__missing_executions(executions_manager):
    """
    Test the batch retrieval when some of the executions are missing from the database.

    Setup:
        - Create 120 Execution objects to guarantee we cross the max batch get item limit
        - Only insert the first 10 into the database

    Test:
        - Retrieve the executions for the identifiers in the Setup by calling `get_executions_for_multiple_identifiers`

    Assert:
        - Assert that the number of retrieved executions is equal to the number of inserted executions
        - Assert that each retrieved execution_id is in the list of `execution_id`s from the inserted executions.
        - Assert that the number of missing executions is as expected (120 - 10 = 110)
    """
    TOTAL_EXECUTIONS_TO_GENERATE = 120
    TOTAL_EXECUTIONS_TO_INSERT = 10

    execution_identifiers, inserted_executions = _create_and_insert_executions(
        executions_manager=executions_manager,
        executions_to_generate=TOTAL_EXECUTIONS_TO_GENERATE,
        executions_to_insert=TOTAL_EXECUTIONS_TO_INSERT
    )

    retrieved_executions = executions_manager.get_executions_for_multiple_identifiers(execution_identifiers)

    assert len(retrieved_executions) == len(inserted_executions)

    for retrieved_execution in retrieved_executions:
        assert retrieved_execution.execution_id in [execution.execution_id for execution in inserted_executions]

    inserted_execution_ids = set(execution.execution_id for execution in inserted_executions)
    missing_execution_ids = set(execution_identifiers.execution_ids) - inserted_execution_ids
    assert len(missing_execution_ids) == TOTAL_EXECUTIONS_TO_GENERATE - TOTAL_EXECUTIONS_TO_INSERT


def test_write_multiple_execution_data(executions_manager):
    """
    Test the batch writing of multiple execution data to DynamoDB.

    Setup:
        - Create a list of ExecutionData objects, each with a unique execution_id.

    Test:
        - Perform the batch write of the ExecutionData objects using `write_multiple_execution_data`.

    Assert:
        - Assert that the number of submitted records is equal to the number of ExecutionData objects created.
        - Assert that each record submitted to the database is a valid ExecutionDataEntity object.
        - Assert that each ExecutionData object in DynamoDB is from the list of ExecutionData objects we created.
    """
    NUMBER_OF_EXECUTIONS_TO_GENERATE = 5

    assert_db_item_length(executions_manager, 0)

    mock_execution_data_list = [
        ExecutionData(
            execution_data_json=json.dumps({"key": "value"}),
            created_at=str(datetime.now()),
            tenant_id=MOCK_EXECUTION_DATA.tenant_id,
            jit_event_id=MOCK_EXECUTION_DATA.jit_event_id,
            execution_id=str(uuid.uuid4()),  # different execution IDs to create multiple items
        ) for _ in range(NUMBER_OF_EXECUTIONS_TO_GENERATE)
    ]

    executions_manager.write_multiple_execution_data(mock_execution_data_list)

    assert_db_item_length(executions_manager, NUMBER_OF_EXECUTIONS_TO_GENERATE)

    for execution_data in mock_execution_data_list:
        execution_data_entity = ExecutionDataEntity(
            **execution_data.dict(),
            PK=f"TENANT#{execution_data.tenant_id}#JIT_EVENT#{execution_data.jit_event_id}",
            SK=f"EXECUTION#{execution_data.execution_id}#ENTITY#execution_data",
        )
        items = executions_manager.table.scan()["Items"]
        assert execution_data_entity.dict(exclude_none=True) in items

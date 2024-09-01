import json
import uuid
from datetime import datetime
from http import HTTPStatus
from typing import Dict, Optional

import pytest
from dateutil import parser
from pydantic import BaseModel

from jit_utils.models.execution import Execution
from jit_utils.jit_event_names import JitEventName
from jit_utils.models.execution_context import RunnerSetup

from src.handlers.update_execution import register_handler
from src.handlers.update_execution import vendor_job_start_handler
from src.lib.constants import CI_RUNNER_EXECUTION_TIMEOUT
from src.lib.constants import MINUTE_IN_SECONDS
from src.lib.constants import WATCHDOG_GRACE_PERIOD
from src.lib.data.executions_manager import ExecutionsManager
from src.lib.models.execution_models import ExecutionStatus

from tests.component.fixtures import _mock_events_client
from tests.component.fixtures import _prepare_execution_register_event
from tests.component.fixtures import _prepare_execution_to_update
from tests.component.fixtures import _prepare_job_start_event
from tests.mocks.execution_mocks import MOCK_EXECUTION


class RegisterHandlerTestCase(BaseModel):
    jit_event_name: JitEventName
    status: ExecutionStatus
    config: Optional[Dict] = None
    runner_setup: Optional[RunnerSetup] = None

    expected_timeout_seconds: Optional[int]
    expected_status_code: int = HTTPStatus.OK


class TestRegisterHandler:
    @pytest.mark.parametrize(
        "test_case",
        [
            pytest.param(RegisterHandlerTestCase(
                status=ExecutionStatus.DISPATCHING,
                jit_event_name=JitEventName.PullRequestCreated,
                expected_timeout_seconds=CI_RUNNER_EXECUTION_TIMEOUT,
            ), id="PR related event"),
            pytest.param(RegisterHandlerTestCase(
                status=ExecutionStatus.DISPATCHING,
                jit_event_name=JitEventName.MergeDefaultBranch,
                expected_timeout_seconds=2 * CI_RUNNER_EXECUTION_TIMEOUT,
            ), id="Non-PR related event"),
            pytest.param(RegisterHandlerTestCase(
                status=ExecutionStatus.DISPATCHING,
                jit_event_name=JitEventName.PullRequestCreated,
                runner_setup=RunnerSetup(timeout_minutes=10),
                expected_timeout_seconds=10 * MINUTE_IN_SECONDS,
            ), id="Custom timeout"),
            pytest.param(RegisterHandlerTestCase(
                status=ExecutionStatus.DISPATCHED,
                jit_event_name=JitEventName.PullRequestCreated,
                expected_timeout_seconds=CI_RUNNER_EXECUTION_TIMEOUT,
            ), id="Already dispatched"),
            pytest.param(RegisterHandlerTestCase(
                status=ExecutionStatus.DISPATCHED,
                jit_event_name=JitEventName.PullRequestCreated,
                runner_setup=RunnerSetup(timeout_minutes=10),
                expected_timeout_seconds=10 * MINUTE_IN_SECONDS,
            ), id="Already dispatched with custom timeout"),
            pytest.param(RegisterHandlerTestCase(
                status=ExecutionStatus.DISPATCHING,
                jit_event_name=JitEventName.PullRequestCreated,
                config={
                    "resource_management": {
                        "runner_config": {
                            "job_execution_timeout_minutes": 15,
                            "pr_job_setup_timeout_minutes": 5,
                            "pr_job_execution_timeout_minutes": 20,
                        },
                    },
                },
                expected_timeout_seconds=20 * MINUTE_IN_SECONDS,
            ), id="Custom timeout in config for PR related event"),
            pytest.param(RegisterHandlerTestCase(
                status=ExecutionStatus.DISPATCHING,
                jit_event_name=JitEventName.ItemActivated,
                config={
                    "resource_management": {
                        "runner_config": {
                            "job_execution_timeout_minutes": 25,
                            "pr_job_execution_timeout_minutes": 5,
                        },
                    },
                },
                expected_timeout_seconds=25 * MINUTE_IN_SECONDS,
            ), id="Custom timeout in config for non-PR related event"),
            pytest.param(RegisterHandlerTestCase(
                status=ExecutionStatus.DISPATCHED,
                jit_event_name=JitEventName.ItemActivated,
                config={
                    "resource_management": {
                        "runner_config": {
                            "job_execution_timeout_minutes": 10,
                        },
                    },
                },
                expected_timeout_seconds=10 * MINUTE_IN_SECONDS,
            ), id="Custom timeout in config for non-PR related event and already dispatched"),
            pytest.param(RegisterHandlerTestCase(
                status=ExecutionStatus.DISPATCHED,
                jit_event_name=JitEventName.PullRequestCreated,
                config={
                    "resource_management": {
                        "runner_config": {
                            "pr_job_execution_timeout_minutes": 25,
                        },
                    },
                },
                expected_timeout_seconds=25 * MINUTE_IN_SECONDS,
            ), id="Custom timeout in config for PR related event and already dispatched"),
            pytest.param(RegisterHandlerTestCase(
                status=ExecutionStatus.PENDING,
                jit_event_name=JitEventName.PullRequestCreated,
                expected_status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            ), id="Pending execution should fail"),
        ] + [  # Generating test cases for all possible conflict statuses
            pytest.param(RegisterHandlerTestCase(
                status=conflict_status,
                jit_event_name=JitEventName.PullRequestCreated,
                expected_status_code=HTTPStatus.CONFLICT,
            ), id=f"Conflict status: {conflict_status}")
            for conflict_status in [
                ExecutionStatus.RUNNING,
                ExecutionStatus.COMPLETED,
                ExecutionStatus.FAILED,
                ExecutionStatus.CONTROL_TIMEOUT,
                ExecutionStatus.WATCHDOG_TIMEOUT]
        ]
    )
    def test_register_handler(
            self,
            executions_manager: ExecutionsManager,
            mocker,
            test_case: RegisterHandlerTestCase,
    ):
        tenant_id = str(uuid.uuid4())
        jit_event_id = str(uuid.uuid4())
        execution_id = str(uuid.uuid4())

        _prepare_execution_to_update(
            executions_manager=executions_manager,
            tenant_id=tenant_id,
            jit_event_id=jit_event_id,
            execution_id=execution_id,
            status=test_case.status,
            runner_setup=test_case.runner_setup,
            jit_event_name=test_case.jit_event_name,
            config=test_case.config,
        )

        event = _prepare_execution_register_event(
            tenant_id=tenant_id,
            jit_event_id=jit_event_id,
            execution_id=execution_id)
        _mock_events_client(mocker)

        response = register_handler(event, {})

        if test_case.expected_status_code == HTTPStatus.OK:
            assert response["statusCode"] == HTTPStatus.OK
            execution = Execution(**json.loads(response["body"]))
            assert execution.tenant_id == tenant_id
            assert execution.jit_event_id == jit_event_id
            assert execution.execution_id == execution_id
            assert execution.status == ExecutionStatus.RUNNING
            watchdog_timeout_delta = parser.parse(execution.execution_timeout) - datetime.utcnow()
            is_watchdog_timeout_as_expected = (
                    test_case.expected_timeout_seconds <
                    watchdog_timeout_delta.seconds <
                    test_case.expected_timeout_seconds + WATCHDOG_GRACE_PERIOD
            )
            assert is_watchdog_timeout_as_expected
        else:
            assert response["statusCode"] == test_case.expected_status_code


def test_start_handler(executions_manager, mock_create_executions):
    run_id = "007"
    executions, _ = executions_manager.get_executions_by_tenant_id_and_jit_event(
        MOCK_EXECUTION.tenant_id, mock_create_executions[0].jit_event_id, limit=1, start_key={}
    )

    execution_id = executions[0].execution_id
    jit_event_id = executions[0].jit_event_id
    assert executions[0].run_id is None

    event = _prepare_job_start_event(MOCK_EXECUTION.tenant_id, jit_event_id, execution_id, run_id)

    response = vendor_job_start_handler(event, {})

    assert response["statusCode"] == HTTPStatus.OK

    executions, _ = executions_manager.get_executions_by_tenant_id_and_jit_event(
        MOCK_EXECUTION.tenant_id, jit_event_id, limit=1, start_key={}
    )
    assert executions[0].run_id == run_id


def test_start_handler__server_error_execution_doesnt_exist(executions_manager):
    run_id = "007"
    tenant_id = str(uuid.uuid4())
    jit_event_id = str(uuid.uuid4())
    execution_id = str(uuid.uuid4())

    event = _prepare_job_start_event(tenant_id, jit_event_id, execution_id, run_id)

    response = vendor_job_start_handler(event, {})

    assert response["statusCode"] == HTTPStatus.INTERNAL_SERVER_ERROR


def test_start_handler__client_error_job_id_not_provided(executions_manager):
    event = _prepare_job_start_event(MOCK_EXECUTION.tenant_id, "aaa", "bbb")
    response = vendor_job_start_handler(event, {})
    assert response["statusCode"] == HTTPStatus.BAD_REQUEST

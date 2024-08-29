from uuid import UUID

import pytest
from dateutil.parser import parse
from freezegun import freeze_time
from unittest.mock import MagicMock

from jit_utils.event_models.trigger_event import TriggerExecutionEvent
from jit_utils.models.execution_context import Runner
from jit_utils.models.execution_priority import ExecutionPriority
from jit_utils.models.execution import Execution

from test_utils.aws import idempotency

from src.lib.cores import create_execution
from src.lib.models.execution_models import ExecutionStatus

from tests.mocks.execution_mocks import generate_mock_executions
from tests.mocks.execution_mocks import MOCK_TENANT_ID


@pytest.mark.parametrize('mock_execution', [
    generate_mock_executions(1, MOCK_TENANT_ID, job_runner=Runner.CI)[0],
    generate_mock_executions(1, MOCK_TENANT_ID, job_runner=Runner.JIT)[0]
])
@freeze_time("2022-12-05")
def test_create_execution_core(mocker, mock_execution):
    """
    Test that the create_execution_core function creates an execution
    """
    idempotency.mock_idempotent_decorator(
        mocker=mocker,
        module_to_reload=create_execution,
        decorator_name='idempotent_function',
    )

    mocked_execution_manager = MagicMock()
    mocked_execution_manager.create_execution = MagicMock(lambda execution: execution)

    mocker.patch(
        target='jit_utils.models.execution.uuid4',
        return_value=UUID(mock_execution.execution_id),
    )

    mock_jit_event_attribute = mock_execution.context.jit_event
    trigger_execution_event = TriggerExecutionEvent(**{**mock_execution.dict(),
                                                       "jit_event": mock_jit_event_attribute,
                                                       "steps": mock_execution.context.job.steps
                                                       })
    mock_asset = trigger_execution_event.context.asset
    create_execution.trigger_execution(trigger_execution_event, mocked_execution_manager)
    # fix the assert
    mocked_execution_manager.create_execution.assert_called_once_with(
        Execution(
            **trigger_execution_event.dict(), **mock_jit_event_attribute.dict(), vendor=mock_asset.vendor,
            created_at_ts=int(parse(trigger_execution_event.created_at).timestamp()),
            asset_name=mock_asset.asset_name, status=ExecutionStatus.PENDING,
            asset_type=mock_asset.asset_type, execution_id=mock_execution.execution_id,
            control_name=mock_execution.context.job.steps[0].name,
            control_image=mock_execution.context.job.steps[0].uses,
            priority=ExecutionPriority.LOW,
        )
    )


@freeze_time("2022-12-05")
def test_create_execution_core_with_task_token(mocker):
    """
    Test that the create_execution_core function creates an execution with task token
    """
    idempotency.mock_idempotent_decorator(
        mocker=mocker,
        module_to_reload=create_execution,
        decorator_name='idempotent_function',
    )

    mock_task_token = "mock_task_token"
    mock_execution = generate_mock_executions(1, MOCK_TENANT_ID)[0]

    mocked_execution_manager = MagicMock()
    mocked_execution_manager.create_execution = MagicMock(lambda execution: execution)

    mocker.patch(
        target='jit_utils.models.execution.uuid4',
        return_value=UUID(mock_execution.execution_id),
    )

    mock_jit_event_attribute = mock_execution.context.jit_event
    trigger_execution_event = TriggerExecutionEvent(
        **{**
           mock_execution.dict(),
           "jit_event": mock_jit_event_attribute,
           "steps": mock_execution.context.job.steps})
    mock_asset = trigger_execution_event.context.asset

    create_execution.trigger_execution(
        trigger_event=trigger_execution_event,
        executions_manager=mocked_execution_manager,
        task_token=mock_task_token,
    )
    mocked_execution_manager.create_execution.assert_called_once_with(Execution(
        **trigger_execution_event.dict(), **mock_jit_event_attribute.dict(), vendor=mock_asset.vendor,
        created_at_ts=int(parse(trigger_execution_event.created_at).timestamp()),
        asset_name=mock_asset.asset_name, status=ExecutionStatus.PENDING,
        asset_type=mock_asset.asset_type, execution_id=mock_execution.execution_id,
        control_name=mock_execution.context.job.steps[0].name, control_image=mock_execution.context.job.steps[0].uses,
        priority=ExecutionPriority.LOW,
        task_token=mock_task_token))

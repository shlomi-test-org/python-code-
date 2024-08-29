import uuid

import pytest
from jit_utils.event_models import JitEventName
from jit_utils.models.execution_priority import ExecutionPriority
from pydantic import ValidationError

from src.lib.models.execution_models import SilentInvocationRequest


class TestExecutionPriority:
    @pytest.mark.parametrize("jit_event_name, expected_priority", [
        (JitEventName.FullScan, ExecutionPriority.LOW),
        (JitEventName.PullRequestCreated, ExecutionPriority.HIGH),
        (JitEventName.PullRequestUpdated, ExecutionPriority.HIGH),
        (JitEventName.OpenFixPullRequest, ExecutionPriority.HIGH),
        (JitEventName.MergeDefaultBranch, ExecutionPriority.LOW),
        (JitEventName.RegisterScheduledTasks, ExecutionPriority.LOW),
        (JitEventName.UnregisterScheduledTasks, ExecutionPriority.LOW),
        (JitEventName.TriggerScheduledTask, ExecutionPriority.LOW),
        (JitEventName.NonProductionDeployment, ExecutionPriority.LOW),
        (JitEventName.ManualExecution, ExecutionPriority.LOW),
    ])
    def test_from_jit_event_name(self, jit_event_name, expected_priority):
        assert ExecutionPriority.from_jit_event_name(jit_event_name) == expected_priority


def test_silent_invocation_request__valid_control_name_and_job_definition():
    request = SilentInvocationRequest(
        id=str(uuid.uuid4()), tenant_id="tenant1", control_name="prowler", job_definition="prowler-job"
    )
    assert request.control_name == "prowler"
    assert request.job_definition == "prowler-job"


def test_silent_invocation_request__invalid_control_name():
    with pytest.raises(ValidationError):
        SilentInvocationRequest(tenant_id="tenant1", control_name="invalid", job_definition="prowler-job")


def test_silent_invocation_request__control_name_not_in_job_definition():
    with pytest.raises(ValidationError):
        SilentInvocationRequest(tenant_id="tenant1", control_name="prowler", job_definition="invalid-job")

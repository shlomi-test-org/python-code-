import pytest
import responses
from jit_utils.aws_clients.sfn import StepFunctionEvent
from jit_utils.models.execution import ControlType

from src.handlers.enrich import enrich_async
from src.lib.models.trigger import EnrichAsyncResponse
from tests.component.utils.mock_responses import mock_plan_service_api
from tests.component.utils.mocks.mocks import (
    MOCK_JIT_CENTRALIZED_REPO_FILES_METADATA,
    PREPARE_FOR_EXECUTION_PR_CREATED__WITH_DEPENDS_ON,
    PREPARE_FOR_EXECUTION_PR_UPDATED_MULTIPLE_JOBS__WITH_DEPENDS_ON,
    PREPARE_FOR_EXECUTION_RESOURCE_ADDED__WITH_DEPENDS_ON,
)


def execute_enrich_async_on_prepare_for_execution_event(mocker, prepare_for_execution_event):
    mocker.patch("src.lib.clients.plan_service.PlanService.get_centralized_repo_files_metadata",
                 return_value=MOCK_JIT_CENTRALIZED_REPO_FILES_METADATA)
    event = StepFunctionEvent(
        step_input=prepare_for_execution_event,
        state_machine_execution_id="state_machine_execution_id",
    )
    mock_plan_service_api.mock_get_scopes_api("workflow-enrichment-code", "enrich", [])
    return enrich_async(event.dict(), {})


@pytest.mark.parametrize("input_json", [
    PREPARE_FOR_EXECUTION_PR_CREATED__WITH_DEPENDS_ON,
    PREPARE_FOR_EXECUTION_PR_UPDATED_MULTIPLE_JOBS__WITH_DEPENDS_ON,
    PREPARE_FOR_EXECUTION_RESOURCE_ADDED__WITH_DEPENDS_ON,
])
@responses.activate
def test_enrich_async(mocker, input_json, mock_get_configuration_file_for_tenant, mock_get_integration_file_for_tenant):
    enrich_async_response = EnrichAsyncResponse(
        **execute_enrich_async_on_prepare_for_execution_event(mocker, input_json)
    )

    event = enrich_async_response.trigger_enrich_execution
    assert event.workflow_slug == "workflow-enrichment-code"
    assert event.job_name == "enrich"
    assert event.job_runner == "github_actions"
    assert len(event.steps) == 1
    assert event.steps[0].name in [
        "Run code controls execution enrichment for languages and frameworks detection",
        "Run code enrichment",
    ]
    assert event.steps[0].uses == "ghcr.io/jitsecurity-controls/control-enrichment-slim:latest"
    assert event.control_type == ControlType.ENRICHMENT

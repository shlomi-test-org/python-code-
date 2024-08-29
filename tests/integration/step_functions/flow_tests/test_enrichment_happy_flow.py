from typing import List

import pytest
from test_utils.step_functions.localstack import LocalstackStepFunction

from src.lib.models.trigger import PrepareForExecutionEvent, EnrichedData
from tests.component.utils.mocks.mocks import PREPARE_FOR_EXECUTION_PR_UPDATED_MULTIPLE_JOBS__WITH_DEPENDS_ON
from tests.integration.step_functions.flow_tests.common import (
    setup_listener_for_enrichment_execution_event,
    execute_state_machine,
    listen_to_enrichment_execution_event,
    listen_to_the_actual_executions_we_need_to_run,
    assert_state_machine_steps,
    # visualize,
)


@pytest.mark.parametrize("enriched_data, expected_job_names", [
    [{"mime_types": [], "languages": [], "frameworks": [], "package_managers": []}, []],
    [{}, ["static-code-analysis-js", "static-code-analysis-go", "static-code-analysis-python", "docker-scan",
          "software-component-analysis-go", "software-component-analysis", "software-component-analysis-js",
          "iac-misconfig-detection", "secret-detection"]],
    [
        {"mime_types": ["text"], "languages": ["python"], "frameworks": [], "package_managers": []},
        ["static-code-analysis-python", "software-component-analysis", "secret-detection"],
    ],
    [
        {"mime_types": [], "languages": ["javascript"], "frameworks": [], "package_managers": []},
        ["static-code-analysis-js"],
    ],
])
def test_enrichment_happy_flow(enriched_data: EnrichedData, expected_job_names: List[str]):
    local_stack_step_function = LocalstackStepFunction()
    queue, queue_url = setup_listener_for_enrichment_execution_event()
    execution_arn = execute_state_machine(
        local_stack_step_function, PREPARE_FOR_EXECUTION_PR_UPDATED_MULTIPLE_JOBS__WITH_DEPENDS_ON
    )

    """
    should enrich?
    async_enrich
    trigger async enrich
    --- wait for callback with task token ---
    prepare for execution
    trigger executions
    """

    task_token = listen_to_enrichment_execution_event(queue, queue_url)
    local_stack_step_function.send_async_task_result(
        token=task_token,
        is_success=True,
        payload=enriched_data,
    )
    if expected_job_names:
        executions_data = listen_to_the_actual_executions_we_need_to_run(queue, queue_url)
        # Assert execution based on prepare for execution data
        prepare_for_execution = PrepareForExecutionEvent(
            **PREPARE_FOR_EXECUTION_PR_UPDATED_MULTIPLE_JOBS__WITH_DEPENDS_ON
        )
        assert executions_data.tenant_id == prepare_for_execution.jit_event.tenant_id
        assert executions_data.jit_event_name == prepare_for_execution.jit_event.jit_event_name

        job_names = [e.job_name for e in executions_data.executions]
        assert job_names == expected_job_names, f"Expected: {expected_job_names} but got {job_names}"

    history = local_stack_step_function.get_history(execution_arn)
    expected_step_names = ["Prepare Enrich Async", "Trigger Async Enricher", "Prepare For Execution"]
    if expected_job_names:
        expected_step_names.append("Trigger Executions")
    assert_state_machine_steps(history, expected_step_names)

    # visualize(local_stack_step_function, history)

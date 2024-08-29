from test_utils.step_functions.localstack import LocalstackStepFunction

from tests.component.utils.mocks.mocks import PREPARE_FOR_EXECUTION_PR_UPDATED_MULTIPLE_JOBS__WITH_DEPENDS_ON
from tests.integration.step_functions.flow_tests.common import (
    setup_listener_for_enrichment_execution_event,
    execute_state_machine,
    listen_to_enrichment_execution_event,
    assert_state_machine_steps,
    # visualize,
)


def test_enrichment_job_failure__should_not_trigger_executions(
        create_internal_notification_service_queue,
        teardown_internal_notification_service_queue,
):
    local_stack_step_function = LocalstackStepFunction()
    queue, queue_url = setup_listener_for_enrichment_execution_event()
    execution_arn = execute_state_machine(
        local_stack_step_function, PREPARE_FOR_EXECUTION_PR_UPDATED_MULTIPLE_JOBS__WITH_DEPENDS_ON
    )
    task_token = listen_to_enrichment_execution_event(queue, queue_url)
    local_stack_step_function.send_async_task_result(
        token=task_token,
        is_success=False,
        error="Execution failed with status failed",
    )

    history = local_stack_step_function.get_history(execution_arn)
    assert_state_machine_steps(
        history,
        [
            "Prepare Enrich Async",
        ],
        has_execution_succeeded=False,
    )

    # visualize(local_stack_step_function, history)

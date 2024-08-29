from test_utils.step_functions.localstack import LocalstackStepFunction

from tests.component.utils.mocks.mocks import PATH_TO_PREPARE_FOR_EXECUTION_EVENT__WITHOUT_DEPENDS_ON
from tests.integration.step_functions.flow_tests.common import (
    execute_state_machine,
    # visualize,
)


def test_not_enrichment_flow__should_enrich_is_false_no_depends_on():
    local_stack_step_function = LocalstackStepFunction()
    execution_arn = execute_state_machine(
        local_stack_step_function, PATH_TO_PREPARE_FOR_EXECUTION_EVENT__WITHOUT_DEPENDS_ON
    )
    history = local_stack_step_function.get_history(execution_arn)
    steps = [step["stateExitedEventDetails"]["name"] for step in history if step.get("stateExitedEventDetails")]
    expected_steps = [
        'Has Enricher?',
        'Prepare For Execution',
        'Are There Executions To Trigger?',
        'Trigger Executions'
    ]
    assert steps == expected_steps
    # visualize(local_stack_step_function, history)

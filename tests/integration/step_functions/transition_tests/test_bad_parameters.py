import os

from test_utils.step_functions.step_functions_local import StepFunctionLocal

SERVERLESS_YML_FILE_NAME = "serverless.yml"

EXPECTED_RESPONSE = [
    {
        'type': 'ExecutionFailed',
        'id': 3,
        'previousEventId': 2,
        'executionFailedEventDetails': {
            'error': 'States.Runtime',
            'cause': "An error occurred while executing the state 'Has Enricher?' (entered at"
                     " the event id #2). Invalid path '$.should_enrich': The choice state's "
                     "condition path references an invalid value."
        },
        'resource_type': None
    }
]


def test_bad_parameters() -> None:
    step_function = StepFunctionLocal()

    machine_arn = step_function.create_state_machine(
        state_machine_name="EnrichmentProcess",
        state_machine_asl_path=os.path.join(os.getcwd(), "enrichment-process.asl.yaml"),
        sls_yml_path=os.path.join(os.getcwd(), SERVERLESS_YML_FILE_NAME),
    )
    # Without mock test case:
    execution_arn = step_function.start_execution(
        machine_arn,
        mock_test_case="BadParameters",
        payload={},
    )
    history = step_function.get_history(execution_arn)
    redacted_history = step_function.get_redacted_execution(history)
    assert redacted_history == EXPECTED_RESPONSE

    # from test_utils.step_functions.execution_visualizer import ExecutionVisualizer
    # vis = ExecutionVisualizer(redacted_history)
    # vis.visualize()

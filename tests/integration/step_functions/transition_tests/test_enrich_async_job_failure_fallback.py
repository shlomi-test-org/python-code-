import json
import os
from os.path import join, dirname

from test_utils.step_functions.step_functions_local import StepFunctionLocal

SERVERLESS_YML_FILE_NAME = "serverless.yml"


def test_async_job_failure_fallback() -> None:
    step_function = StepFunctionLocal()

    machine_arn = step_function.create_state_machine(
        state_machine_name="EnrichmentProcess",
        state_machine_asl_path=os.path.join(os.getcwd(), "enrichment-process.asl.yaml"),
        sls_yml_path=os.path.join(os.getcwd(), SERVERLESS_YML_FILE_NAME),
    )
    # Without mock test case:
    execution_arn = step_function.start_execution(
        machine_arn,
        mock_test_case="AsyncJobFailureWithFallback",
        payload={"should_enrich": True},
    )
    history = step_function.get_history(execution_arn)

    redacted_history = step_function.get_redacted_execution(history)

    with open(join(dirname(__file__), "output_samples", "test_enrich_async_job_failure_fallback.json")) as f:
        expected = json.load(f)

    assert redacted_history == expected

    # from test_utils.step_functions.execution_visualizer import ExecutionVisualizer
    # vis = ExecutionVisualizer(redacted_history)
    # vis.visualize()

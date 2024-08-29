from typing import Type
from jit_utils.logger.logger import add_label
from jit_utils.models.execution_context import Runner, CI_RUNNERS

from src.lib.cores.execution_runner.ci_execution_runners import get_ci_execution_runner_type
from src.lib.cores.execution_runner.execution_runner import ExecutionRunner
from src.lib.cores.execution_runner.cloud_execution_runners import get_cloud_execution_runner_type
from jit_utils.models.execution import Execution


def get_execution_runner(execution: Execution) -> ExecutionRunner:
    execution_runner_type = map_runner_to_runner_type(execution)
    add_label("runner", execution_runner_type.__name__)
    return execution_runner_type(execution)


def map_runner_to_runner_type(execution: Execution) -> Type[ExecutionRunner]:
    runner_type = execution.context.job.runner.type
    if runner_type in CI_RUNNERS:
        execution_runner_type = get_ci_execution_runner_type(execution)
    elif runner_type == Runner.JIT:
        execution_runner_type = get_cloud_execution_runner_type(execution)
    else:
        raise KeyError(
            f"Runner type: {runner_type} is not a valid runner in the system."
            f"Valid runners: {list(Runner.values())}"
        )
    return execution_runner_type

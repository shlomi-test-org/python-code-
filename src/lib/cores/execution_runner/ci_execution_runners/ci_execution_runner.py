from abc import ABC

from jit_utils.jit_event_names import JitEventName

from src.lib.constants import CI_RUNNER_DISPATCHED_TIMEOUT, CI_RUNNER_EXECUTION_TIMEOUT
from src.lib.cores.execution_runner.execution_runner import ExecutionRunner


class CiExecutionRunner(ExecutionRunner, ABC):
    @property
    def default_dispatched_state_timeout(self) -> int:
        return CI_RUNNER_DISPATCHED_TIMEOUT

    @property
    def default_running_state_timeout(self) -> int:
        if self._execution.jit_event_name in [JitEventName.PullRequestCreated, JitEventName.PullRequestCreated]:
            # PR scans working only on diff + PR experience should be quick -> setting a low running timeout
            return CI_RUNNER_EXECUTION_TIMEOUT
        else:
            # any other type of scan (like full scan) might take longer since it scans the whole asset
            return 2 * CI_RUNNER_EXECUTION_TIMEOUT

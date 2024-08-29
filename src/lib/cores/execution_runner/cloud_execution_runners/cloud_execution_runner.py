from abc import ABC, abstractmethod
from typing import List, Dict, Tuple

from jit_utils.logger import logger
from jit_utils.models.execution import Execution

from src.lib.constants import (
    JIT_BASE_API_URL,
    EXECUTION_ID_ENV_VAR,
    JIT_EVENT_ID_ENV_VAR,
    JIT_RUNNER_EXECUTION_TIMEOUT,
    TENANT_ID_ENV_VAR,
)
from src.lib.constants import JIT_RUNNER_DISPATCHED_TIMEOUT
from src.lib.cores.execution_runner.execution_runner import ExecutionRunner


class CloudExecutionRunner(ExecutionRunner, ABC):
    """
    Protected methods
    """
    @abstractmethod
    def _encrypt_jit_token(self, callback_token: str) -> str:
        raise NotImplementedError

    @classmethod
    def _setup_for_execution(cls, execution: Execution, encrypted_jit_token: str) -> Tuple[Dict[str, str], List[str]]:
        """
        This sets up the needed data for starting the execution.
        1. creates environment to inject to the control
        2. creates command args to run the control
        :param execution: The execution object containing execution details
        :param encrypted_jit_token: The encrypted JIT token
        :return: env and command args to execute the control
        """
        env = {
            TENANT_ID_ENV_VAR: execution.tenant_id,
            JIT_EVENT_ID_ENV_VAR: execution.jit_event_id,
            EXECUTION_ID_ENV_VAR: execution.execution_id,
        }

        command = [
            "--jit-token-encrypted", encrypted_jit_token,
            "--base-url", JIT_BASE_API_URL,
            '--event-id', execution.jit_event_id,
            '--execution-id', execution.execution_id,
        ]

        return env, command

    @property
    def default_dispatched_state_timeout(self) -> int:
        return JIT_RUNNER_DISPATCHED_TIMEOUT

    @property
    def default_running_state_timeout(self) -> int:
        return JIT_RUNNER_EXECUTION_TIMEOUT

    @staticmethod
    def _job_name(execution: Execution, max_length: int) -> str:
        """
        A descriptive name for the job - will be shown in the console
        """

        job_name = f"{execution.control_name.lower().replace(' ', '-')}-{execution.execution_id}"
        if len(job_name) > max_length:
            logger.info(f"{job_name=} is too long, {max_length=}")
            job_name = job_name[(len(job_name) - max_length):].strip("-")
            logger.info(f"{job_name=} after shortening")

        logger.info(f"Calculated {job_name=}")
        return job_name

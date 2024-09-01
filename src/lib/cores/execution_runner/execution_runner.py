import os
from abc import ABC
from abc import abstractmethod
from datetime import datetime
from datetime import timedelta
from functools import cached_property
from typing import List, Optional

from jit_utils.logger import logger
from jit_utils.models.execution import ControlExecutionData
from jit_utils.models.execution import ControlOperationalData
from jit_utils.models.execution import DispatchExecutionEvent
from jit_utils.models.execution import ExecutionStatus
from jit_utils.models.execution_context import Runner
from jit_utils.models.github.github_api_objects import GetVendorExecutionFailureResponse
from jit_utils.models.jit_files.jit_config import ResourceManagement, ResourceManagementRunnerConfigOptions

from src.lib.constants import EXECUTION_LOG_S3_OBJECT_KEY
from src.lib.constants import PULL_REQUESTS_RELATED_JIT_EVENTS
from src.lib.constants import LAUNCH_DARKLY_SDK_KEY
from src.lib.constants import MINUTE_IN_SECONDS
from src.lib.constants import WATCHDOG_GRACE_PERIOD
from src.lib.cores.prepare_data_for_execution_core import get_callback_urls
from src.lib.data.executions_manager import ExecutionsManager
from jit_utils.models.execution import Execution
from src.lib.models.execution_models import ExecutionData
from src.lib.models.execution_models import STATUSES_WITH_TIMEOUT


class ExecutionRunnerDispatchError(Exception):
    def __init__(self, message: str = "An error happened during the dispatch operation"):
        self.message = message
        super().__init__(self.message)


class ExecutionRunner(ABC):
    def __init__(self, execution: Execution):
        self._execution = execution

    @classmethod
    def get_dispatch_execution_event(cls, execution: Execution, callback_token: str) -> DispatchExecutionEvent:
        """
        The dispatch event includes additional data needed for any kind of execution.
        """
        logger.info(f"Building dispatch execution event for execution {execution=}")
        callback_urls = get_callback_urls(execution)

        dispatch_execution_event = DispatchExecutionEvent(
            context=execution.context,
            secrets={},
            execution_data=ControlExecutionData(
                execution_id=execution.execution_id,
            ),
            operational_data=ControlOperationalData(
                callback_urls=callback_urls,
                callback_token=callback_token,
                control_name=execution.context.job.steps[0].name,
                control_image=execution.context.job.steps[0].uses,
                control_timeout_seconds=cls(execution).running_state_timeout,
                feature_flags_api_key=os.getenv(LAUNCH_DARKLY_SDK_KEY),
            ),
        )
        logger.info(f"Dispatching execution: {dispatch_execution_event}")

        return dispatch_execution_event

    @classmethod
    def store_executions_data_in_db(cls, executions: List[Execution], callback_token: str) -> None:
        """
        Store the executions data in the DB
        """
        logger.info(f"Storing execution data for {len(executions)} executions..")
        execution_data_batch = []
        for execution in executions:
            dispatch_event = cls.get_dispatch_execution_event(execution, callback_token)
            execution_data = ExecutionData(
                tenant_id=execution.tenant_id,
                jit_event_id=execution.jit_event_id,
                execution_id=execution.execution_id,
                execution_data_json=dispatch_event.json(),
                created_at=datetime.utcnow().isoformat(),
            )
            execution_data_batch.append(execution_data)

        ExecutionsManager().write_multiple_execution_data(execution_data_batch)
        logger.info(f"Stored execution data for {len(executions)} executions.")

    @classmethod
    @abstractmethod
    def dispatch(cls, executions: List[Execution], callback_token: str) -> Optional[str]:
        raise NotImplementedError

    def can_terminate(self) -> bool:
        has_run_id = self._execution.run_id is not None
        if not has_run_id:
            logger.info(f"Shouldn't terminate - execution_status={self._execution.status} and no run_id")
        return has_run_id

    @abstractmethod
    def terminate(self):
        raise NotImplementedError

    def get_execution_failure_reason(self) -> Optional[GetVendorExecutionFailureResponse]:
        return None

    @property
    def logs_url(self) -> Optional[str]:
        return None

    @property
    def _logs_key(self) -> Optional[str]:
        return EXECUTION_LOG_S3_OBJECT_KEY.format(
            tenant_id=self._execution.tenant_id,
            jit_event_id=self._execution.jit_event_id,
            execution_id=self._execution.execution_id,
        )

    @property
    def runner_type(self) -> Runner:
        return self._execution.context.job.runner.type

    @property
    def running_state_timeout(self) -> int:
        logger.info("Getting running watchdog timeout")

        if self._runner_config:
            logger.info(
                f"Timeout override exists in jit config: {self._runner_config} "
                f"and event is: {self._execution.context.jit_event.jit_event_name}"
            )
            if self._execution.jit_event_name in PULL_REQUESTS_RELATED_JIT_EVENTS:
                if self._runner_config.pr_job_execution_timeout_minutes:
                    return self._runner_config.pr_job_execution_timeout_minutes * MINUTE_IN_SECONDS
            elif self._runner_config.job_execution_timeout_minutes:  # We're not in PR event
                return self._runner_config.job_execution_timeout_minutes * MINUTE_IN_SECONDS

        runner_setup = self._execution.context.job.runner.setup
        if runner_setup and runner_setup.timeout_minutes:
            logger.info(f"Timeout exists in runner setup: {runner_setup.timeout_minutes}")
            return runner_setup.timeout_minutes * MINUTE_IN_SECONDS

        return self.default_running_state_timeout

    @property
    def dispatched_state_timeout(self) -> int:
        logger.info("Getting setup watchdog timeout")
        if self._runner_config:
            logger.info(
                f"Timeout override exists in jit config: {self._runner_config} "
                f"and event is: {self._execution.context.jit_event.jit_event_name}"
            )
            if self._execution.jit_event_name in PULL_REQUESTS_RELATED_JIT_EVENTS:
                if self._runner_config.pr_job_setup_timeout_minutes:
                    return self._runner_config.pr_job_setup_timeout_minutes * MINUTE_IN_SECONDS
            elif self._runner_config.job_setup_timeout_minutes:  # We're not in PR event
                return self._runner_config.job_setup_timeout_minutes * MINUTE_IN_SECONDS
        return self.default_dispatched_state_timeout

    @property
    @abstractmethod
    def default_dispatched_state_timeout(self) -> int:
        """
        The timeout for the system to start running the execution.
        If it takes more than this time, the execution will get timed out.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def default_running_state_timeout(self) -> int:
        """
        The default timeout for the executions running on the runner, in case the `timeout_minutes` was not declared in
        the `runner.setup`.
        If it takes more than this time, the execution will get timed out.
        """
        raise NotImplementedError

    def get_watchdog_timeout(self, status: ExecutionStatus) -> Optional[str]:
        if status not in STATUSES_WITH_TIMEOUT:
            # status should not have a timeout
            return None

        now = datetime.utcnow()
        logger.info(f"Execution status is {status}")
        if status in [ExecutionStatus.DISPATCHING, ExecutionStatus.DISPATCHED]:
            """
            watchdog timeout for execution in dispatch transition, is the pending timeout of the runner - this is the
            time we wait for the execution to be dispatched
            """
            logger.info(f"Setting watchdog timeout of {self.dispatched_state_timeout / MINUTE_IN_SECONDS} minutes")
            execution_timeout = now + timedelta(seconds=self.dispatched_state_timeout)
        else:
            """
            watchdog timeout for execution in running state, is the running timeout of the runner - this is the time we
            wait for execution that started, to get completed + some grace time as we have latency of backend operations
            """
            watchdog_running_state_timeout = self.running_state_timeout + WATCHDOG_GRACE_PERIOD
            logger.info(f"Setting watchdog timeout of {watchdog_running_state_timeout / MINUTE_IN_SECONDS} minutes")
            execution_timeout = now + timedelta(seconds=watchdog_running_state_timeout)

        return execution_timeout.isoformat()

    @cached_property
    def _runner_config(self) -> Optional[ResourceManagementRunnerConfigOptions]:
        """
        Returns the runner config from the jit config file
        """
        resource_management_section = ResourceManagement(
            **(self._execution.context.config.get("resource_management", {}))
        )
        logger.info(f"Runner config section is: {resource_management_section.runner_config}")
        return resource_management_section.runner_config

from typing import List, Optional

from jit_utils.event_models import CodeRelatedJitEvent
from jit_utils.jit_clients.authentication_service.client import AuthenticationService
from jit_utils.jit_clients.github_service.client import GithubService
from jit_utils.jit_clients.github_service.exceptions import GithubServiceApiException
from jit_utils.logger import logger
from jit_utils.models.execution import FetchLogsEvent, Execution
from jit_utils.models.execution import GithubOidcDispatchExecutionEvent
from jit_utils.models.execution_context import RunnerSetup
from jit_utils.models.github.github_api_objects import GetVendorExecutionFailureResponse

from src.lib.clients.eventbridge import EventsClient
from src.lib.clients.github_service import GithubService as OldGithubService
from src.lib.constants import CANCEL_EXECUTION_EVENT_BUS_NAME, JIT_BASE_API_URL
from src.lib.constants import CANCEL_EXECUTION_EVENT_DETAIL_TYPE
from src.lib.constants import CANCEL_EXECUTION_EVENT_SOURCE
from src.lib.constants import EXECUTION_EVENT_BUS_NAME
from src.lib.constants import EXECUTION_EVENT_SOURCE
from src.lib.constants import FETCH_LOGS_EVENT_DETAIL_TYPE
from src.lib.constants import JIT_GITHUB_JOB_LOGS_BUCKET_NAME
from src.lib.constants import S3_OBJECT_FORMAT
from src.lib.cores.execution_runner.ci_execution_runners.ci_execution_runner import CiExecutionRunner
from src.lib.cores.execution_runner.execution_runner import ExecutionRunnerDispatchError
from src.lib.cores.utils.multithreading import execute_function_concurrently_with_args_list
from src.lib.models.github_models import CancelWorkflowRunRequest


class GithubActionExecutionRunner(CiExecutionRunner):
    @classmethod
    def _single_dispatch_execution(cls, execution: Execution) -> None:
        logger.info("Dispatching execution using GithubActionExecutionRunner")
        try:
            context_installation = execution.context.installation
            context_jit_event = execution.context.jit_event
            event = GithubOidcDispatchExecutionEvent(
                tenant_id=execution.tenant_id,
                jit_event_id=execution.jit_event_id,
                execution_id=execution.execution_id,
                jit_base_api=JIT_BASE_API_URL,
                workflow_slug=execution.context.workflow.slug,
                job_name=execution.context.job.job_name,
                centralized_repo=execution.context.centralized,
                installation_id=context_installation.installation_id if context_installation else None,
                asset_name=execution.context.asset.asset_name,
                commits=context_jit_event.commits if isinstance(context_jit_event, CodeRelatedJitEvent) else None,
                runner_setup=execution.context.job.runner.setup or RunnerSetup(checkout=True),
                branch=context_jit_event.branch if isinstance(context_jit_event, CodeRelatedJitEvent) else None,
            )

            OldGithubService().dispatch(tenant_id=execution.tenant_id, event=event)
        except Exception as exc:
            raise ExecutionRunnerDispatchError(message=str(exc))

    @classmethod
    def dispatch(cls, executions: List[Execution], callback_token: str) -> Optional[str]:
        cls.store_executions_data_in_db(executions, callback_token)

        logger.info(f"Starting to dispatch {len(executions)} executions...")
        args_list = [(execution,) for execution in executions]
        execute_function_concurrently_with_args_list(
            function_to_execute=cls._single_dispatch_execution,
            list_of_argument_tuples=args_list,
            max_workers=6
        )
        logger.info(f"Finished dispatching operation for all {len(executions)} executions.")

    def terminate(self) -> None:
        """
        Terminate a workflow run on GitHub
        """
        terminate_request = CancelWorkflowRunRequest(
            app_id=self._execution.context.installation.app_id,
            installation_id=self._execution.context.installation.installation_id,
            owner=self._execution.context.installation.owner,
            run_id=self._execution.run_id,
            vendor=self._execution.vendor,
            repo=self._execution.context.installation.centralized_repo_asset.asset_name,
        )
        event_client = EventsClient()
        event_client.put_event(
            source=CANCEL_EXECUTION_EVENT_SOURCE,
            bus_name=CANCEL_EXECUTION_EVENT_BUS_NAME,
            detail_type=CANCEL_EXECUTION_EVENT_DETAIL_TYPE,
            detail=terminate_request.json(),
        )
        self._send_fetch_logs_request_event()

    def get_execution_failure_reason(self) -> Optional[GetVendorExecutionFailureResponse]:
        try:
            api_token = AuthenticationService().get_api_token(tenant_id=self._execution.tenant_id)
            return GithubService().get_vendor_execution_failure(self._execution.execution_id, api_token)
        except GithubServiceApiException:
            logger.warning("Got error when fetching failure")
            return None

    @property
    def logs_url(self) -> Optional[str]:
        return S3_OBJECT_FORMAT.format(bucket_name=JIT_GITHUB_JOB_LOGS_BUCKET_NAME, object_key=self._logs_key)

    def _send_fetch_logs_request_event(self) -> None:
        """
        This will trigger the github-service to fetch the logs from the github api and store them in S3.
        """
        event_client = EventsClient()
        logger.info("Placing a fetch-logs event to executions bus")

        event_client.put_event(
            source=EXECUTION_EVENT_SOURCE,
            bus_name=EXECUTION_EVENT_BUS_NAME,
            detail_type=FETCH_LOGS_EVENT_DETAIL_TYPE,
            detail=FetchLogsEvent(
                tenant_id=self._execution.tenant_id,
                logs_key=self._logs_key,
                run_id=self._execution.run_id,
                vendor=self._execution.vendor,
            ).json()
        )

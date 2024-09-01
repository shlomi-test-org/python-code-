from typing import List, Optional

from jit_utils.event_models import CodeRelatedJitEvent
from jit_utils.jit_clients.gitlab_service.client import GitlabService
from jit_utils.logger import logger
from jit_utils.models.execution import CiDispatchExecutionEvent, CiJobPayload, Execution
from jit_utils.models.execution_context import RunnerSetup

from src.lib.constants import JIT_BASE_API_URL
from src.lib.cores.execution_runner.ci_execution_runners.ci_execution_runner import CiExecutionRunner
from src.lib.cores.execution_runner.execution_runner import ExecutionRunnerDispatchError


class GitlabExecutionRunner(CiExecutionRunner):

    @classmethod
    def dispatch(cls, executions: List[Execution], callback_token: str) -> Optional[str]:
        cls.store_executions_data_in_db(executions, callback_token)
        logger.info("Dispatching execution using GitlabExecutionRunner")
        try:
            first_execution = executions[0]  # majority of the data is the same for all executions, use the first one
            context_installation = first_execution.context.installation
            context_jit_event = first_execution.context.jit_event
            event = CiDispatchExecutionEvent(
                tenant_id=first_execution.tenant_id,
                installation_id=context_installation.installation_id if context_installation else None,
                jit_event_id=first_execution.jit_event_id,
                jit_base_api=JIT_BASE_API_URL,
                centralized_repo=first_execution.context.centralized,
                asset_name=first_execution.context.asset.asset_name,
                branch=context_jit_event.branch if isinstance(context_jit_event, CodeRelatedJitEvent) else None,
                commits=context_jit_event.commits if isinstance(context_jit_event, CodeRelatedJitEvent) else None,
                runner_setup=first_execution.context.job.runner.setup or RunnerSetup(checkout=True),
                jobs=[
                    CiJobPayload(
                        execution_id=execution.execution_id,
                        workflow_slug=execution.context.workflow.slug,
                        job=execution.context.job,
                    )
                    for execution in executions
                ],
            )

            response = GitlabService().dispatch(dispatch_request=event)
        except Exception as exc:
            raise ExecutionRunnerDispatchError(message=str(exc))

        return response.pipeline_id

    def terminate(self):
        pass

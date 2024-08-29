from typing import Optional, List

from pydantic import ValidationError
from aws_lambda_powertools.utilities.idempotency import IdempotencyConfig
from aws_lambda_powertools.utilities.idempotency import idempotent_function

from jit_utils.event_models.trigger_event import TriggerExecutionEvent
from jit_utils.logger import logger
from jit_utils.models.execution_priority import ExecutionPriority
from jit_utils.utils.aws.idempotency import get_persistence_layer
from jit_utils.models.execution import (
    Execution,
    AssetTypeNotSupportedException,
    ExecutionStatus,
)

from src.lib.constants import EXECUTION_ENRICH_EXECUTION_EVENT_DETAIL_TYPE
from src.lib.cores.execution_events import send_trigger_execution_failed_event
from src.lib.cores.execution_runner import get_execution_runner
from src.lib.cores.execution_runner.ci_execution_runners import VendorTypeNotSupportedException
from src.lib.cores.executions_core import put_dispatch_execution_events
from src.lib.cores.resources_core import should_manage_resource
from src.lib.data.executions_manager import ExecutionsManager


@idempotent_function(
    data_keyword_argument='trigger_event',
    persistence_store=get_persistence_layer(),
    config=IdempotencyConfig(
        event_key_jmespath='[context.jit_event.tenant_id, '
                           'context.jit_event.jit_event_id, '
                           'context.asset.asset_id, '
                           'context.workflow.slug, '
                           'context.job.job_name, '
                           'retry_count]',
        raise_on_no_idempotency_key=True,
    ),
)
def trigger_execution(
        trigger_event: TriggerExecutionEvent,
        executions_manager: ExecutionsManager,
        task_token: Optional[str] = None,
) -> Optional[str]:
    """
    This function will create a new execution from a TriggerExecutionEvent and will initiate its execution process.
    """
    try:
        execution = Execution.from_trigger_execution_event(trigger_event, task_token)
    except (ValidationError, IndexError, AssetTypeNotSupportedException, VendorTypeNotSupportedException):
        logger.exception("Trigger event is corrupted, not triggering the execution")
        # We can't create a new execution from the event, we'll skip it and send a trigger failure event,
        # to be processed by any component involved (ci-service, pipeline-service)
        send_trigger_execution_failed_event(trigger_event)
        return

    if not should_manage_resource(resource_type=execution.resource_type):
        logger.info("This is a high priority execution - should get in the DB as already DISPATCHING")
        execution.status = ExecutionStatus.DISPATCHING
        runner = get_execution_runner(execution)
        execution.execution_timeout = runner.get_watchdog_timeout(ExecutionStatus.DISPATCHING)

    logger.info(f"Creating execution: {execution}")
    executions_manager.create_execution(execution)

    # We need to pass it as dict to the idempotency decorator, so it will be JSON serialized
    return execution.json()


def send_dispatch_high_priority_executions_events(executions: List[Execution]):
    logger.info(f"Sending dispatch events for high priority executions (handling {len(executions)} executions)")

    if not executions:
        logger.info("No executions found, not sending a dispatch event")
        return

    high_priority_executions = [execution for execution in executions if execution.priority ==
                                ExecutionPriority.HIGH]
    logger.info(f"Found {len(high_priority_executions)} high priority executions")
    if not high_priority_executions:
        logger.info("No high priority executions found, not sending a dispatch event")
        return

    put_dispatch_execution_events(
        executions=high_priority_executions,
        detail_type=EXECUTION_ENRICH_EXECUTION_EVENT_DETAIL_TYPE
    )

    logger.info(f"Sent dispatch event for {len(high_priority_executions)} high priority executions")

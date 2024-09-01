from jit_utils.logger import logger
from jit_utils.logger.logger import add_label
from jit_utils.models.execution import ExecutionStatus

from src.lib.constants import ALLOCATE_RUNNER_RESOURCES_RETRY_COUNT
from src.lib.constants import DYNAMODB_INSERT_EVENT_TYPE
from src.lib.constants import DYNAMODB_MODIFY_EVENT_TYPE
from src.lib.constants import EXECUTION_ENRICH_EXECUTION_EVENT_DETAIL_TYPE
from src.lib.cores.execution_events import send_allocation_invoked_metric_event, send_execution_dispatched_metric_event
from src.lib.cores.execution_runner import get_execution_runner
from src.lib.cores.executions_core import put_dispatch_execution_events
from src.lib.cores.resources_core import generate_allocate_resource_queries
from src.lib.data.executions_manager import ExecutionsManager
from jit_utils.models.execution import Execution
from src.lib.models.execution_models import UpdateRequest


def allocate_runner_resources(event_type: str, execution: Execution):
    """
    Allocate runner resources for the execution.
    If the event type is MODIFY, then the lambda have been triggered by freeing a resource, and therefore
    we need to check if there is another execution that is pending to be executed on this runner. If there is,
    then we need to allocate the resources to this execution. Otherwise, we exit.

    If the event type is INSERT, then we know for sure that there is an execution that is pending to be executed.
    In this case, we first check if there is another execution that is pending to be executed on this runner for longer
    period than the one that we have received in the event. If there is, then we execute it. Otherwise, we execute the
    one that we have received in the event.
    """

    # We want to trigger immediately executions with priority HIGH.
    # We must validate that the event type is INSERT!
    add_label("customer_id", execution.tenant_id)
    add_label("old_execution_id", execution.execution_id)
    send_allocation_invoked_metric_event(execution=execution)

    executions_manager = ExecutionsManager()

    for i in range(ALLOCATE_RUNNER_RESOURCES_RETRY_COUNT):
        next_execution_to_execute = executions_manager.get_next_execution_to_run(
            tenant_id=execution.tenant_id,
            runner=execution.job_runner)

        if next_execution_to_execute:
            add_label("next_execution_to_execute", next_execution_to_execute.execution_id)

        logger.info(f"Retrieved Next execution to execute: {next_execution_to_execute}")

        if not next_execution_to_execute and event_type == DYNAMODB_MODIFY_EVENT_TYPE:
            # If we have been triggered by completed operation and there is no other execution to be executed, we exit.
            logger.info(
                f'No more executions to execute for tenant {execution.tenant_id} and runner {execution.job_runner}')
            return

        if not next_execution_to_execute and event_type == DYNAMODB_INSERT_EVENT_TYPE:
            # If there is no other execution to be executed, we execute the one that we have received in the event.
            next_execution_to_execute = execution

        update_execution_status = UpdateRequest(
            tenant_id=next_execution_to_execute.tenant_id,
            execution_id=next_execution_to_execute.execution_id,
            jit_event_id=next_execution_to_execute.jit_event_id,
            status=ExecutionStatus.DISPATCHING.value,
        )

        runner = get_execution_runner(execution)
        update_execution_status.execution_timeout = runner.get_watchdog_timeout(ExecutionStatus.DISPATCHING)

        logger.info(f"Next execution to execute: {next_execution_to_execute}")
        allocate_resources_queries = generate_allocate_resource_queries(execution=next_execution_to_execute)
        update_execution_query = executions_manager.generate_update_execution_query(
            update_request=update_execution_status,
            plan_item_slug=next_execution_to_execute.plan_item_slug,
            resource_type=next_execution_to_execute.resource_type)
        queries_to_execute = [update_execution_query] + allocate_resources_queries
        try:
            logger.info(f"Executing queries: {queries_to_execute}")
            executions_manager.execute_transaction(queries_to_execute)
        except Exception as e:
            logger.info(f"Retry: {i}")
            logger.info(e)
        else:
            put_dispatch_execution_events(
                executions=[next_execution_to_execute],
                detail_type=EXECUTION_ENRICH_EXECUTION_EVENT_DETAIL_TYPE
            )
            send_execution_dispatched_metric_event(execution=next_execution_to_execute)
            break
    else:
        logger.info("Failed to allocate resources")

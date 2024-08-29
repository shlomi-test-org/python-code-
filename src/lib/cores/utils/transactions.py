from jit_utils.logger import logger
from jit_utils.models.execution import Execution

from src.lib.cores.resources_core import generate_free_resource_queries
from src.lib.data.executions_manager import ExecutionsManager
from src.lib.models.execution_models import UpdateRequest, UpdateAttributes


def execute_resource_freeing_transaction(
        execution_to_terminate: Execution,
        update_execution_status: UpdateRequest,
) -> UpdateAttributes:
    """
    Prepares and executes a transaction to free resources and update the execution status.
    Note: Ideally we would want all the queries to be executed in a single transaction, but since we are using

    Args:
        execution_to_terminate (Execution): The execution object to be terminated.
        update_execution_status (UpdateRequest): The update request object with the new execution status.

    Returns:
        UpdateAttributes: The updated execution attributes.
    """
    executions_manager = ExecutionsManager()
    queries_to_execute = generate_free_resource_queries(execution_to_terminate)
    logger.info(f"Executing queries: {queries_to_execute}")
    executions_manager.execute_transaction(queries_to_execute)

    update_execution_query = executions_manager.update_execution(
        update_request=update_execution_status,
        plan_item_slug=execution_to_terminate.plan_item_slug,
        job_runner=execution_to_terminate.job_runner
    )

    return update_execution_query

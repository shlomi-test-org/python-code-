from typing import Dict

from aws_lambda_typing.context import Context
from jit_utils.lambda_decorators import lambda_warmup_handler
from jit_utils.logger import logger
from jit_utils.logger import logger_customer_id

from src.lib.cores.get_execution_data_core import (
    verify_execution_in_dispatching_or_dispatched,
)
from src.lib.data.executions_manager import ExecutionsManager
from src.lib.models.execution_models import ExecutionValidationIdentifies


@lambda_warmup_handler
@logger_customer_id(auto=True)
def handler(event: Dict, context: Context) -> bool:
    logger.info(f"Validating if active execution: {event=}")
    execution_event = ExecutionValidationIdentifies(**event)
    execution_manager = ExecutionsManager()

    # We will allow throwing exceptions (and alerting our slack) if the execution is not in dispatching or dispatched,
    # or any other issue - this is because this situation should not occur, and we would need to check why it happened.
    verify_execution_in_dispatching_or_dispatched(
        execution_manager=execution_manager,
        execution_id=execution_event.execution_id,
        tenant_id=execution_event.tenant_id,
        jit_event_id=execution_event.jit_event_id,
        target_asset_name=execution_event.target_asset_name
    )
    return True

import json

from jit_utils.aws_clients.events import EventBridgeClient
from jit_utils.lambda_decorators import lambda_warmup_handler
from jit_utils.logger import logger, alert, logger_customer_id
from jit_utils.logger.logger import add_label
from jit_utils.models.execution import BaseExecutionIdentifiers, ExecutionStatus
from jit_utils.utils.encoding import MultiTypeJSONEncoder

from src.lib.constants import (
    EXECUTION_NOT_FOUND_ERROR_ALERT,
    EXECUTION_EVENT_SOURCE,
    TRIGGER_EXECUTION_EVENT_BUS_NAME,
    TRIGGER_EXECUTION_DETAIL_TYPE, EXECUTION_RETRY_LIMIT, EXECUTION_MAX_RETRIES_ALERT,
)
from src.lib.cores.executions_core import get_execution_by_id, update_execution
from src.lib.models.execution_models import UpdateRequest


@lambda_warmup_handler
@logger_customer_id(auto=True)
def handler(event, __):
    """
    Changes the execution status to retry and sends a trigger execution event to the bus
    """
    logger.info(f"Event started: {event=}")
    # convert the event to a basic execution identifiers
    basic_execution_identifiers = BaseExecutionIdentifiers(**event)
    add_label('execution_id', basic_execution_identifiers.execution_id)
    add_label('jit_event_id', basic_execution_identifiers.jit_event_id)
    add_label('tenant_id', basic_execution_identifiers.tenant_id)
    execution = get_execution_by_id(
        tenant_id=basic_execution_identifiers.tenant_id,
        jit_event_id=basic_execution_identifiers.jit_event_id,
        execution_id=basic_execution_identifiers.execution_id,
    )

    if execution is None:
        alert(
            f'Invoked retry for non existing execution {basic_execution_identifiers=}',
            alert_type=EXECUTION_NOT_FOUND_ERROR_ALERT
        )
        return

    add_label('jit_event_name', execution.jit_event_name)
    add_label('control_name', execution.control_name)

    # update the execution in DB to retry status
    if execution.retry_count == EXECUTION_RETRY_LIMIT:
        alert(
            f'Execution reached max retries {basic_execution_identifiers=}',
            alert_type=EXECUTION_MAX_RETRIES_ALERT
        )
        return

    update_request = UpdateRequest(
        tenant_id=execution.tenant_id,
        jit_event_id=execution.jit_event_id,
        execution_id=execution.execution_id,
        status=ExecutionStatus.RETRY,
        retry_count=execution.retry_count + 1,
    )
    execution = update_execution(execution, update_request)
    trigger_execution_event = execution.to_trigger_execution_event()
    task_token = execution.task_token
    logger.info(f"Updated the execution to retry status, sending event to BUS {event=}")
    EventBridgeClient().put_event(
        source=EXECUTION_EVENT_SOURCE,
        bus_name=TRIGGER_EXECUTION_EVENT_BUS_NAME,
        detail_type=TRIGGER_EXECUTION_DETAIL_TYPE,
        detail=json.dumps(dict(Message=trigger_execution_event.dict(), TaskToken=task_token), cls=MultiTypeJSONEncoder),
    )
    logger.info(f"Published the retry event to event bridge {event=}")

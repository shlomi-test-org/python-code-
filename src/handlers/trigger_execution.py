import json
from typing import Union

from jit_utils.event_models.trigger_event import BulkTriggerExecutionEvent
from jit_utils.event_models.trigger_event import TriggerExecutionEvent
from jit_utils.lambda_decorators import feature_flags_init_client
from jit_utils.lambda_decorators import lambda_warmup_handler
from jit_utils.logger import logger
from jit_utils.logger import logger_customer_id
from jit_utils.models.execution import Execution
from pydantic.tools import parse_obj_as

from src.lib.cores.create_execution import trigger_execution, send_dispatch_high_priority_executions_events
from src.lib.data.executions_manager import ExecutionsManager
from src.lib.exceptions import FailedTriggersExceptions


@logger_customer_id(auto=True)
@lambda_warmup_handler
@feature_flags_init_client()
def handler(event, __):
    """
    Receives the event from the trigger service and create execution entity in the DB.
    """
    logger.info(f"Starting job runner lambda with {event=}")

    if "Message" in event["detail"]:
        body = event["detail"]["Message"]
    else:
        body = event["detail"]

    request = parse_obj_as(Union[BulkTriggerExecutionEvent, TriggerExecutionEvent], body)
    if isinstance(request, TriggerExecutionEvent):
        events = [request]
    else:
        events = request.executions

    logger.info(f"Received {len(events)} trigger execution events, {events=}")

    # Validate that all events have the same tenant_id
    tenant_id = events[0].jit_event.tenant_id
    if not all(trigger_event.jit_event.tenant_id == tenant_id for trigger_event in events[1:]):
        raise ValueError('All trigger execution events must have the same tenant_id')

    executions_manager = ExecutionsManager()

    failed_triggers = []
    created_executions = []
    for trigger_execution_event in events:
        try:
            created_execution_dict = trigger_execution(
                trigger_event=trigger_execution_event,
                executions_manager=executions_manager,
                task_token=event["detail"].get('TaskToken')
            )
            if created_execution_dict:
                created_executions.append(Execution(**json.loads(created_execution_dict)))
        except Exception:  # noqa
            logger.exception("Got an unexpected exception, the trigger event would be retried")
            failed_triggers.append(trigger_execution_event)

    # High priority execution will be triggered immediately. others will be managed by the resource management (Streams)
    send_dispatch_high_priority_executions_events(executions=created_executions)

    if failed_triggers:
        raise FailedTriggersExceptions(failed_triggers)

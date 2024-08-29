import json
from typing import Dict, List, Union

from aws_lambda_typing.context import Context
from jit_utils.aws_clients.decorators import step_functions_deferred_message_handler
from jit_utils.aws_clients.events import EventBridgeClient
from jit_utils.aws_clients.sfn import StepFunctionEvent
from jit_utils.event_models.trigger_event import TriggerExecutionEvent, BulkTriggerExecutionEvent
from jit_utils.lambda_decorators import lambda_warmup_handler, feature_flags_init_client
from jit_utils.logger import logger, logger_customer_id
from jit_utils.logger.logger import add_label
from jit_utils.models.trigger.jit_event_life_cycle import JitEventStatus

from src.lib.constants import (
    TRIGGER_EVENT_SOURCE,
    TRIGGER_EXECUTION_BUS_NAME,
    TRIGGER_EXECUTION_DETAIL_TYPE_PUBLISHED_PREPARE_FOR_EXECUTION,
)
from src.lib.cores.jit_event_life_cycle.jit_event_life_cycle_handler import JitEventLifeCycleHandler
from src.lib.cores.prepare_for_execution_core import prepare_for_execution_core
from src.lib.models.trigger import PrepareForExecutionEventWithEnrichedData, PrepareForExecutionEvent


@logger_customer_id(auto=True)
@lambda_warmup_handler
@feature_flags_init_client()
@step_functions_deferred_message_handler(custom_input_key_s3="prepare_for_execution_event")
def handler(event: Dict, _: Context) -> Dict:
    """
    Get trigger event with enriched data and filters out the relevant jobs for the execution based on enrichment
    """
    logger.info(f'event: {event}')
    step_function_event = StepFunctionEvent[
        Union[PrepareForExecutionEventWithEnrichedData, PrepareForExecutionEvent]](**event)
    if isinstance(step_function_event.step_input, PrepareForExecutionEventWithEnrichedData):
        prepare_for_execution = step_function_event.step_input.prepare_for_execution_event
        prepare_for_execution.enriched_data = step_function_event.step_input.enriched_data
    else:
        prepare_for_execution = step_function_event.step_input

    # Send the prepare_for_execution event to event bus, one of the consumers is metrics (mixpanel)
    event_bridge_client = EventBridgeClient()
    event_bridge_client.put_event(
        source=TRIGGER_EVENT_SOURCE,
        bus_name=TRIGGER_EXECUTION_BUS_NAME,
        detail_type=TRIGGER_EXECUTION_DETAIL_TYPE_PUBLISHED_PREPARE_FOR_EXECUTION,
        detail=json.dumps({
            "should_enrich": prepare_for_execution.should_enrich,
            "enriched_data": prepare_for_execution.enriched_data,
            "jit_event_name": prepare_for_execution.jit_event.jit_event_name,
            "tenant_id": prepare_for_execution.jit_event.tenant_id,
        }),
    )

    tenant_id = prepare_for_execution.jit_event.tenant_id
    jit_event_id = prepare_for_execution.jit_event.jit_event_id
    add_label("step_function_id", step_function_event.get_state_machine_execution_id())
    add_label("customer_id", tenant_id)
    add_label("jit_event_id", jit_event_id)
    try:
        trigger_exec_events: List[TriggerExecutionEvent] = prepare_for_execution_core(prepare_for_execution)

        bulk_events: BulkTriggerExecutionEvent = BulkTriggerExecutionEvent(
            executions=trigger_exec_events,
            tenant_id=prepare_for_execution.jit_event.tenant_id,
            jit_event_name=prepare_for_execution.jit_event.jit_event_name,
        )
    except Exception:
        logger.exception(f"Completing {jit_event_id=} with status: {JitEventStatus.FAILED},"
                         f" due to exception in prepare for execution")
        JitEventLifeCycleHandler().jit_event_completed(
            tenant_id=tenant_id,
            jit_event_id=jit_event_id,
            status=JitEventStatus.FAILED,
        )
        raise

    logger.info(f"Sending bulk trigger exec event: {bulk_events}")
    return json.loads(bulk_events.json())

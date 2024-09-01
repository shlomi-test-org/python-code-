import json
from typing import Dict

from aws_lambda_typing.context import Context
from jit_utils.aws_clients.sfn import StepFunctionEvent
from jit_utils.lambda_decorators import lambda_warmup_handler
from jit_utils.logger import logger, logger_customer_id
from jit_utils.logger.logger import add_label

from src.lib.cores.enrich_core import generate_trigger_execution_events
from src.lib.models.trigger import PrepareForExecutionEvent, EnrichAsyncResponse


@lambda_warmup_handler
@logger_customer_id(auto=True)
def enrich_async(event: Dict, _: Context) -> Dict:
    """
    This function is triggered for the step `Prepare Enrich Async` in the enrichment process state machine.
    Should create an event that triggers executions for the enrichment control.

    :param event: PrepareForExecutionEvent event that includes the contenders jobs to run on a single asset

    :return: TriggerExecutionEvent that the state machine is passing to the next step as a raw dictionary
    """
    logger.info(f'Handling enrich async event: {event}')

    step_function_event = StepFunctionEvent[PrepareForExecutionEvent](**event)
    prepare_for_execution = step_function_event.step_input
    add_label('step_function_id', step_function_event.get_state_machine_execution_id())
    add_label('customer_id', prepare_for_execution.jit_event.tenant_id)

    trigger_execution_events = generate_trigger_execution_events(prepare_for_execution)

    return json.loads(EnrichAsyncResponse(
        prepare_for_execution_event=prepare_for_execution,
        trigger_enrich_execution=trigger_execution_events[0],
    ).json())  # doing `json.loads(*.json())` instead of `*.dict()` since `dict()` not handling `set` in serialization

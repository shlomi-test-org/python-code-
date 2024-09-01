from typing import Union

from aws_lambda_powertools.utilities.idempotency import idempotent, IdempotencyConfig
from aws_lambda_typing.context import Context
from aws_lambda_typing.events import EventBridgeEvent
from jit_utils.logger import logger_customer_id, logger
from jit_utils.logger.customer_id_finders import tenant_id_from_eventbridge_message
from jit_utils.logger.logger import add_label
from jit_utils.models.execution import Execution, TriggerExecutionFailedUpdateEvent
from jit_utils.utils.aws.idempotency import get_persistence_layer
from pydantic import parse_obj_as

from src.lib.cores.jit_event_life_cycle.jit_event_life_cycle_handler import JitEventLifeCycleHandler


@logger_customer_id(customer_id_finder=tenant_id_from_eventbridge_message)
@idempotent(
    persistence_store=get_persistence_layer(),
    config=IdempotencyConfig(
        event_key_jmespath='id',
        raise_on_no_idempotency_key=True,
    ),
)
def handler(event: EventBridgeEvent, _: Context) -> None:
    """
    Invoked when an execution is completed
    Enrichment execution triggers this lambda only if it failed to finish asset run since no job will run
    """
    logger.info(f"Handling execution completed {event=}")

    event_model = parse_obj_as(Union[Execution, TriggerExecutionFailedUpdateEvent], event['detail'])  # type: ignore

    tenant_id = event_model.tenant_id
    jit_event_id = event_model.jit_event_id
    asset_id = event_model.asset_id

    add_label("jit_event_id", jit_event_id)
    add_label("asset_id", asset_id)
    if isinstance(event_model, Execution):
        add_label("execution_id", event_model.execution_id)

    JitEventLifeCycleHandler().job_completed(
        tenant_id=tenant_id,
        jit_event_id=jit_event_id,
        asset_id=asset_id,
    )

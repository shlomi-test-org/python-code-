from jit_utils.logger import logger
from jit_utils.aws_clients.events import EventBridgeClient

from src.lib.constants import TRIGGER_EVENT_SOURCE, JIT_EVENT_LIFE_CYCLE_EVENT_BUS_NAME, TRIGGER_EXECUTION_BUS_NAME


def send_jit_event_life_cycle_event(detail_type: str, jit_event_life_cycle_event: str) -> None:
    logger.info(f"Sending Jit event life cycle event bridge: {detail_type=} {jit_event_life_cycle_event=}")
    event_bridge_client = EventBridgeClient()
    event_bridge_client.put_event(
        source=TRIGGER_EVENT_SOURCE,
        bus_name=JIT_EVENT_LIFE_CYCLE_EVENT_BUS_NAME,
        detail_type=detail_type,
        detail=jit_event_life_cycle_event,
    )


def send_jit_event_processing_event(detail_type: str, jit_event_resources_fetched_event: str) -> None:
    logger.info(f"Sending Jit event processing event bridge: {detail_type=} {jit_event_resources_fetched_event=}")
    event_bridge_client = EventBridgeClient()
    event_bridge_client.put_event(
        source=TRIGGER_EVENT_SOURCE,
        bus_name=TRIGGER_EXECUTION_BUS_NAME,
        detail_type=detail_type,
        detail=jit_event_resources_fetched_event,
    )

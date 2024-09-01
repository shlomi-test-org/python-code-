import datetime

import boto3
from jit_utils.aws_clients.config.aws_config import get_aws_config
from jit_utils.logger import logger

EVENTS_CLIENT = None


class EventsClient:
    """
    A client for connecting to AWS EventBridge
    """

    def __init__(self):
        params = get_aws_config()
        self.client = boto3.client('events', **params)

    def put_event(self, source: str, bus_name: str, detail_type: str, detail: str):
        entry = {
            'Time': datetime.datetime.utcnow(),
            'Source': source,
            'Resources': [],
            'DetailType': detail_type,
            'Detail': detail,
            'EventBusName': bus_name,
        }

        logger.info(f'EventBridge entry: {entry}')

        response = self.client.put_events(Entries=[entry])

        logger.info(f'EventBridge response: {response}')

        if response.get("FailedEntryCount"):
            raise Exception(f"FailedEntryCount: {response}")


def get_events_client() -> EventsClient:
    global EVENTS_CLIENT
    if EVENTS_CLIENT is None:
        EVENTS_CLIENT = EventsClient()
    return EVENTS_CLIENT

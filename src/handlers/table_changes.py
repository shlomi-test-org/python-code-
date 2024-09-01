import json
import os
from typing import Union

from aws_lambda_typing.context import Context
from aws_lambda_typing.events import DynamoDBStreamEvent
from aws_lambda_typing.events import EventBridgeEvent
from jit_utils.lambda_decorators import exception_handler
from jit_utils.logger import logger
from jit_utils.logger import logger_customer_id

from src.lib.clients.eventbridge import get_events_client
from src.lib.constants import EXECUTION_EVENT_SOURCE
from src.lib.constants import EXECUTION_UPDATES_BUS_NAME
from src.lib.constants import EXECUTION_UPDATES_DETAIL_TYPE
from src.lib.constants import RESOURCE_COUNTER_DETAIL_TYPE
from src.lib.constants import RESOURCE_IN_USE_DETAIL_TYPE
from src.lib.constants import RESOURCE_UPDATES_BUS_NAME
from src.lib.data.executions_manager import ExecutionsManager
from src.lib.data.resources_manager import ResourcesManager
from jit_utils.models.execution import Execution
from src.lib.models.metric_models import ExecutionUpdateMetric
from src.lib.models.resource_models import Resource
from src.lib.models.resource_models import ResourceInUse


@exception_handler()
@logger_customer_id(auto=True)
def execution_record_changed(event: Union[EventBridgeEvent, DynamoDBStreamEvent], context: Context):
    """
    This function is used to get all changes from the resource table and send them to an eventbus for everything that
    might be interested in data changes.
    """
    logger.info(f"Execution table change: {event=}")
    event: DynamoDBStreamEvent = event
    for record in event['Records']:
        new_image = record['dynamodb']['NewImage']
        execution_manager = ExecutionsManager()
        data = execution_manager.parse_dynamodb_item_to_python_dict(new_image)
        execution = Execution(**data)
        logger.info(f'{execution=}')
        metric = ExecutionUpdateMetric(metadata=ExecutionUpdateMetric.ExecutionUpdateMetadata(**{
            **execution.dict(),
            "event_id": execution.jit_event_id,
            "event_name": execution.jit_event_name,
            "env_name": os.getenv("ENV_NAME")
        }), data=ExecutionUpdateMetric.ExecutionUpdateData(**execution.dict()))
        logger.info(f'{metric=}')

        events_client = get_events_client()
        params = {
            'source': EXECUTION_EVENT_SOURCE,
            'bus_name': EXECUTION_UPDATES_BUS_NAME,
            'detail_type': EXECUTION_UPDATES_DETAIL_TYPE,
            'detail': json.dumps(metric.dict())
        }
        events_client.put_event(**params)


@exception_handler()
@logger_customer_id(auto=True)
def resource_changed(event: Union[EventBridgeEvent, DynamoDBStreamEvent], context: Context):
    """
    This function is used to get all changes from the resource table and send them to an event bus for everything that
    might be interested in data changes.
    """
    logger.info(f"Resource table change: {event=}")
    event: DynamoDBStreamEvent = event
    for record in event['Records']:
        new_image = record['dynamodb']['NewImage']
        resource_manager = ResourcesManager()
        data = resource_manager.parse_dynamodb_item_to_python_dict(new_image)
        if "resource_type" in data and "jit_event_id" in data:
            resource_in_use = ResourceInUse(**data)
            logger.info(f'{resource_in_use=}')
            metric = {
                "metadata": {
                    "env_name": os.getenv("ENV_NAME"),
                    "event_id": resource_in_use.jit_event_id,
                    "tenant_id": resource_in_use.tenant_id,
                    "resource_type": resource_in_use.resource_type},
                "data": {
                    "execution_id": resource_in_use.execution_id,
                    "created_at": resource_in_use.created_at,
                    "created_at_ts": resource_in_use.created_at_ts,
                }
            }

            events_client = get_events_client()
            params = {
                'source': EXECUTION_EVENT_SOURCE,
                'bus_name': RESOURCE_UPDATES_BUS_NAME,
                'detail_type': RESOURCE_IN_USE_DETAIL_TYPE,
                'detail': json.dumps(metric)
            }
            events_client.put_event(**params)

        if "resources_in_use" in data:
            resource = Resource(**data)
            logger.info(f'{resource=}')
            metric = {
                "metadata": {
                    "env_name": os.getenv("ENV_NAME"),
                    "tenant_id": resource.tenant_id,
                    "resource_type": resource.resource_type,
                },
                "data": {
                    "resources_in_use": resource.resources_in_use,
                    "max_resources_in_use": resource.max_resources_in_use,
                }
            }
            events_client = get_events_client()
            params = {
                'source': EXECUTION_EVENT_SOURCE,
                'bus_name': RESOURCE_UPDATES_BUS_NAME,
                'detail_type': RESOURCE_COUNTER_DETAIL_TYPE,
                'detail': json.dumps(metric)
            }
            events_client.put_event(**params)

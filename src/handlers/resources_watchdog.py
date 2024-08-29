import json
from collections import defaultdict
from typing import List

from aws_lambda_typing.events import SQSEvent
from jit_utils.lambda_decorators import exception_handler
from jit_utils.lambda_decorators import request_headers_keys
from jit_utils.lambda_decorators import response_wrapper
from jit_utils.logger import logger
from jit_utils.logger import logger_customer_id
from pydantic import parse_obj_as

from src.lib.constants import BATCH_ITEMS_FAILURE
from src.lib.constants import ITEM_IDENTIFIER
from src.lib.constants import MESSAGE_ID
from src.lib.cores.resources_watchdog_core import find_executions_to_terminate_and_push_to_queue
from src.lib.cores.resources_watchdog_core import forward_free_resource_failed_msg_to_notification_service
from src.lib.cores.resources_watchdog_core import terminate_execution_and_free_resources_core
from jit_utils.models.execution import Execution


@exception_handler()
@request_headers_keys
@response_wrapper
@logger_customer_id(auto=True)
def watchdog(event, __):
    """
    This lambda responsible to find executions that haven't been cleaned up, push them to a queue
    & push send them to notification service.
    """
    logger.info(f"event: {event}")
    find_executions_to_terminate_and_push_to_queue()


@exception_handler()
@request_headers_keys
@logger_customer_id(auto=True)
def free_resources_handler(event, __):
    """
    This lambda responsible to find executions that haven't been cleaned up, and terminate them.
    """
    logger.info(f"event: {event}")

    execution_id_to_message_id = defaultdict()
    to_terminate = []
    for record in event['Records']:
        payload = json.loads(record['body'])
        execution: Execution = parse_obj_as(Execution, payload)
        to_terminate.append(execution)
        execution_id_to_message_id[execution.execution_id] = record[MESSAGE_ID]

    failed_executions: List[Execution] = terminate_execution_and_free_resources_core(to_terminate)
    logger.info(f"Finished freeing resources with {failed_executions=}")

    response = {
        BATCH_ITEMS_FAILURE: [
            {ITEM_IDENTIFIER: execution_id_to_message_id[resource.execution_id]}
            for resource
            in failed_executions
        ],
    }
    logger.info(f"{response}")
    return response


@exception_handler()
@request_headers_keys
@response_wrapper
@logger_customer_id(auto=True)
def notify_free_resource_failed(event: SQSEvent, __) -> None:
    """
    Responsible to forward dead letter queue messages to the notification service for internal handling
    """
    logger.info(f"event: {event}")
    forward_free_resource_failed_msg_to_notification_service(event["Records"])

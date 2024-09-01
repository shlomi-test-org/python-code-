from typing import Any

from aws_lambda_typing.events import APIGatewayProxyEventV1
from jit_utils.lambda_decorators import exception_handler
from jit_utils.logger import logger
from jit_utils.logger import logger_customer_id


@exception_handler()
@logger_customer_id(auto=True)
def handler(event: APIGatewayProxyEventV1, __: Any):
    logger.info(f"Event: {event}")

    body = event.get("body")
    if body:
        logger.info(f"Body: {body}")
    else:
        logger.info("No body in event payload")

    return {
        "statusCode": 200,
        "body": "OK"
    }

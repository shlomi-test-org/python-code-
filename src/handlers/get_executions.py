import base64
import json
from http import HTTPStatus
from typing import cast

from aws_lambda_typing.context import Context
from aws_lambda_typing.events import APIGatewayProxyEventV2 as APIEvent
from jit_utils.lambda_decorators import dynamodb_tenant_isolation
from jit_utils.lambda_decorators import DynamodbIsolationRule
from jit_utils.lambda_decorators import exception_handler
from jit_utils.lambda_decorators import lambda_warmup_handler
from jit_utils.lambda_decorators import request_headers_keys
from jit_utils.lambda_decorators import response_wrapper
from jit_utils.logger import logger
from jit_utils.logger import logger_customer_id
from py_api import api_documentation
from py_api import Method
from py_api import Parameter
from py_api import Response

from src.lib.constants import EXECUTION_TABLE_NAME
from src.lib.constants import START_KEY
from src.lib.cores.executions_core import get_executions_by_filter
from src.lib.models.execution_models import GetExecutionsFilters
from src.lib.models.execution_models import GetExecutionsResponse


@exception_handler()
@lambda_warmup_handler
@request_headers_keys
@response_wrapper
@dynamodb_tenant_isolation(
    rules=[
        DynamodbIsolationRule(
            table_name=EXECUTION_TABLE_NAME,
            actions=["dynamodb:Query", "dynamodb:GetItem"]
        ),
    ]
)
@logger_customer_id(auto=True)
@api_documentation(
    get=Method(
        description='Get paginated executions',
        query_parameters=[Parameter(name="start_key", schema=str, description="Start key for pagination"), ],
        method_responses={
            HTTPStatus.OK: Response(
                schema=GetExecutionsResponse,
                description='Execution',
            ),
        },
    )
)
def handler(event: APIEvent, context: Context):
    """
    Get executions by filter
    """
    logger.info(f"Get executions by filter {event=}")
    tenant_id = cast(str, event['requestContext']['authorizer']['tenant_id'])
    query_parameters = event.get("queryStringParameters", {}) or {}

    start_key = query_parameters.get(START_KEY)
    if start_key:
        query_parameters[START_KEY] = json.loads(base64.b64decode(start_key).decode())

    filters = GetExecutionsFilters(**query_parameters)
    logger.info(f"Getting executions for tenant {tenant_id} with filters {filters}")

    executions, last_key = get_executions_by_filter(tenant_id, filters)
    last_key_encoded = base64.b64encode(json.dumps(last_key).encode()).decode() if last_key else None
    return HTTPStatus.OK, {"data": [json.loads(execution.json()) for execution in executions],
                           "metadata": {"count": len(executions),
                                        "last_key": last_key_encoded}}

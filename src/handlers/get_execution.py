from typing import cast
from http import HTTPStatus

from aws_lambda_typing.context import Context
from aws_lambda_typing.events import APIGatewayProxyEventV2 as APIEvent
from py_api import api_documentation, Method, Parameter, Response

from jit_utils.models.execution import Execution
from jit_utils.logger import logger, logger_customer_id
from jit_utils.lambda_decorators import (dynamodb_tenant_isolation, DynamodbIsolationRule, exception_handler,
                                         lambda_warmup_handler, request_headers_keys, response_wrapper)

from src.lib.models.api_models import NotFoundResponse
from src.lib.cores.executions_core import get_execution_by_id
from src.lib.models.execution_models import GetExecutionByIdFilters


@exception_handler()
@lambda_warmup_handler
@request_headers_keys
@response_wrapper
@dynamodb_tenant_isolation(
    rules=[
        DynamodbIsolationRule(
            table_name="Executions",
            actions=['dynamodb:GetItem']
        )
    ]
)
@logger_customer_id(auto=True)
@api_documentation(
    get=Method(
        description='Get execution by any filter (jit_event_id and execution_id or other filters)',
        query_parameters=[Parameter(name="Filters", schema=GetExecutionByIdFilters, description="Execution filters")],
        method_responses={
            HTTPStatus.OK: Response(
                schema=Execution,
                description='Execution',
            ),
            HTTPStatus.NOT_FOUND: Response(
                title="NOT_FOUND",
                schema=NotFoundResponse,
                description='Execution not found',
            ),
        },
    )
)
def handler(event: APIEvent, context: Context):
    """
    Get execution by jit_event_id and execution_id
    """
    logger.info(f'Getting execution by jit_event_id and execution_id: {event=}')
    tenant_id = cast(str, event['requestContext']['authorizer']['tenant_id'])
    query_parameters = event.get('queryStringParameters', {}) or {}

    filters = GetExecutionByIdFilters(**query_parameters)
    logger.info(f'Getting execution for {tenant_id=} with {filters=}')

    execution = get_execution_by_id(tenant_id, filters.jit_event_id, filters.execution_id)
    return (
        (HTTPStatus.OK, execution)
        if execution
        else (HTTPStatus.NOT_FOUND, NotFoundResponse(message='Execution not found').dict())
    )

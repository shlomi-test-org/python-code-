import os
from http import HTTPStatus
from typing import cast

from aws_lambda_typing.context import Context
from aws_lambda_typing.events import APIGatewayProxyEventV2 as APIEvent
from jit_utils.lambda_decorators import exception_handler
from jit_utils.lambda_decorators import lambda_warmup_handler
from jit_utils.lambda_decorators import response_wrapper
from jit_utils.lambda_decorators import s3_tenant_isolation
from jit_utils.lambda_decorators import S3IsolationRule
from jit_utils.logger import logger
from jit_utils.logger import logger_customer_id
from py_api import api_documentation
from py_api import Method
from py_api import PathParameter
from py_api import Response

from src.lib.clients.execution_log import ExecutionLogNotFoundException
from src.lib.constants import EXECUTION_LOG_GET_SIZE_LIMIT
from src.lib.cores.execution_log import get_execution_log_truncated_with_presigned_url_read
from src.lib.cores.execution_log import GetTruncatedLogWithPresignedResult
from src.lib.models.api_models import NotFoundResponse
from src.lib.models.log_models import GetLogRequest


@exception_handler()
@lambda_warmup_handler
@response_wrapper
@logger_customer_id(auto=True)
@s3_tenant_isolation(rules=[S3IsolationRule(os.environ["S3_EXECUTION_LOGS_BUCKET_NAME"], ["s3:GetObject"])])
@api_documentation(
    get=Method(
        description="When a job is created, this function is called to register the job",
        path_parameters=[
            PathParameter(
                name='jit_event_id',
                schema=str,
                description='jit event id',
            ),
            PathParameter(
                name='execution_id',
                schema=str,
                description='execution id',
            )
        ],
        method_responses={
            HTTPStatus.OK: Response(
                schema=GetTruncatedLogWithPresignedResult,
                description="Got logs successfully",
            ),
            HTTPStatus.BAD_REQUEST: Response(
                title='NotFound',
                schema=NotFoundResponse,
                description="Invalid parameters passed",
            )
        },
    )
)
def handler(event: APIEvent, context: Context):
    logger.info(f"Received event: {event}")
    request = GetLogRequest(**event["pathParameters"])
    logger.info(f"Request: {request}")
    try:
        result: GetTruncatedLogWithPresignedResult = get_execution_log_truncated_with_presigned_url_read(
            tenant_id=cast(str, event["requestContext"]["authorizer"]["tenant_id"]),
            jit_event_id=request.jit_event_id,
            execution_id=request.execution_id,
            max_bytes=EXECUTION_LOG_GET_SIZE_LIMIT,
        )
    except ExecutionLogNotFoundException as e:
        logger.info(f"Execution log not found: {e}")
        return HTTPStatus.NOT_FOUND, NotFoundResponse(message="Execution log not found").dict()

    return HTTPStatus.OK, result

from http import HTTPStatus
from typing import Tuple

from aws_lambda_powertools.utilities.data_classes import event_source, APIGatewayProxyEvent
from aws_lambda_typing.context import Context
from jit_utils.documentation.py_api import api_documentation, Method, Response, Request
from jit_utils.lambda_decorators import (
    response_wrapper,
    lambda_warmup_handler,
    status_code_wrapper,
    feature_flags_init_client,
)
from jit_utils.lambda_decorators.rate_limiter import rate_limiter_decorator, RateLimiterConfig
from jit_utils.lambda_decorators.status_code_wrapper import load_json_with_validation
from jit_utils.logger import logger, logger_customer_id
from jit_utils.logger.logger import add_label
from jit_utils.models.common.documentation import RES_BAD_REQUEST
from jit_utils.models.common.responses import ErrorResponse
from jit_utils.models.trigger.requests import ManualExecutionRequest
from jit_utils.models.trigger.responses import ManualExecutionResponse

from src.lib.cores.manual_execution.exceptions import (
    EmptyPlanItemSlug,
    NoAssetsException,
    AssetNotExistsException,
    InactivePlanItemException,
    NoManualWorkflowsForPlanItemException,
    AssetWithNoWorkflowException,
    AssetConflictException,
)
from src.lib.cores.manual_execution.manual_execution_handler import ManualExecutionHandler
from src.lib.utils import get_tenant_id_from_api_gw_request


@lambda_warmup_handler  # type: ignore
@response_wrapper
@status_code_wrapper()
@feature_flags_init_client()
@logger_customer_id(auto=True)
@rate_limiter_decorator(RateLimiterConfig())
@api_documentation(
    post=Method(
        is_public=True,
        tags=["Executions"],
        description="Trigger executions for plan-item and assets to run against"
                    "\n\n"
                    "**NOTE** This endpoint only support triggering executions for plan-items.",
        summary="Trigger plan-item execution",
        request_body=Request(
            description="The fields describing the execution request.",
            required=True,
            schema=ManualExecutionRequest,
        ),
        method_responses={
            HTTPStatus.ACCEPTED: Response(
                schema=ManualExecutionResponse,
                description="Trigger execution response",
            ),
            HTTPStatus.BAD_REQUEST: RES_BAD_REQUEST,
        },
    )
)
@event_source(data_class=APIGatewayProxyEvent)
def handler(event: APIGatewayProxyEvent, _: Context) -> Tuple:
    tenant_id = get_tenant_id_from_api_gw_request(event)
    event_body = load_json_with_validation(event["body"]) if event["body"] else {}
    request = ManualExecutionRequest(**event_body)

    try:
        manual_execution_handler = ManualExecutionHandler.fromManualExecutionRequest(tenant_id, request)
    except (
            EmptyPlanItemSlug,
            NoAssetsException,
            AssetNotExistsException,
            AssetConflictException,
            InactivePlanItemException,
            NoManualWorkflowsForPlanItemException,
            AssetWithNoWorkflowException,
    ) as e:
        logger.error(e)
        return HTTPStatus.BAD_REQUEST, ErrorResponse(error=HTTPStatus.BAD_REQUEST, message=e.message)
    jit_event_id = manual_execution_handler.trigger()
    add_label("jit_event_id", jit_event_id)
    return HTTPStatus.CREATED, ManualExecutionResponse(jit_event_id=jit_event_id)

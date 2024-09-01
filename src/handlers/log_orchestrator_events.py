from http import HTTPStatus
from typing import Dict

from aws_lambda_typing.context import Context
from aws_lambda_typing.events import APIGatewayProxyEventV2 as APIEvent
from jit_utils.lambda_decorators import exception_handler
from jit_utils.lambda_decorators import lambda_warmup_handler
from jit_utils.lambda_decorators import response_wrapper
from jit_utils.logger import logger_customer_id
from py_api import api_documentation
from py_api import Method
from py_api import PathParameter
from py_api import Request
from py_api import Response


@exception_handler()
@lambda_warmup_handler
@response_wrapper
@logger_customer_id(auto=True)
@api_documentation(
    post=Method(
        description='Deprecated - This Lambda logs the events from the Orchestrator.',
        path_parameters=[PathParameter(name="jit_event_id", schema=str, description="jit_event_id"),
                         PathParameter(name="execution_id", schema=str, description="execution_id")],
        request_body=Request(
            schema=Dict,
            title="NoBody",
            description='No request body',
        ),
        method_responses={
            HTTPStatus.OK: Response(
                schema=Dict,
                title="NoResponse",
                description='No response',
            ),

        },
    )
)
def handler(event: APIEvent, context: Context):
    """
    This Lambda logs the events from the Orchestrator.
    this allows us to see what is happening in the remote orchestrator.
    NOTE (15/12/22 - Arielb) - removed the code, we will need to remove from entrypoint then we can delete this lambda
    """
    pass

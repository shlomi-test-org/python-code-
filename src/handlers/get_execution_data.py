import json
import os
from http import HTTPStatus

from py_api import Method
from py_api import Response
from py_api import Parameter
from py_api import api_documentation
from aws_lambda_typing.context import Context
from aws_lambda_typing.events import APIGatewayProxyEventV1

from jit_utils.jit_clients.scm_service.exceptions import GetAccessTokenException
from jit_utils.lambda_decorators import DynamodbIsolationRule
from jit_utils.lambda_decorators import exception_handler
from jit_utils.lambda_decorators import general_tenant_isolation
from jit_utils.lambda_decorators import lambda_warmup_handler
from jit_utils.lambda_decorators import logger_cleanup_sensitive_data
from jit_utils.lambda_decorators import request_headers_keys
from jit_utils.lambda_decorators import response_wrapper
from jit_utils.lambda_decorators.core.tenant_isolation.isolation_rule import KMSIsolationRule
from jit_utils.lambda_decorators.core.tenant_isolation.isolation_rule import SSMIsolationRule
from jit_utils.logger import logger
from jit_utils.logger import logger_customer_id
from jit_utils.models.execution import DispatchExecutionEvent

from src.lib.aws_common import AwsAssumeRoleError
from src.lib.constants import EXECUTION_TABLE_NAME
from src.lib.cores.get_execution_data_core import fetch_execution_data
from src.lib.cores.get_execution_data_core import parse_and_validate_get_execution_data_request
from src.lib.cores.prepare_data_for_execution_core import add_secrets_values
from src.lib.exceptions import ExecutionDataAlreadyRetrievedError
from src.lib.exceptions import ExecutionDataNotFoundException
from src.lib.exceptions import ExecutionNotExistException
from src.lib.exceptions import InvalidExecutionStatusException
from src.lib.exceptions import InvalidGetExecutionDataRequest
from src.lib.models.execution_models import GetExecutionDataResponse


@exception_handler()
@lambda_warmup_handler
@request_headers_keys
@response_wrapper
@logger_cleanup_sensitive_data()
@general_tenant_isolation(
    rules=[
        DynamodbIsolationRule(
            table_name=EXECUTION_TABLE_NAME,
            actions=[
                "dynamodb:GetItem",
                "dynamodb:UpdateItem",
            ],
        ),
        SSMIsolationRule(
            account_id=os.environ["AWS_ACCOUNT_ID"],
            region=os.environ["AWS_REGION_NAME"],
            base_path="data",
            actions=['ssm:GetParameter'],
        ),
        KMSIsolationRule(
            account_id=os.environ["AWS_ACCOUNT_ID"],
            region=os.environ["AWS_REGION_NAME"],
            actions=["kms:Decrypt"],
        )
    ]
)
@logger_customer_id(auto=True)
@api_documentation(
    get=Method(
        description='Get execution data by tenant id, jit event id and execution id',
        query_parameters=[Parameter(name="jit_event_id", schema=str, description="jit event id to fetch data"), ],
        method_responses={
            HTTPStatus.OK: Response(
                schema=GetExecutionDataResponse,
                description='Execution Data',
            ),
        },
    )
)
def handler(event: APIGatewayProxyEventV1, context: Context):
    """
    Get executions by filter
    """
    logger.info(f"Get executions data by {event=}")
    try:
        execution_identifiers = parse_and_validate_get_execution_data_request(event)
    except InvalidGetExecutionDataRequest as invalid_get_execution_data_request:
        return HTTPStatus.BAD_REQUEST, {"message": str(invalid_get_execution_data_request)}

    try:
        execution_data = fetch_execution_data(
            tenant_id=execution_identifiers.tenant_id,
            jit_event_id=execution_identifiers.jit_event_id,
            execution_id=execution_identifiers.execution_id
        )
    except InvalidExecutionStatusException as e:
        return HTTPStatus.BAD_REQUEST, {"message": str(e)}
    except (ExecutionDataNotFoundException, ExecutionNotExistException) as e:
        return HTTPStatus.NOT_FOUND, {"message": str(e)}
    except ExecutionDataAlreadyRetrievedError:
        return HTTPStatus.GONE

    dispatch_execution_event = DispatchExecutionEvent(**json.loads(execution_data.execution_data_json))
    try:
        add_secrets_values(dispatch_execution_event)
    except (AwsAssumeRoleError, GetAccessTokenException) as e:
        return HTTPStatus.FAILED_DEPENDENCY, {"message": str(e)}

    return HTTPStatus.OK, {"data": dispatch_execution_event.json()}

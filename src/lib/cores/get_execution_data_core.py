from typing import cast
from typing import Optional

from aws_lambda_typing.events import APIGatewayProxyEventV1 as APIEvent
from jit_utils.logger import logger
from jit_utils.models.execution import BaseExecutionIdentifiers
from jit_utils.models.execution import ExecutionStatus

from src.lib.data.executions_manager import ExecutionsManager
from src.lib.exceptions import InvalidExecutionStatusException
from src.lib.exceptions import InvalidGetExecutionDataRequest
from src.lib.models.execution_models import ExecutionData


def parse_and_validate_get_execution_data_request(
        request: APIEvent,
) -> BaseExecutionIdentifiers:
    """
    The function parses the request
    It validates it received execution_id and jit_event_id
    Returns BaseExecutionIdentifiers with the identifiers for the execution data
    """
    handler_authorizer = request["requestContext"]["authorizer"]
    tenant_id = cast(str, handler_authorizer["tenant_id"])

    path_params = request.get("pathParameters", {})
    query_parameters = request.get("queryStringParameters", {})

    logger.info(
        f"Received the following {query_parameters=} and {path_params=} from request"
    )
    jit_event_id = query_parameters.get("jit_event_id", None)
    execution_id = path_params.get("execution_id", None)

    if not jit_event_id or not execution_id:
        raise InvalidGetExecutionDataRequest(
            "Received invalid request, request should contain valid "
            "jit_event_id and execution_id"
        )
    return BaseExecutionIdentifiers(
        tenant_id=tenant_id, jit_event_id=jit_event_id, execution_id=execution_id
    )


def verify_execution_in_dispatching_or_dispatched(
        execution_manager: ExecutionsManager,
        execution_id: str,
        tenant_id: str,
        jit_event_id: str,
        target_asset_name: Optional[str] = None,
) -> None:
    matching_execution = (
        execution_manager.get_execution_by_jit_event_id_and_execution_id(
            tenant_id=tenant_id,
            jit_event_id=jit_event_id,
            execution_id=execution_id,
            raise_=True,
        )
    )

    if matching_execution.status not in (
            ExecutionStatus.DISPATCHING,
            ExecutionStatus.DISPATCHED,
    ):
        raise InvalidExecutionStatusException(
            f"Execution {execution_id} is in status {matching_execution.status} and not dispatching/dispatched"
        )
    if target_asset_name is not None and matching_execution.asset_name != target_asset_name:
        raise InvalidExecutionStatusException(
            f"target asset requested was {target_asset_name}, "
            f"but in execution it's actual {matching_execution.asset_name}"
        )


def fetch_execution_data(
        tenant_id: str,
        jit_event_id: str,
        execution_id: str,
) -> ExecutionData:
    """
    Fetch execution data from dynamodb
    """
    logger.info(
        f"Fetching execution data for {tenant_id=} {jit_event_id=} {execution_id=}"
    )

    execution_manager = ExecutionsManager()
    verify_execution_in_dispatching_or_dispatched(
        execution_manager=execution_manager,
        execution_id=execution_id,
        tenant_id=tenant_id,
        jit_event_id=jit_event_id,
    )

    # Instead of using the get_execution_data method, we are using the update_execution_data_as_retrieved method
    # which also updates the execution_data_retrieved_at field
    return execution_manager.update_execution_data_as_retrieved(
        identifiers=BaseExecutionIdentifiers(
            tenant_id=tenant_id,
            jit_event_id=jit_event_id,
            execution_id=execution_id,
        )
    )

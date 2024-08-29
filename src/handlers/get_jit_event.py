from http import HTTPStatus
from typing import Tuple

from aws_lambda_powertools.utilities.data_classes import event_source, APIGatewayProxyEvent
from aws_lambda_typing.context import Context
from jit_utils.documentation.py_api import api_documentation, Method, Response
from jit_utils.lambda_decorators import (
    response_wrapper,
    lambda_warmup_handler,
    status_code_wrapper,
)
from jit_utils.logger import logger_customer_id, logger
from jit_utils.logger.logger import add_label
from jit_utils.models.common.documentation import RES_BAD_REQUEST, RES_NOT_FOUND
from jit_utils.models.trigger.jit_event_life_cycle import JitEventLifeCycleEntity

from src.lib.data.jit_event_life_cycle_table import JitEventLifeCycleManager
from src.lib.exceptions import JitEventLifeCycleDBEntityNotFoundException, JitEventIDNotProvidedException
from src.lib.utils import get_tenant_id_from_api_gw_request


@lambda_warmup_handler  # type: ignore
@response_wrapper
@status_code_wrapper(
    status_code_exceptions={JitEventLifeCycleDBEntityNotFoundException, JitEventIDNotProvidedException}
)
@logger_customer_id(auto=True)
@api_documentation(
    get=Method(
        is_public=False,
        tags=["Executions"],
        description="Get Jit Event by id.",
        summary="Get Jit Event by id",
        method_responses={
            HTTPStatus.OK: Response(
                schema=JitEventLifeCycleEntity,
                description="Jit Event Entity",
            ),
            HTTPStatus.BAD_REQUEST: RES_BAD_REQUEST,
            HTTPStatus.NOT_FOUND: RES_NOT_FOUND,
        },
    )
)  # TODO: add RBAC decorator
@event_source(data_class=APIGatewayProxyEvent)
def handler(event: APIGatewayProxyEvent, _: Context) -> Tuple:
    tenant_id = get_tenant_id_from_api_gw_request(event)
    jit_event_id = (event.path_parameters or {}).get("jit_event_id")
    logger.info(f'Handling get_jit_event request for {tenant_id=}, {jit_event_id=}')
    if not jit_event_id:
        raise JitEventIDNotProvidedException()

    add_label("jit_event_id", jit_event_id)
    jit_event_db_entity = JitEventLifeCycleManager().get_jit_event(tenant_id=tenant_id, jit_event_id=jit_event_id)
    jit_event_entity = JitEventLifeCycleEntity(**jit_event_db_entity.dict())

    return HTTPStatus.OK, jit_event_entity

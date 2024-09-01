from aws_lambda_typing.context import Context
from aws_lambda_typing.events import EventBridgeEvent
from jit_utils.logger import logger, logger_customer_id

from src.lib.cores.delete_tenant_data import delete_all_tenant_data
from src.lib.models.delete_tenant_data_request import DeleteTenantDataRequest


@logger_customer_id(auto=True)
def handler(event: EventBridgeEvent, _: Context) -> None:
    detail = event["detail"]
    logger.info(f"Got delete all tenant data request with detail: {detail}")
    delete_all_tenant_data(DeleteTenantDataRequest(**detail))

from http import HTTPStatus

from jit_utils.lambda_decorators import exception_handler, response_wrapper
from jit_utils.logger import logger, logger_customer_id
from jit_utils.models.delete_tenant_data_request import DeleteTenantDataRequest

from src.lib.cores.delete_tenant_data_core import delete_all_tenant_data


@exception_handler()
@response_wrapper
@logger_customer_id(auto=True)
def handler(event, context):
    detail = event["detail"]
    logger.info("Got delete all tenant data request with detail: {}".format(detail))
    delete_all_tenant_data(DeleteTenantDataRequest(**detail))
    return HTTPStatus.OK

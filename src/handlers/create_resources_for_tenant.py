from jit_utils.lambda_decorators import dynamodb_tenant_isolation
from jit_utils.lambda_decorators import DynamodbIsolationRule
from jit_utils.lambda_decorators import exception_handler
from jit_utils.lambda_decorators import lambda_warmup_handler
from jit_utils.logger import logger
from jit_utils.logger import logger_customer_id

from src.lib.constants import RESOURCES_TABLE_NAME
from src.lib.cores.create_resources_for_tenant_core import create_resource_for_tenant
from src.lib.models.tenants_models import TenantCreated


@exception_handler()
@lambda_warmup_handler
@logger_customer_id(auto=True)
@dynamodb_tenant_isolation(
    rules=[
        DynamodbIsolationRule(
            table_name=RESOURCES_TABLE_NAME,
            actions=["dynamodb:PutItem"],
        )
    ]
)
def handler(event, context):
    """
    Receives an event from the Tenant service when a tenant is created, and creates new resources for the tenant.
    """
    logger.info(f"{event=}")

    body = event["detail"]
    tenant_created_event = TenantCreated(**body)
    logger.info(f"{tenant_created_event=}")
    created_resources = create_resource_for_tenant(tenant_created_event.tenant_id)
    logger.info(f"{created_resources=}")

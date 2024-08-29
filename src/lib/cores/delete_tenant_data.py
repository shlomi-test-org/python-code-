from src.lib.constants import ENRICHMENT_RESULTS_TABLE_NAME, JIT_EVENT_LIFE_CYCLE_TABLE_NAME
from src.lib.models.delete_tenant_data_request import DeleteTenantDataRequest
from jit_utils.utils.delete_tenant_data.dynamodb import delete_dynamodb_tenant_data
from jit_utils.logger import logger


def delete_all_tenant_data(request: DeleteTenantDataRequest) -> None:
    """
    Delete all the data of a tenant
    """
    tenant_id = request.tenant_id
    logger.info(f"Started removal of all the events of tenant: {tenant_id}")
    delete_dynamodb_tenant_data(ENRICHMENT_RESULTS_TABLE_NAME, tenant_id)
    delete_dynamodb_tenant_data(JIT_EVENT_LIFE_CYCLE_TABLE_NAME, tenant_id)
    logger.info("Successfully deleted tenant data from DynamoDB tables.")

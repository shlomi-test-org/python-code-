from jit_utils.logger import logger
from jit_utils.utils.delete_tenant_data.s3 import delete_s3_tenant_data
from jit_utils.models.delete_tenant_data_request import DeleteTenantDataRequest
from jit_utils.utils.delete_tenant_data.dynamodb import delete_dynamodb_tenant_data

from src.lib.constants import RESOURCES_TABLE_NAME
from src.lib.constants import S3_EXECUTION_OUTPUTS_BUCKET_NAME


def delete_all_tenant_data(request: DeleteTenantDataRequest):
    """
    Delete all the data of a tenant
    """
    tenant_id = request.tenant_id
    s3_buckets = [S3_EXECUTION_OUTPUTS_BUCKET_NAME]

    logger.info(f"Started removal of all data regarding tenant: {tenant_id}")
    delete_dynamodb_tenant_data(RESOURCES_TABLE_NAME, tenant_id)

    for s3_bucket in s3_buckets:
        delete_s3_tenant_data(s3_bucket, tenant_id)

    logger.info("Successfully removed all data from security review table")

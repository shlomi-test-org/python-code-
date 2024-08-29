from typing import List

from jit_utils.logger import logger

from src.lib.constants import MAX_RESOURCES_IN_USE
from src.lib.constants import UNLIMITED_MAX_RESOURCES_IN_USE
from src.lib.data.resources_manager import ResourcesManager
from jit_utils.models.execution import ResourceType
from src.lib.models.resource_models import Resource


def create_resource_for_tenant(tenant_id: str) -> List[Resource]:
    """
    Create a resource for a tenant.
    :param tenant_id:
    :return:
    """
    resources_manager = ResourcesManager()
    resources_to_create = [
        create_resource_object(tenant_id=tenant_id, resource_type=resource_type) for resource_type in
        ResourceType.values()
    ]

    logger.info(f"creating resources: {resources_to_create}")

    create_resources_queries = [
        resources_manager.generate_create_resource_query(resource) for resource in resources_to_create
    ]
    logger.info(f"creating resources queries: {create_resources_queries}")

    resources_manager.execute_transaction(create_resources_queries)

    return resources_to_create


def create_resource_object(tenant_id: str, resource_type: ResourceType) -> Resource:
    """
    Create a resource object for a tenant.
    :param tenant_id:
    :param resource_type:
    :return:
    """

    if resource_type in [ResourceType.JIT_HIGH_PRIORITY, ResourceType.CI_HIGH_PRIORITY]:
        max_resources_in_use = UNLIMITED_MAX_RESOURCES_IN_USE
    else:
        max_resources_in_use = MAX_RESOURCES_IN_USE

    return Resource(
        tenant_id=tenant_id,
        runner=resource_type,
        resource_type=resource_type,
        max_resources_in_use=max_resources_in_use
    )

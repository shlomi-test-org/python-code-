from datetime import datetime
from typing import List, Any, Dict

from jit_utils.logger import logger
from jit_utils.models.execution import Execution
from jit_utils.models.execution import ResourceType

from src.lib.data.resources_manager import ResourcesManager
from src.lib.models.resource_models import Resource,  ResourceInUse


def should_manage_resource(resource_type: ResourceType) -> bool:
    if resource_type not in ResourceType.manageable_types():
        logger.info(f"Should not manage resources for non-managed {resource_type=}")
        return False

    return True


def free_resource(tenant_id: str, resource_type: ResourceType, jit_event_id: str, execution_id: str) -> None:
    """
    Free the resources of the execution
    :param tenant_id: Tenant id
    :param resource_type: Resource type
    :param jit_event_id: JIT event id
    :param execution_id: Execution id
    :return:
    """
    if not should_manage_resource(resource_type=resource_type):
        return

    resources_manager = ResourcesManager()

    resource = Resource(
        tenant_id=tenant_id,
        resource_type=resource_type
    )
    now = datetime.utcnow()
    resource_in_use = ResourceInUse(
        tenant_id=tenant_id,
        resource_type=resource_type,
        jit_event_id=jit_event_id,
        execution_id=execution_id,
        created_at=now.isoformat(),
        created_at_ts=int(now.timestamp())
    )

    resources_manager.decrease_resource_in_use(resource, resource_in_use)


def generate_free_resource_queries(execution: Execution) -> List[Dict[str, Any]]:
    """
    Generate the queries to free the resources of the execution.
    In order to free a resource, we need to decrease the number of resources in use and
    delete the ResourceInUse entity.
    :param execution: Execution object
    :return: List of queries that handles the free of the resources operations.
    """
    if not should_manage_resource(resource_type=execution.resource_type):
        return []

    resources_manager = ResourcesManager()
    resource = Resource(
        tenant_id=execution.tenant_id,
        resource_type=execution.resource_type
    )

    decrease_resource_in_use_query = resources_manager.generate_decrease_resource_in_use_query(resource)
    delete_resource_in_use_query = resources_manager.generate_delete_resource_in_use_query(execution.tenant_id,
                                                                                           execution.jit_event_id,
                                                                                           execution.execution_id)
    return [decrease_resource_in_use_query, delete_resource_in_use_query]


def generate_allocate_resource_queries(execution: Execution):
    """
    Generate the queries to allocate the resources of the execution.
    In order to allocate a resource, we need to increase the number of resources in use and
    create a ResourceInUse entity.
    :param execution: Execution object
    :return: List of queries that handles the allocation of the resources operations.
    """
    resources_manager = ResourcesManager()

    resource = resources_manager.get_resource(execution.tenant_id, execution.resource_type)

    if not resource:
        raise Exception(f"Resource {execution.resource_type} not found for tenant {execution.tenant_id}")
    now = datetime.utcnow()
    resource_in_use = ResourceInUse(
        tenant_id=execution.tenant_id,
        resource_type=execution.resource_type,
        jit_event_id=execution.jit_event_id,
        execution_id=execution.execution_id,
        created_at=now.isoformat(),
        created_at_ts=int(now.timestamp())
    )

    increase_resource_in_use_query = resources_manager.generate_increase_resource_in_use_query(resource)
    create_resource_in_use_query = resources_manager.generate_create_resource_in_use_query(resource_in_use)
    return [increase_resource_in_use_query, create_resource_in_use_query]

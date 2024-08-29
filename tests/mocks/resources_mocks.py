# from uuid import uuid4
from datetime import datetime
from random import randint
from typing import Dict
from typing import List
from uuid import uuid4

from src.lib.constants import MESSAGE_ID
from jit_utils.models.execution import Execution
from jit_utils.models.execution import ResourceType
from src.lib.models.resource_models import Resource
from src.lib.models.resource_models import ResourceInUse
from src.lib.models.tenants_models import TenantCreated


def generate_mock_resources(tenant_id: str):
    """
    Generate mock of the resources of a tenant.

    :param tenant_id: The tenant id.
    :return: Mock of the resources of a tenant.
    """
    return [
        Resource(
            tenant_id=tenant_id,
            resource_type=resource_type,
            resources_in_use=randint(1, 10),
            max_resources_in_use=randint(10, 20)
        ) for resource_type in ResourceType.values()
    ]


def generate_messages_from_resources_in_use(
        resources_in_use: List[Execution]
) -> List[Dict[str, str]]:
    """
    Generate a list of messages from a list of resources in use.
    """
    return [{
        MESSAGE_ID: str(uuid4()),
        'body': resource_in_use.json(),

    } for resource_in_use in resources_in_use]


def generate_mock_resource_in_use(tenant_id: str, resource_type: ResourceType, amount: int) -> List[ResourceInUse]:
    """
    Generate mock of a resource in use.

    :param tenant_id: The tenant id.
    :param resource_type: The Resource type.
    :param amount: The amount of resources in use.
    :return: Mock of a resource in use.
    """
    return [ResourceInUse(
        tenant_id=tenant_id,
        resource_type=resource_type,
        jit_event_id=str(uuid4()),
        execution_id=str(uuid4()),
        created_at=datetime.utcnow().isoformat(),
        created_at_ts=int(datetime.utcnow().timestamp())
    ) for _ in range(amount)]


MOCK_TENANT_CREATED_EVENT = {
    "detail": TenantCreated(tenant_id=str(uuid4())).dict()
}

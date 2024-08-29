from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

from pydantic import parse_obj_as

from jit_utils.logger import logger
from jit_utils.models.execution import ResourceType

from src.lib.constants import (
    EXCLUSIVE_START_KEY,
    GSI1PK,
    GSI1SK,
    GSI2,
    GSI2PK,
    GSI2SK,
    LAST_EVALUATED_KEY,
    LIMIT,
    PK,
    RESOURCE_IN_USE,
    RESOURCES_TABLE_NAME,
    SK
)
from src.lib.data.db_table import DbTable
from src.lib.models.resource_models import Resource
from src.lib.models.resource_models import ResourceEntity
from src.lib.models.resource_models import ResourceInUse


class ResourcesManager(DbTable):
    """
    This class is responsible for managing the resources table
    """
    TABLE_NAME = RESOURCES_TABLE_NAME

    def __init__(self):
        super().__init__(self.TABLE_NAME)

    def create_resource(self, resource: Resource) -> Resource:
        """
        Creates a resource in the resources table.

        :param resource: Resource to be created
        :return: Created resource
        """
        pk = self.get_key(tenant=resource.tenant_id)
        sk = self.get_key(resource_type=resource.resource_type)
        resource_entity = ResourceEntity(
            PK=pk,
            SK=sk,
            **resource.dict(exclude_unset=True)
        )
        response = self.table.put_item(Item=resource_entity.dict(exclude_none=True))
        logger.info(f"Put item response: {response}")
        self._verify_response(response)

        return resource

    def generate_create_resource_query(self, resource: Resource) -> Dict[str, Any]:
        """
        Generate query for creating a resource.

        :param resource: Resource to be created
        :return: str
        """
        pk = self.get_key(tenant=resource.tenant_id)
        sk = self.get_key(resource_type=resource.resource_type)
        create_resource_query = {
            'Put': {
                'TableName': self.TABLE_NAME,
                'Item': self.convert_python_dict_to_dynamodb_object({
                    PK: pk,
                    SK: sk,
                    **resource.dict()
                })
            }
        }
        logger.info(f"Create resource query: {create_resource_query}")
        return create_resource_query

    def generate_increase_resource_in_use_query(self, resource: Resource) -> Dict[str, Any]:
        """
        Generate query for increasing the number of resources in use by 1.
        We need it as string because we will use it in a transaction.

        :param resource: Resource to be increased
        :return: str
        """
        pk = self.get_key(tenant=resource.tenant_id)
        sk = self.get_key(resource_type=resource.resource_type)
        increase_resource_in_use_query = {
            'Update': {
                'TableName': self.TABLE_NAME,
                'Key': self.convert_python_dict_to_dynamodb_object({
                    PK: pk,
                    SK: sk
                }),
                'UpdateExpression': "ADD #resources_in_use :inc",
                'ConditionExpression': "#resources_in_use < :max_resources_in_use",
                'ExpressionAttributeNames': {
                    "#resources_in_use": "resources_in_use"
                },
                'ExpressionAttributeValues': self.convert_python_dict_to_dynamodb_object({
                    ":inc": 1,
                    ":max_resources_in_use": resource.max_resources_in_use
                }),
            }
        }
        logger.info(f"Increase resource in use query: {increase_resource_in_use_query}")
        return increase_resource_in_use_query

    def generate_decrease_resource_in_use_query(self, resource: Resource) -> Dict[str, Any]:
        """
        Decreases the number of resources in use by 1.

        :param resource: Resource to be decreased
        :return: str
        """
        pk = self.get_key(tenant=resource.tenant_id)
        sk = self.get_key(resource_type=resource.resource_type)
        decrease_resource_in_use_query = {
            'Update': {
                'TableName': self.TABLE_NAME,
                'Key': self.convert_python_dict_to_dynamodb_object({
                    PK: pk,
                    SK: sk
                }),
                'UpdateExpression': "ADD #resources_in_use :inc",
                'ConditionExpression': "#resources_in_use > :min_resources_in_use",
                'ExpressionAttributeNames': {
                    "#resources_in_use": "resources_in_use"
                },
                'ExpressionAttributeValues': self.convert_python_dict_to_dynamodb_object({
                    ":inc": -1,
                    ":min_resources_in_use": 0
                }),
            }
        }
        return decrease_resource_in_use_query

    def get_resource(self, tenant_id: str, resource_type: ResourceType) -> Optional[Resource]:
        """
        Gets a resource from the resources table.

        :param tenant_id: Tenant ID
        :param resource_type: ResourceType
        :return: Resource
        """
        pk = self.get_key(tenant=tenant_id)
        sk = self.get_key(resource_type=resource_type)
        response = self.table.get_item(
            Key={
                PK: pk,
                SK: sk
            }
        )
        logger.info(f"Get item response: {response}")
        self._verify_response(response)

        item = response.get("Item", None)

        if not item:
            return None

        return Resource(**item)

    def generate_create_resource_in_use_query(self, resource_in_use: ResourceInUse) -> Dict[str, Any]:
        """
        Generates query for creating a resource in use.

        :param resource_in_use: ResourceInUse to be created
        :return: str
        """
        pk = self.get_key(tenant=resource_in_use.tenant_id)
        sk = self.get_key(jit_event_id=resource_in_use.jit_event_id, execution_id=resource_in_use.execution_id)
        gsi1pk = self.get_key(tenant=resource_in_use.tenant_id)
        gsi1sk = gsi2sk = resource_in_use.created_at
        gsi2pk = self.get_key(item_type=RESOURCE_IN_USE)
        create_resource_in_use_query = {
            'Put': {
                'TableName': self.TABLE_NAME,
                'Item': self.convert_python_dict_to_dynamodb_object({
                    PK: pk,
                    SK: sk,
                    GSI1PK: gsi1pk,
                    GSI1SK: gsi1sk,
                    GSI2PK: gsi2pk,
                    GSI2SK: gsi2sk,
                    **resource_in_use.dict(exclude_none=True)
                })
            }
        }
        return create_resource_in_use_query

    def generate_delete_resource_in_use_query(
            self,
            tenant_id: str,
            jit_event_id: str,
            execution_id: str
    ) -> Dict[str, Any]:
        """
        Generates query for deleting a resource in use for execution.

        :param tenant_id: tenant_id to deleted its resource
        :param jit_event_id: jit_event_id related to the resource
        :param execution_id: Execution related to the resource
        :return: Dict[str, Any]
        """
        pk = self.get_key(tenant=tenant_id)
        sk = self.get_key(jit_event_id=jit_event_id,
                          execution_id=execution_id)
        delete_resource_in_use_query = {
            'Delete': {
                'TableName': self.TABLE_NAME,
                'Key': self.convert_python_dict_to_dynamodb_object({
                    PK: pk,
                    SK: sk
                }),
                "ConditionExpression": "attribute_exists(PK)",
            }
        }
        return delete_resource_in_use_query

    def increase_resource_in_use(self, resource: Resource, resource_in_use: ResourceInUse) -> None:
        """
        Increases the number of resources in use.
        :param resource: Resource to be increased
        :param resource_in_use: ResourceInUse to be increased
        :return: None
        """
        logger.info(f"Increasing resource in use: {resource_in_use}")
        increase_resource_in_use_query = self.generate_increase_resource_in_use_query(resource)
        crease_resource_in_use_query = self.generate_create_resource_in_use_query(resource_in_use)
        response = self.execute_transaction([
            increase_resource_in_use_query,
            crease_resource_in_use_query
        ])
        logger.info(f"Increase resource in use response: {response}")
        self._verify_response(response)
        return response

    def decrease_resource_in_use(self, resource: Resource, resource_in_use: ResourceInUse) -> None:
        """
        Decreases the number of resources in use.
        :param resource: Resource to be decreased
        :param resource_in_use: ResourceInUse to be decreased
        :return: None
        """
        logger.info(f"Decreasing resource in use: {resource_in_use}")
        decrease_resource_in_use_query = self.generate_decrease_resource_in_use_query(resource)
        delete_resource_in_use_query = self.generate_delete_resource_in_use_query(resource_in_use.tenant_id,
                                                                                  resource_in_use.jit_event_id,
                                                                                  resource_in_use.execution_id)
        response = self.execute_transaction([
            decrease_resource_in_use_query,
            delete_resource_in_use_query
        ])
        logger.info(f"Decrease resource in use response: {response}")
        self._verify_response(response)
        return response

    def get_resource_in_use(self, tenant: str, jit_event_id: str, execution_id: str) -> Optional[ResourceInUse]:
        """
        Gets a resource in use from the resources in use table.
        :param tenant: Tenant ID
        :param jit_event_id: JIT event ID
        :param execution_id: Execution ID
        :return: ResourceInUse
        """
        pk = self.get_key(tenant=tenant)
        sk = self.get_key(jit_event_id=jit_event_id, execution_id=execution_id)
        response = self.table.get_item(
            Key={
                PK: pk,
                SK: sk
            }
        )
        logger.info(f"Get item response: {response}")
        self._verify_response(response)

        item = response.get("Item", None)

        if not item:
            return None

        return ResourceInUse(**item)

    def get_resources_in_use_exceeded_time_limitation(self, time_limitation: str, start_key=None, limit=None) -> \
            Tuple[List[ResourceInUse], str]:
        """
        Retrieves all resources in use that exceeded the time limitation.
        """
        logger.info(f"Retrieving resources in use that exceeded the time limitation: {time_limitation}")
        gsi2pk = self.get_key(item_type=RESOURCE_IN_USE)
        gsi2sk = time_limitation
        query_kwargs = {
            "KeyConditionExpression": "#gsi2pk = :gsi2pk AND #gsi2sk < :gsi2sk",
            "ExpressionAttributeNames": {
                "#gsi2pk": GSI2PK,
                "#gsi2sk": GSI2SK
            },
            "ExpressionAttributeValues": {
                ":gsi2pk": gsi2pk,
                ":gsi2sk": gsi2sk
            },
            "IndexName": GSI2,
        }

        if start_key:
            query_kwargs[EXCLUSIVE_START_KEY] = start_key

        if limit:
            query_kwargs[LIMIT] = limit

        response = self.table.query(**query_kwargs)
        self._verify_response(response)
        items = response.get("Items", [])
        logger.info(f"Retrieved {len(items)} resources in use that exceeded the time limitation: {time_limitation}")
        resources_in_use = parse_obj_as(List[ResourceInUse], items)
        return resources_in_use, response.get(LAST_EVALUATED_KEY, "")

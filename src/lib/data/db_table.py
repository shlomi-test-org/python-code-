from typing import Any, Dict

import boto3
from jit_utils.aws_clients.config.aws_config import get_aws_config
from jit_utils.logger import logger
from jit_utils.lambda_decorators import get_dynamodb_session_keys

from src.lib.constants import PK, SK


class DbTable:
    def __init__(self, table: str) -> None:
        aws_config = get_dynamodb_session_keys() or get_aws_config()
        self.dynamodb = boto3.resource("dynamodb", **aws_config)
        self.table = self.dynamodb.Table(table)
        self.client = boto3.client("dynamodb", **aws_config)

    @staticmethod
    def get_key(**kwargs: Any) -> str:
        return '#'.join(f'{key.upper()}#{str(value).lower()}' for key, value in kwargs.items())

    @staticmethod
    def _verify_response(response: Dict[str, Any]) -> None:
        if "Error" in response:
            logger.error(response)
            raise Exception(f"HTTPStatusCode: {response['ResponseMetadata']['HTTPStatusCode']}"
                            f"message={response['Error']['Message']}")

    def delete_tenant_data(self, tenant_id: str) -> int:
        """
        Deletes all items for a given tenant.
        """
        pk = self.get_key(tenant=tenant_id)
        done = False
        start_key = None
        deleted_instances_amount = 0

        # Based on AWS docs step 4.3: Scan:
        # https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/GettingStarted.Python.04.html
        # We need to have convention of using pagination everywhere we use scan or query, so we
        # won't have bugs related to amount of items.
        query_kwargs = {
            "KeyConditionExpression": "#pk = :pk",
            "ExpressionAttributeNames": {"#pk": PK},
            "ExpressionAttributeValues": {":pk": pk},
            "Limit": 25  # Limit is 25 because this is the amount of items we can delete in batch_write
        }

        while not done:
            if start_key:
                query_kwargs['ExclusiveStartKey'] = start_key  # type: ignore
            try:
                response = self.table.query(**query_kwargs)  # type: ignore
            except Exception as e:
                logger.error(f"Failed to query the data: {e}")
                raise e

            logger.info(f"Query response: {response}")
            self._verify_response(response)  # type: ignore
            items = response.get("Items", [])

            with self.table.batch_writer() as batch:
                for item in items:
                    batch.delete_item(Key={PK: item[PK], SK: item[SK]})
                    deleted_instances_amount += 1

            start_key = response.get('LastEvaluatedKey', None)
            done = start_key is None

        logger.info(f"Deleted {deleted_instances_amount} items of tenant {tenant_id}")

        return deleted_instances_amount

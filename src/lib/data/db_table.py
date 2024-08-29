from typing import Any
from typing import Dict
from typing import List
from typing import Mapping

import boto3
from jit_utils.aws_clients.config.aws_config import get_aws_config
from jit_utils.lambda_decorators import get_dynamodb_session_keys
from jit_utils.lambda_decorators.core.tenant_isolation.tenant_isolation_context import get_general_session_keys
from jit_utils.logger import logger


class DbTable:
    def __init__(self, table):
        aws_config = get_general_session_keys() or get_dynamodb_session_keys() or get_aws_config()
        dynamodb = boto3.resource("dynamodb", **aws_config)
        self.table = dynamodb.Table(table)
        self.client = boto3.client("dynamodb", **aws_config)
        logger.info("Initializing dynamodb client")

    @staticmethod
    def get_key(**kwargs):
        return '#'.join(f'{key.upper()}#{str(value).lower()}' for key, value in kwargs.items())

    @staticmethod
    def parse_dynamodb_item_to_python_dict(item) -> Dict[str, Any]:
        deserializer = boto3.dynamodb.types.TypeDeserializer()
        return {k: deserializer.deserialize(v) for k, v in item.items()}

    @staticmethod
    def convert_python_dict_to_dynamodb_object(item: Mapping[str, Any]) -> Dict[str, Any]:
        """
        Converts python dict to dynamodb object.
        """
        serializer = boto3.dynamodb.types.TypeSerializer()
        return {k: serializer.serialize(v) for k, v in item.items()}

    @staticmethod
    def _verify_response(response):
        logger.debug(f'Validating response: {response=}')
        if "Error" in response:
            logger.error(response)
            raise Exception(f"HTTPStatusCode: {response['ResponseMetadata']['HTTPStatusCode']}"
                            f"message={response['Error']['Message']}")

    def execute_transaction(self, transaction_items: List[Dict[str, Any]]) -> Any:
        """
        Executes a transaction.
        """
        logger.info(f"Executing transaction: {transaction_items}")
        if not transaction_items:
            logger.info("No transaction items - skipping")
            return

        try:
            response = self.client.transact_write_items(
                TransactItems=transaction_items
            )
        except Exception as e:
            logger.error(f"Failed to execute transaction: {e}")
            raise e

        logger.info(f"Transaction response: {response}")
        self._verify_response(response)

        return response

import os

from jit_utils.lambda_decorators import DynamodbIsolationRule
from jit_utils.lambda_decorators import dynamodb_tenant_isolation
from jit_utils.lambda_decorators import exception_handler
from jit_utils.lambda_decorators import feature_flags_init_client
from jit_utils.lambda_decorators import lambda_warmup_handler
from jit_utils.lambda_decorators import limit_lambda_invocations
from jit_utils.logger import logger
from jit_utils.logger import logger_customer_id

from src.lib.constants import EXECUTION_TABLE_NAME
from src.lib.constants import RESOURCES_TABLE_NAME
from src.lib.cores.allocate_runner_resources_core import allocate_runner_resources
from src.lib.data.executions_manager import ExecutionsManager
from jit_utils.models.execution import Execution


@exception_handler()
@lambda_warmup_handler
@limit_lambda_invocations(max_invocations=os.getenv("MAX_INVOCATIONS_PER_HOUR") or 10000)
@logger_customer_id(auto=True)
@dynamodb_tenant_isolation(
    rules=[
        DynamodbIsolationRule(
            table_name=EXECUTION_TABLE_NAME,
            actions=["dynamodb:GetItem", "dynamodb:UpdateItem", "dynamodb:Query"]
        ),
        DynamodbIsolationRule(
            table_name=RESOURCES_TABLE_NAME,
            actions=["dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:GetItem"]
        ),
    ]
)
@feature_flags_init_client()
def handler(event, _):
    """
    Handle the dynamodb stream and send it to the enrich and dispatch lambda.
    """
    logger.info(f"Received DynamoDB stream {event=}")
    record = event.get('Records')[0]
    event_type = record.get('eventName')
    new_image = record.get("dynamodb", {}).get("NewImage", {})
    logger.info(f"New image {new_image}")
    executions_manager = ExecutionsManager()
    parsed_execution = executions_manager.parse_dynamodb_item_to_python_dict(new_image)
    logger.info(f"Parsed execution {parsed_execution}")
    execution = Execution(**parsed_execution)
    logger.info(f"{execution=}")

    allocate_runner_resources(event_type, execution)

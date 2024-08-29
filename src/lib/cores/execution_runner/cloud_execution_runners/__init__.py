from typing import Type

from jit_utils.lambda_decorators.feature_flags import evaluate_feature_flag
from jit_utils.logger import logger
from jit_utils.models.execution import Execution

from src.lib.cores.execution_runner.cloud_execution_runners.cloud_execution_runner import CloudExecutionRunner
from src.lib.cores.execution_runner.cloud_execution_runners.gcp_execution_runner import GcpExecutionRunner
from src.lib.cores.execution_runner.cloud_execution_runners.aws_execution_runner import AwsExecutionRunner


def _is_jit_gcp_runner(tenant_id: str) -> bool:
    return evaluate_feature_flag(
        feature_flag_key="use-jit-gcp-runner",
        payload={"key": tenant_id},
        local_test_value=False,
        raise_exception=False,
        default_value=False,
    )


def get_cloud_execution_runner_type(execution: Execution) -> Type[CloudExecutionRunner]:
    """
    CloudExecutionRunner is running controls inside our backend.
    For specific tenant we need to run the executions inside our GCP backend instead of our AWS backend.
    """
    if _is_jit_gcp_runner(execution.tenant_id):
        logger.info("Going to use Cloud GCP Runner")
        return GcpExecutionRunner
    logger.info("Going to use Cloud AWS Runner")
    return AwsExecutionRunner

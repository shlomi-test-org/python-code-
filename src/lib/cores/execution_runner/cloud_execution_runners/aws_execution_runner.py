from typing import List, Optional

from jit_utils.aws_clients.batch import BatchClient
from jit_utils.aws_clients.kms import KmsClient
from jit_utils.logger import logger

from src.lib.aws_common import run_fargate_task, get_job_definition
from src.lib.constants import ECS_TASK_KMS_ARN, KMS_KEY_ID_ENV_VAR, TERMINATED_BY_WATCHDOG_REASON
from src.lib.cores.execution_runner.cloud_execution_runners.cloud_execution_runner import CloudExecutionRunner
from src.lib.cores.execution_runner.execution_runner import ExecutionRunnerDispatchError
from jit_utils.models.execution import Execution

# https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/batch/client/submit_job.html#
JOB_NAME_MAX_LENGTH = 128


class AwsExecutionRunner(CloudExecutionRunner):
    """
    Public methods overrides
    """
    @classmethod
    def dispatch(cls, executions: List[Execution], callback_token: str) -> Optional[str]:
        """
        Currently supports dispatching a SINGLE execution, we will return the run_id of the dispatched execution.
        """
        logger.info("Dispatching execution using AwsExecutionRunner")
        cls.store_executions_data_in_db(executions, callback_token)
        encrypted_token = cls._encrypt_jit_token(callback_token)
        for execution in executions:
            env, command = cls._setup_for_execution(execution, encrypted_token)
            env[KMS_KEY_ID_ENV_VAR] = KmsClient.get_key_id(ECS_TASK_KMS_ARN)
            job_definition = get_job_definition(image_ecr_path=execution.context.job.steps[0].uses)

            logger.info(f"Going to dispatch execution using AwsExecutionRunner {job_definition=}")
            try:
                run_id = run_fargate_task(
                    job_name=cls._job_name(execution=execution, max_length=JOB_NAME_MAX_LENGTH),
                    job_definition=job_definition,
                    env=env,
                    command=command,
                )
                return run_id
            except Exception as exc:
                logger.exception(f"Exception during dispatch {exc}")
                raise ExecutionRunnerDispatchError(message=str(exc))

    def terminate(self) -> None:
        """
        Cancel a workflow run on JitRunner
        """
        batch_client = BatchClient()
        batch_client.terminate(self._execution.run_id, TERMINATED_BY_WATCHDOG_REASON)

    """
    Protected methods
    """

    @staticmethod
    def _encrypt_jit_token(callback_token: str) -> str:
        """
        In order to create "trust" between the control to our backend, we are providing the control with an encrypted
        jwt token.
        Only containers that are running with the right permissions would be able to decrypt this token and use it to
        communicate with our backend.

        Jit runner - is running in fargate container (using the Batch service), and has an IAM role with permissions
        to decrypt the token.
        """
        logger.info("Encrypting the jit token to inject to the control execution")
        kms_client = KmsClient()
        kms_key_id = KmsClient.get_key_id(ECS_TASK_KMS_ARN)
        encrypted_token = kms_client.encrypt(key_id=kms_key_id, secret=callback_token)
        logger.info("KMS Token Encrypted")
        return encrypted_token

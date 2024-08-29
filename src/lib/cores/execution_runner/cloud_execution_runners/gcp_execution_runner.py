import os
from typing import List, Optional

from jit_utils.aws_clients.ssm import SSMClient
from jit_utils.aws_clients.s3 import S3Client
from jit_utils.logger import logger
from jit_utils.models.execution import Execution

from src.lib.constants import (
    WATCHDOG_GRACE_PERIOD,
    GCP_KMS_KEY_NAME,
    ENV_NAME_STRING,
    GCP_KMS_KEY_NAME_ENV_VAR,
    S3_OBJECT_FORMAT,
    JIT_GCP_JOB_LOGS_BUCKET_NAME,
)
from src.lib.cores.execution_runner.cloud_execution_runners.cloud_execution_runner import CloudExecutionRunner
from src.lib.cores.execution_runner.execution_runner import ExecutionRunnerDispatchError

if ENV_NAME_STRING != "local" or "IS_PYTEST" in os.environ:
    # The gcp_common module import libraries from google SDK which using a c based library that can't work in localstack
    from src.lib.gcp_common import (get_gcp_credentials, get_gcp_image_uri, encrypt_text, GcpLogicError,
                                    run_batch_job, get_gcp_job_execution_logs, delete_job)

# This will contain the cached credentials for the GCP Service accounts between lambda invocations to avoid the need
# to create them on every invocation
cached_dispatch_credentials = None
cached_free_resources_credentials = None

# https://cloud.google.com/python/docs/reference/batch/latest/google.cloud.batch_v1.types.CreateJobRequest
JOB_ID_MAX_LENGTH = 63


class GcpExecutionRunner(CloudExecutionRunner):
    """
    Public methods overrides
    """

    @classmethod
    def dispatch(cls, executions: List[Execution], callback_token: str) -> Optional[str]:
        """
        Currently supports dispatching a SINGLE execution, we will return the run_id of the dispatched execution.
        """
        logger.info("Dispatching executions using GcpExecutionRunner")
        cls.store_executions_data_in_db(executions, callback_token)
        encrypted_token = cls._encrypt_jit_token(callback_token)
        for execution in executions:  # currently limited to one execution
            env, command = cls._setup_for_execution(execution, encrypted_token)
            env[GCP_KMS_KEY_NAME_ENV_VAR] = GCP_KMS_KEY_NAME

            try:
                image_uri = get_gcp_image_uri(image_ecr_path=execution.context.job.steps[0].uses)
                logger.info(f"Going to dispatch execution using GcpExecutionRunner {image_uri=}")
                run_id = run_batch_job(
                    credentials=cls._gcp_batch_dispatch_credentials(),
                    job_name=cls._job_name(execution=execution, max_length=JOB_ID_MAX_LENGTH),
                    max_run_time=GcpExecutionRunner(execution).running_state_timeout + WATCHDOG_GRACE_PERIOD,
                    image_uri=image_uri,
                    env=env,
                    command=command,
                    high_specs=cls._needs_high_specs_container(image_uri),
                )
                return run_id
            except GcpLogicError as exc:
                logger.exception(f"Exception during dispatch {exc}")
                raise ExecutionRunnerDispatchError(message=str(exc))

    @property
    def logs_url(self) -> Optional[str]:
        return S3_OBJECT_FORMAT.format(bucket_name=JIT_GCP_JOB_LOGS_BUCKET_NAME, object_key=self._logs_key)

    def terminate(self) -> None:
        """
        Cancel a workflow run on JitRunner & Uploads the logs to S3
        """
        logger.info(f"Terminating execution {self._execution.execution_id}")

        logger.info(f"Fetching logs from GCP for job: {self._execution.run_id=}")
        logs: str = get_gcp_job_execution_logs(
            credentials=self._gcp_free_resources_credentials,
            job_path=self._execution.run_id
        )
        logger.info("Successfully fetched logs from GCP")

        logger.info(f"Saving logs to s3 bucket: {JIT_GCP_JOB_LOGS_BUCKET_NAME}, with {self._logs_key=}")
        S3Client().put_object(bucket_name=JIT_GCP_JOB_LOGS_BUCKET_NAME, key=self._logs_key, body=logs)
        logger.info("Successfully saved logs to s3")

        logger.info(f"Deleting job: {self._execution.run_id}")
        delete_job(credentials=self._gcp_free_resources_credentials, job_path=self._execution.run_id)
        logger.info("Successfully deleted job")

    """
    Protected methods overrides
    """

    @staticmethod
    def _encrypt_jit_token(callback_token: str) -> str:
        """
        Jit GCP runner - is running using the Batch service under containers, and has a service account with permissions
        to decrypt the token.
        """
        return encrypt_text(
            credentials=GcpExecutionRunner._gcp_batch_dispatch_credentials(),
            key_name=GCP_KMS_KEY_NAME,
            text=callback_token,
        )

    """
    Private methods
    """

    @staticmethod
    def _needs_high_specs_container(image_uri: str) -> bool:
        """
        THIS IS A TEMPORARY SOLUTION!
        Currently, we have no way to know data about the control from outside its scope (since it's declared in the
        control level).
        We need to know the control's container spec requirements, so that's why we pushed this *BAD* solution,
        until we have a better mechanism to track controls properties.
        """
        HIGH_REQUIREMENTS_CONTROL = ["prowler", "zap"]
        for control in HIGH_REQUIREMENTS_CONTROL:
            if control in image_uri:
                return True
        return False

    @staticmethod
    def _gcp_batch_dispatch_credentials():
        global cached_dispatch_credentials
        if cached_dispatch_credentials is None:
            credentials_str = SSMClient().get(
                name=f"/{ENV_NAME_STRING}/infra/gcp-batch/dispatch-gcp-credentials",
                is_secret=True,
            )
            cached_dispatch_credentials = get_gcp_credentials(credentials_str)
        return cached_dispatch_credentials

    @property
    def _gcp_free_resources_credentials(self):
        global cached_free_resources_credentials
        if cached_free_resources_credentials is None:
            credentials_str = SSMClient().get(
                name=f"/{ENV_NAME_STRING}/infra/gcp-batch/free-resources-gcp-credentials",
                is_secret=True,
            )
            cached_free_resources_credentials = get_gcp_credentials(credentials_str)
        return cached_free_resources_credentials

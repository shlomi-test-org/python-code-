import datetime
import os
import re
from typing import Dict
from typing import Optional
from typing import Set

from jit_utils.aws_clients.s3 import S3Client
from jit_utils.aws_clients.utils.secret_utils import get_secret_value
from jit_utils.jit_clients.scm_service.client import ScmServiceClient
from jit_utils.logger import logger
from jit_utils.models.execution import CallbackUrls
from jit_utils.models.execution import DispatchExecutionEvent
from jit_utils.models.execution import Execution
from jit_utils.models.execution_context import Auth
from jit_utils.models.execution_context import AuthType
from jit_utils.models.execution_context import ExecutionContext
from jit_utils.models.execution_context import WorkflowJob
from jit_utils.models.oauth.entities import VendorEnum
from jit_utils.service_discovery import get_service_url

from src.lib.constants import EXECUTION_LOGS_S3_BUCKET
from src.lib.constants import FINDINGS_UPLOAD_S3_BUCKET
from src.lib.constants import FINDINGS_UPLOAD_URL_EXPIRATION_SECONDS
from src.lib.constants import LOGS_UPLOAD_URL_EXPIRATION_SECONDS
from src.lib.cores.fargate.aws_account_core import get_tenant_aws_credentials
from src.lib.endpoints import ACTIONS_CALLBACK_URL, UPDATE_FINDING_CALLBACK_URL
from src.lib.endpoints import EXECUTION_CALLBACK_URL
from src.lib.endpoints import GET_FINDING_SCHEMA_BY_VERSION_CALLBACK_URL
from src.lib.endpoints import IGNORES_CALLBACK_URL


def get_callback_urls(execution: Execution) -> CallbackUrls:
    callback_urls = generate_callback_urls(
        tenant_id=execution.context.jit_event.tenant_id,
        asset_id=execution.context.asset.asset_id,
        jit_event_id=execution.context.jit_event.jit_event_id,
        execution_id=execution.execution_id
    )
    return callback_urls


def add_secrets_values(event: DispatchExecutionEvent) -> None:
    """
    This method will add all the secret values required by the execution data.
    THE VALUES ARE NOT ENCRYPTED!!! USE THIS METHOD WISELY

    if secret parameter not found -> return None
    """
    logger.info("Adding secrets to the event")
    event.secrets = get_secret_with_values(tenant_id=event.context.jit_event.tenant_id, job=event.context.job)
    event.context = run_runner_setup_services(context=event.context)


def get_secret_with_values(tenant_id: str, job: WorkflowJob) -> Dict:
    """
    input: the Workflowjob
    logic: the function would go over all the workflow, and would find any instance of "jit_secrets" text
    and would fetch the secret data by name
    """

    def get_used_secrets_list(params: str) -> Set[str]:
        # this regex would return all values between jit_secrets. and the next none letter value
        regex = r"jit_secrets\.(\S+?)\s*(?![\w\d])"
        matches = set(re.findall(regex, params))
        return matches

    secret_with_value: Dict = {}
    all_used_secrets = get_used_secrets_list(str(job.steps))
    logger.info(f"Bringing secrets values for {all_used_secrets}")
    for secret_name in all_used_secrets:
        secret_value = get_secret_value(tenant_id=tenant_id, secret_name=secret_name)
        if secret_value:
            secret_with_value[secret_name] = secret_value

    return secret_with_value


def handle_auth_service(context: ExecutionContext, auth_type: Optional[AuthType]):
    logger.info(f"Handling auth service for {auth_type=}")
    if auth_type == AuthType.AWS_IAM_ROLE:
        installation_id = context.installation.installation_id
        aws_credentials = get_tenant_aws_credentials(
            tenant_id=context.jit_event.tenant_id,
            installation_id=installation_id,
            asset_id=context.asset.asset_id,
            assume_role_id=context.asset.aws_account_id or installation_id,
            aws_external_id=context.asset.aws_jit_role_external_id,
            aws_jit_role_name=context.asset.aws_jit_role_name,
        )
        context.auth = Auth(type=auth_type, config=aws_credentials)

    elif auth_type == AuthType.SCM_TOKEN:
        logger.info("Retrieving scm token for context")
        scm_service = ScmServiceClient(vendor=VendorEnum(context.installation.vendor))
        context.auth = Auth(
            type=auth_type,
            config={
                "scm_token": scm_service.get_access_token(
                    app_id=context.installation.app_id,
                    installation_id=context.installation.installation_id,
                ).token
            }
        )

    return context


def run_runner_setup_services(context: ExecutionContext) -> ExecutionContext:
    if runner_setup := context.job.runner.setup:
        context = handle_auth_service(context=context, auth_type=runner_setup.auth_type)

    return context


def generate_callback_urls(tenant_id: str, asset_id: str, jit_event_id: str, execution_id: str) -> CallbackUrls:
    """
    Generates the callback urls for the execution.
    """
    # Generate the callback url
    api_host = os.environ.get("API_HOST")
    execution_service_base_url = get_service_url("execution-service")["service_url"]
    findings_service_base_url = get_service_url("finding-service")["service_url"]
    action_service_base_url = get_service_url("action-service")["service_url"]
    base_api_url = f'https://{api_host}' if api_host else None

    execution_callback_url = EXECUTION_CALLBACK_URL.format(base=execution_service_base_url)
    get_ignore_list_url = IGNORES_CALLBACK_URL.format(base=findings_service_base_url, asset_id=asset_id,
                                                      control_name="{control_name}")  # only known in the orchestrator
    presigned_findings_upload_url = generate_findings_upload_url(
        tenant_id=tenant_id, jit_event_id=jit_event_id, execution_id=execution_id
    )
    presigned_logs_upload_url = generate_logs_upload_url(
        tenant_id=tenant_id, jit_event_id=jit_event_id, execution_id=execution_id
    )

    # Note that the other params ('action_id', 'finding_id') will be formatted by the control itself
    actions_callback_url = ACTIONS_CALLBACK_URL.format(base=action_service_base_url, action_id='{action_id}',
                                                       finding_id='{finding_id}')

    get_finding_model_version_url = GET_FINDING_SCHEMA_BY_VERSION_CALLBACK_URL.format(base=findings_service_base_url,
                                                                                      schema_type="{schema_type}",
                                                                                      schema_version="{schema_version}")
    update_finding_callback_url = UPDATE_FINDING_CALLBACK_URL.format(base=findings_service_base_url,
                                                                     finding_id='{finding_id}')

    return CallbackUrls(
        execution=execution_callback_url,
        presigned_findings_upload_url=presigned_findings_upload_url,
        ignores=get_ignore_list_url,
        presigned_logs_upload_url=presigned_logs_upload_url,
        finding_schema=get_finding_model_version_url,
        base_api=base_api_url,
        update_finding_url=update_finding_callback_url,
        actions=actions_callback_url,
    )


def generate_findings_upload_url(tenant_id: str, jit_event_id: str, execution_id: str) -> str:
    """
    Generated an S3 presigned URL that the client (entrypoint) will use to upload the findings to S3.
    Returns the URL itself.
    """
    s3_client = S3Client()
    return s3_client.generate_put_presigned_url(
        bucket_name=FINDINGS_UPLOAD_S3_BUCKET,
        key=f'{tenant_id}/{jit_event_id}-{execution_id}-{datetime.datetime.now()}.json',
        expiration_seconds=FINDINGS_UPLOAD_URL_EXPIRATION_SECONDS,
    )


def generate_logs_upload_url(tenant_id: str, jit_event_id: str, execution_id: str) -> str:
    """
    Generates an S3 presigned URL that the client (entrypoint) will use to upload the logs to S3.
    Returns the URL itself.
    """
    s3_client = S3Client()
    return s3_client.generate_put_presigned_url(
        bucket_name=EXECUTION_LOGS_S3_BUCKET,
        key=f'{tenant_id}/{jit_event_id}-{execution_id}.log',
        expiration_seconds=LOGS_UPLOAD_URL_EXPIRATION_SECONDS,
    )

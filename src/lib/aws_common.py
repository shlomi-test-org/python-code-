import hashlib
import json
import os
from datetime import datetime
from typing import Dict
from typing import List
from typing import Optional

import boto3
import cachetools.func
from jit_utils.aws_clients.config.aws_config import get_aws_config
from jit_utils.jit_clients.asset_service.client import AssetService
from jit_utils.jit_clients.authentication_service.client import AuthenticationService
from jit_utils.logger import logger
from jit_utils.logger.logger import add_label
from jit_utils.models.asset.entities import AssetStatus
from jit_utils.models.asset.requests import UpdateAssetRequest
from mypy_boto3_batch import BatchClient
from mypy_boto3_batch.type_defs import ContainerOverridesTypeDef
from mypy_boto3_batch.type_defs import KeyValuePairTypeDef
from pydantic.json import pydantic_encoder

from src.lib.clients.eventbridge import EventsClient
from src.lib.constants import AWS, IS_SILENT_INVOCATION_ENV_VAR
from src.lib.constants import AWS_COMMON_ASSUMED_ROLE_CREDENTIALS_KEY
from src.lib.constants import AWS_COMMON_BATCH_CLIENT_NAME
from src.lib.constants import AWS_COMMON_CREDENTIALS_MAP
from src.lib.constants import AWS_COMMON_REGION_NAME_KEY
from src.lib.constants import AWS_COMMON_SESSION_SECONDS_DURATION
from src.lib.constants import AWS_COMMON_STS_CLIENT_NAME
from src.lib.constants import AWS_JIT_ROLE
from src.lib.constants import EXECUTION_EVENT_BUS_NAME
from src.lib.constants import EXECUTION_EVENT_SOURCE
from src.lib.constants import EXECUTION_FARGATE_TASK_FINISHED
from src.lib.constants import FAILED_TO_ASSUME_ROLE_ASSET_STATUS_DETAILS
from src.lib.constants import INSTALLATION_PARTIAL_UPDATE_EVENT_BUS
from src.lib.constants import INSTALLATION_PARTIAL_UPDATE_EVENT_DETAIL_TYPE
from src.lib.constants import REGION_NAME
from src.lib.cores.fargate.constants import FARGATE_TASKS_BATCH_QUEUE_NAME
from src.lib.models.ecs_models import ECSTaskData
from src.lib.models.tenants_models import InstallationStatus
from src.lib.models.tenants_models import PartialUpdateInstallationRequest

FARGATE_BATCH_JOB_TIMEOUT = 6 * 60 * 60  # 6 hours


class AwsLogicError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class AwsAssumeRoleError(Exception):
    def __init__(self, message="Error while assuming role"):
        self.message = message
        super().__init__(self.message)


def _calculate_external_id(tenant_id: str, installation_id: str) -> str:
    return hashlib.sha256(f"{tenant_id}{installation_id}".encode()).hexdigest()


def get_aws_credentials(sts_assume_role_response: Dict) -> Dict:
    credentials = sts_assume_role_response[AWS_COMMON_ASSUMED_ROLE_CREDENTIALS_KEY]
    aws_config_credentials = {
        k: credentials[v] for k, v in AWS_COMMON_CREDENTIALS_MAP.items()
    }
    return aws_config_credentials


def send_installation_partial_update_event_error(
        tenant_id: str, installation_id: str, external_id: str
) -> PartialUpdateInstallationRequest:
    status = InstallationStatus.ERROR
    status_details = {
        "error_type": "ACCESS_FAILURE",
        "error_message": f"Failed to assume role {AWS_JIT_ROLE} with {external_id=}",
        "detected_at": datetime.utcnow().isoformat(),
        "source": EXECUTION_EVENT_SOURCE,
    }
    logger.info(
        f"Preparing a partial installation update with {status=} and {status_details=}"
    )
    update_request = PartialUpdateInstallationRequest(
        tenant_id=tenant_id,
        installation_id=installation_id,
        vendor=AWS,
        status=status,
        status_details=status_details,
    )
    logger.info(f"Sending partial installation update: {update_request}")
    events_client = EventsClient()
    events_client.put_event(
        source=EXECUTION_EVENT_SOURCE,
        bus_name=INSTALLATION_PARTIAL_UPDATE_EVENT_BUS,
        detail_type=INSTALLATION_PARTIAL_UPDATE_EVENT_DETAIL_TYPE,
        detail=update_request.json(exclude_none=True, exclude_unset=True),
    )
    return update_request


def update_asset_status(tenant_id: str, asset_id: str, status: AssetStatus, status_details: Optional[str] = None):
    api_token = AuthenticationService().get_api_token(tenant_id)
    asset_service = AssetService()
    update_asset_request = UpdateAssetRequest(status=status)
    if status_details:
        update_asset_request.status_details = status_details
    asset_service.update_asset(tenant_id, asset_id, update_asset_request, api_token)


def assume_role(
        tenant_id: str,
        installation_id: str,
        asset_id: str,
        assume_role_id: str,
        external_id: Optional[str] = None,
        aws_jit_role_name: Optional[str] = None,
) -> Dict:
    aws_settings = get_aws_config()
    sts_client = boto3.client(AWS_COMMON_STS_CLIENT_NAME, **aws_settings)

    external_id = external_id or _calculate_external_id(
        tenant_id=tenant_id, installation_id=installation_id
    )
    aws_jit_role_name = aws_jit_role_name or AWS_JIT_ROLE

    logger.info(f"Assuming role {aws_jit_role_name} with {external_id=}")
    try:
        assumed_role = sts_client.assume_role(
            RoleArn=f"arn:aws:iam::{assume_role_id}:role/{aws_jit_role_name}",
            RoleSessionName=aws_jit_role_name,
            ExternalId=external_id,
            DurationSeconds=AWS_COMMON_SESSION_SECONDS_DURATION,
        )
        aws_config = {
            **get_aws_credentials(assumed_role),
            AWS_COMMON_REGION_NAME_KEY: aws_settings[AWS_COMMON_REGION_NAME_KEY],
        }
        logger.info(f"Successfully assumed role {aws_jit_role_name} with {external_id=}")

        if os.getenv(IS_SILENT_INVOCATION_ENV_VAR) == "true":
            logger.info('Skipping asset status update for silent invocation')
            return aws_config

        logger.info("Updating asset status to CONNECTED")
        update_asset_status(tenant_id, asset_id, AssetStatus.CONNECTED)
        logger.info("Asset status updated to CONNECTED")
        return aws_config
    except Exception as e:
        logger.error(f"Error while assuming role: {e}")
        send_installation_partial_update_event_error(
            tenant_id=tenant_id,
            installation_id=installation_id,
            external_id=external_id,
        )
        logger.info("Updating asset status to FAILED")
        update_asset_status(tenant_id, asset_id, AssetStatus.FAILED, FAILED_TO_ASSUME_ROLE_ASSET_STATUS_DETAILS)
        logger.info("Asset status updated to FAILED")
        add_label("ERROR_FAILED_TO_ASSUME_ROLE", "true")
        raise AwsAssumeRoleError from e


def send_container_task_finish_event(ecs_data: ECSTaskData, price: float):
    request = {
        "metadata": {
            "tenant_id": ecs_data.tenant_id,
            "event_id": ecs_data.jit_event_id,
            "execution_id": ecs_data.execution_id,
            "container_image": ecs_data.container_image,
            "image_digest": ecs_data.image_digest,
        },
        "data": ecs_data.dict(
            exclude={"task_data", "region", "container_image", "image_digest", "tenant_id", "jit_event_id",
                     "execution_id"}
        ),
    }

    request["data"]["price_dollars"] = price
    logger.info(f"Sending completion event for execution {request}")
    events_client = EventsClient()
    events_client.put_event(
        source=EXECUTION_EVENT_SOURCE,
        bus_name=EXECUTION_EVENT_BUS_NAME,
        detail_type=EXECUTION_FARGATE_TASK_FINISHED,
        detail=json.dumps(request, default=pydantic_encoder),
    )


def get_task_definition(task_arn: str) -> Dict:
    aws_config = get_aws_config()
    ecs_client = boto3.client("ecs", **aws_config)
    return ecs_client.describe_task_definition(taskDefinition=task_arn)


@cachetools.func.ttl_cache(maxsize=1, ttl=60 * 60 * 24)
def get_prices() -> Dict:
    aws_config = get_aws_config()
    pricing_client = boto3.client("pricing", **aws_config)
    region = os.getenv(REGION_NAME, None)
    if not region:
        raise Exception(f"{REGION_NAME} environment variable is not set")
    return pricing_client.get_products(
        ServiceCode="AmazonECS",
        Filters=[
            {"Type": "TERM_MATCH", "Field": "regionCode", "Value": region},
            {"Type": "TERM_MATCH", "Field": "productFamily", "Value": "compute"},
        ],
    )


def run_fargate_task(job_name: str, job_definition: str, env: Dict[str, str], command: List[str]) -> str:
    """
    This function submits a fargate job to AWS Batch service, in order to execute the workflow job
    :param job_name: the name of the job in AWS batch (up to 128 characters)
    :param job_definition: representing the Fargate Batch job definition to be executed, if not exists raising exception
    :param env: environment variables to be injected  into the executed container
    :param command: command args to pass to the container
    """
    logger.info(f"Running fargate batch job {job_definition=}")
    aws_settings = get_aws_config()
    batch_client: BatchClient = boto3.client(AWS_COMMON_BATCH_CLIENT_NAME, **aws_settings)
    client_exceptions = batch_client.exceptions

    logger.info(f"Running fargate batch job {job_name=}")
    try:
        container_overrides = ContainerOverridesTypeDef(
            environment=[
                KeyValuePairTypeDef(name=env_var_name, value=env_var_value)
                for env_var_name, env_var_value in env.items()
            ]
        )
        if command:
            container_overrides['command'] = command

        params = dict(
            jobName=job_name,
            jobDefinition=job_definition,
            jobQueue=FARGATE_TASKS_BATCH_QUEUE_NAME,
            containerOverrides=container_overrides,
            timeout={"attemptDurationSeconds": FARGATE_BATCH_JOB_TIMEOUT},
        )

        logger.info(f"Submitting job {params=}")
        response = batch_client.submit_job(**params)
        logger.info(f"Successfully submitted job={job_name}. Response of aws batch client: {response}")
    except (
            client_exceptions.ClientError,
            client_exceptions.ClientException,
            client_exceptions.ServerException,
    ) as e:
        logger.error(f"Failed sending fargate job ({job_name=}) to queue with response={e.response}")
        raise Exception(
            f"Failed sending fargate jobs to queue with response={e.response}"
        )

    return response[
        "jobId"
    ]  # jobId is the identifier we need in order to operate on the job we just submitted


def get_job_definition(image_ecr_path: str) -> str:
    """
    This function will get an image definition in ecr and should return the value of the corresponding job definition
    Example:
        image=121169888995.dkr.ecr.us-east-1.amazonaws.com/github-branch-protection:main
        return value: github-branch-protection__main
    """
    logger.info(f"Getting job definition for image {image_ecr_path=}")

    ecr_and_image_name = image_ecr_path.rsplit("/", 1)
    if len(ecr_and_image_name) < 2:
        raise AwsLogicError(f"Illegal image ecr path {image_ecr_path}, no ECR ARN")

    image_name_part = ecr_and_image_name[1]
    image_and_tag = image_name_part.split(":")
    if len(image_and_tag) < 2:
        raise AwsLogicError(f"Illegal image ecr path {image_ecr_path}, no tag")

    job_definition = "__".join(image_and_tag)
    logger.info(f"Got job definition {job_definition=}")
    return job_definition

import base64
import json

from typing import Dict, List

from jit_utils.logger import logger
from google.auth.exceptions import MalformedError, MutualTLSChannelError
from google.cloud import batch_v1, kms_v1, logging_v2
from google.oauth2 import service_account

from src.lib.constants import (
    GCP_PROJECT_ID,
    GCP_REGION,
    GCP_BATCH_JOB_SERVICE_ACCOUNT_EMAIL,
    GCP_BATCH_VPC_SUBNETWORK_NAME,
    GCP_BATCH_VPC_NETWORK_NAME,
)

CLIENT_INIT_ERRORS = (MutualTLSChannelError, ValueError)


class GcpLogicError(Exception):
    pass


def get_gcp_image_uri(image_ecr_path: str) -> str:
    """
    This function will get an image definition in ecr and should return the value of the corresponding gcr image uri
    Example:
        image=121169888995.dkr.ecr.us-east-1.amazonaws.com/github-branch-protection:main
        return value: us-central1-docker.pkg.dev/github-branch-protection/github-branch-protection:main
    """
    logger.info(f"Getting gcr image uri for image {image_ecr_path=}")

    ecr_and_image_name = image_ecr_path.rsplit("/", 1)
    if len(ecr_and_image_name) < 2:
        raise GcpLogicError(f"Illegal image ecr path {image_ecr_path}, no ECR ARN")

    image_name_part = ecr_and_image_name[1]
    image_and_tag = image_name_part.split(":")
    if len(image_and_tag) < 2:
        raise GcpLogicError(f"Illegal image ecr path {image_ecr_path}, no tag")

    gcr_image_uri = (
        f"{GCP_REGION}-docker.pkg.dev/{GCP_PROJECT_ID}/{image_and_tag[0]}/{image_and_tag[0]}:{image_and_tag[1]}"
    )

    logger.info(f"Got GCR image uri {gcr_image_uri=}")
    return gcr_image_uri


def get_gcp_credentials(credentials_json_str: str) -> service_account.Credentials:
    try:
        return service_account.Credentials.from_service_account_info(json.loads(credentials_json_str))
    except (json.JSONDecodeError, MalformedError, AttributeError, ValueError) as exc:
        raise GcpLogicError from exc


def encrypt_text(credentials: service_account.Credentials, key_name: str, text: str) -> str:
    try:
        client = kms_v1.KeyManagementServiceClient(credentials=credentials)
    except (MutualTLSChannelError, ValueError) as exc:
        raise GcpLogicError from exc
    try:
        response = client.encrypt(request={"name": key_name, "plaintext": base64.b64encode(text.encode())})
        return base64.b64encode(response.ciphertext).decode('utf-8')
    except Exception as exc:
        raise GcpLogicError from exc


def run_batch_job(
        credentials: service_account.Credentials,
        job_name: str,
        max_run_time: int,
        image_uri: str,
        env: Dict[str, str],
        command: List[str],
        high_specs: bool,
) -> str:
    """
    This function creates a batch job to GCP Batch service, in order to execute the workflow job
    :param credentials: GCP credentials to use
    :param job_name: the name of the job in GCP batch (up to 63 characters)
    :param max_run_time: maximum run time for GCP batch job
    :param image_uri: representing the image uri of the control
    :param env: environment variables to be injected  into the executed container
    :param command: command args to pass to the container
    :param high_specs: whether to set up high machine specifications
    :return:
        A str representation of the job's name.
        We should use that value as the run_id of the execution.
        We can use that value to perform batch_v1 operations (e.g. get/delete etc.).
    :raise GcpLogicError:
    """
    try:
        client = batch_v1.BatchServiceClient(credentials=credentials)
    except CLIENT_INIT_ERRORS as exc:
        raise GcpLogicError from exc

    try:
        create_request = _create_job_creation_request(image_uri, job_name, env, command, high_specs, max_run_time)
        created_job = client.create_job(create_request)
    except Exception as exc:
        raise GcpLogicError from exc
    else:
        # This is actually the job path, e.g. projects/123456789/locations/us-central1/jobs/123456789
        run_id = created_job.name
        logger.info(f"Successfully created job in GCP batch - {run_id=}")
        return run_id


def _create_job_creation_request(
        image_uri: str, job_name: str, env: Dict[str, str], command: List[str], high_specs: bool, max_run_time: int
) -> batch_v1.CreateJobRequest:
    HIGH_SPEC_CPU_MILLIS = 2000  # in milliseconds per cpu-second. This means the task requires 2 whole CPUs.
    LOW_SPEC_CPU_MILLIS = 1000  # in milliseconds per cpu-second. This means the task requires 1 whole CPUs.
    HIGH_SPEC_MEMORY_MIB = 4096
    LOW_SPEC_MEMORY_MIB = 512

    # Define what will be done as part of the job.
    runnable = batch_v1.Runnable()
    runnable.container = batch_v1.Runnable.Container()
    runnable.container.image_uri = image_uri
    if env:
        runnable.environment.variables = env
    if command:
        runnable.container.commands = command
    # Jobs can be divided into tasks. In this case, we have only one task.
    task = batch_v1.TaskSpec()
    task.runnables = [runnable]
    # We can specify what resources are requested by each task.
    resources = batch_v1.ComputeResource()
    if high_specs:
        resources.cpu_milli = HIGH_SPEC_CPU_MILLIS
        resources.memory_mib = HIGH_SPEC_MEMORY_MIB
    else:
        resources.cpu_milli = LOW_SPEC_CPU_MILLIS
        resources.memory_mib = LOW_SPEC_MEMORY_MIB
    task.compute_resource = resources
    # no retry when control failed (makes the batch not to retry when control exit with non-zero status code)
    task.max_retry_count = 0
    task.max_run_duration = f"{max_run_time}s"
    # Tasks are grouped inside a job using TaskGroups.
    # Currently, it's possible to have only one task group.
    group = batch_v1.TaskGroup()
    group.task_count = 1
    group.task_spec = task
    # Policies are used to define on what kind of virtual machines the tasks will run on.
    # In this case, we tell the system to use "e2-standard-4" machine type.
    # Read more about machine types here: https://cloud.google.com/compute/docs/machine-types
    policy = batch_v1.AllocationPolicy.InstancePolicy()
    instances = batch_v1.AllocationPolicy.InstancePolicyOrTemplate()
    instances.policy = policy
    allocation_policy = batch_v1.AllocationPolicy()
    allocation_policy.instances = [instances]
    network = batch_v1.AllocationPolicy.NetworkInterface()
    network.network = f"projects/{GCP_PROJECT_ID}/global/networks/{GCP_BATCH_VPC_NETWORK_NAME}"
    network.subnetwork = f"projects/{GCP_PROJECT_ID}/regions/{GCP_REGION}/subnetworks/{GCP_BATCH_VPC_SUBNETWORK_NAME}"
    network.no_external_ip_address = True
    allocation_policy.network.network_interfaces = [network]
    service_account = batch_v1.ServiceAccount()
    service_account.email = GCP_BATCH_JOB_SERVICE_ACCOUNT_EMAIL
    allocation_policy.service_account = service_account
    job = batch_v1.Job()
    job.task_groups = [group]
    job.allocation_policy = allocation_policy
    # We use Cloud Logging as it's an out of the box available option
    job.logs_policy = batch_v1.LogsPolicy()
    job.logs_policy.destination = batch_v1.LogsPolicy.Destination.CLOUD_LOGGING
    create_request = batch_v1.CreateJobRequest()
    create_request.job = job
    create_request.job_id = job_name
    # The job's parent is the region in which the job will run
    create_request.parent = f"projects/{GCP_PROJECT_ID}/locations/{GCP_REGION}"
    return create_request


def get_gcp_job_execution_logs(credentials: service_account.Credentials, job_path: str) -> str:
    """
    This function returns the logs of a GCP batch job.
    Args:
        credentials: the credentials to use to authenticate with GCP.
        job_path: the path to the job to delete. e.g. projects/123456789/locations/us-central1/jobs/123456789
                  This is also the execution's run_id.
    """
    logger.info(f"Getting logs for job {job_path=}")
    log_client = logging_v2.Client(credentials=credentials, project=GCP_PROJECT_ID)
    job_logger = log_client.logger("batch_task_logs")

    try:
        client = batch_v1.BatchServiceClient(credentials=credentials)
    except CLIENT_INIT_ERRORS as exc:
        raise GcpLogicError from exc
    logger.info("Successfully created GCP batch client")

    logger.info("Getting job")
    job = client.get_job(name=job_path)
    logger.info("Successfully got job")

    log_entries = job_logger.list_entries(filter_=f'labels.job_uid="{job.uid}"')
    logger.info("Successfully got log entries")
    formatted_log_entries = [_format_log_entry(entry) for entry in log_entries]
    logger.info(f"Successfully formatted {len(formatted_log_entries)} log entries")

    return "\n".join(formatted_log_entries)


def _format_log_entry(entry: logging_v2.TextEntry) -> str:
    """
    Formats a single log entry into a human readable string.
    Args:
        entry: the log entry to format.
    Returns:
        A string representing the log entry.
    """
    timestamp = entry.timestamp.isoformat().replace("+00:00", "Z")
    severity = entry.severity
    message = entry.payload
    return f"{timestamp} | {severity} | {message}"


def delete_job(credentials: service_account.Credentials, job_path: str) -> None:
    """
    Deletes a job from GCP batch.
    Docs: https://cloud.google.com/python/docs/reference/batch/latest/google.cloud.batch_v1.services.batch_service.BatchServiceClient#google_cloud_batch_v1_services_batch_service_BatchServiceClient_delete_job  # noqa: E501

    Args:
        credentials: the credentials to use to authenticate with GCP.
        job_path: the path to the job to delete. e.g. projects/123456789/locations/us-central1/jobs/123456789
                  This is also the execution's run_id.

    Returns: None
    """
    try:
        client = batch_v1.BatchServiceClient(credentials=credentials)
    except CLIENT_INIT_ERRORS as exc:
        raise GcpLogicError from exc

    try:
        client.delete_job(name=job_path)
    except Exception as exec:
        raise GcpLogicError from exec

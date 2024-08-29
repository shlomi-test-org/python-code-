import datetime
import json
from functools import lru_cache
from typing import Any, Dict, List, Optional

from jit_utils.aws_clients.s3 import S3Client
from jit_utils.aws_clients.utils.secret_utils import get_secret_value
from jit_utils.jit_clients.asset_service.client import AssetService
from jit_utils.jit_clients.authentication_service.client import AuthenticationService
from jit_utils.jit_clients.plan_service.client import PlanService
from jit_utils.jit_clients.tenant_service.client import TenantService
from jit_utils.logger import logger
from jit_utils.models.asset.entities import Asset, AssetStatus
from jit_utils.models.tenant.entities import Installation
from jit_utils.utils.jit_controls.exceptions import AccountNotFoundError, IntegrationFileError

from src.lib.aws_common import run_fargate_task
from src.lib.constants import (
    SILENT_INVOCATION_UPLOAD_FINDINGS_S3_BUCKET,
    SILENT_INVOCATION_UPLOAD_LOGS_S3_BUCKET,
    SILENT_INVOCATION_UPLOAD_URL_EXPIRATION_SECONDS,
)
from src.lib.cores.fargate.aws_account_core import get_tenant_aws_credentials
from src.lib.cores.fargate.constants import AZURE_CREDENTIALS_SECRET_NAMES, GCP_CREDENTIALS_SECRET_NAME
from src.lib.models.execution_models import SilentInvocationControlConfig, SilentInvocationRequest


def execute_silent_invocation(silent_invocation_request: SilentInvocationRequest) -> List[Dict[str, str]]:
    """
    This function executes the silent invocation for the given request, and returns the job ids.
    The flow is:
    1. get all the assets that are relevant for the given control name
    2. for each asset, prepare the task parameters
    3. run the task
    """
    base_job_name = silent_invocation_request.job_name or f'silent-{silent_invocation_request.control_name}'
    invocation_time = datetime.datetime.utcnow().strftime('%Y-%m-%d-%H-%M-%S')  # Keep same invocation time for all jobs

    tenant_id = silent_invocation_request.tenant_id
    api_token = AuthenticationService().get_api_token(tenant_id=tenant_id)

    assets = _get_assets(
        control_name=silent_invocation_request.control_name,
        asset_types=silent_invocation_request.asset_types,
        tenant_id=tenant_id,
        api_token=api_token
    )
    logger.info(f'Found {len(assets)} assets for control={silent_invocation_request.control_name}'
                f' and asset_types={silent_invocation_request.asset_types}: '
                f'{[asset.asset_name for asset in assets]}')

    jobs: List[Dict] = []
    for asset in assets:
        logger.info(f'Preparing the task for {asset.asset_id=}, {asset.asset_name=}')

        silent_invocation_request.job_name = (
            f'{invocation_time}-{base_job_name}-{asset.asset_name}'
        )

        params = build_run_params(silent_invocation_request=silent_invocation_request, asset=asset, api_token=api_token)

        if silent_invocation_request.is_dry_run:
            logger.info(f'Dry run, not running the task. {asset.asset_id=}, {params=}')
            continue

        logger.info(f'Running the task for {asset.asset_id=}. {params=}')
        job_id = run_fargate_task(**params)
        jobs.append({"job_id": job_id, "job_name": silent_invocation_request.job_name})
        logger.info(f'Task started. {job_id=} job_name={silent_invocation_request.job_name}')
    return jobs


def build_run_params(silent_invocation_request: SilentInvocationRequest,
                     asset: Asset, api_token: str) -> Dict[str, Any]:
    """
    This function prepares the task parameters for the given asset.
    It can also run a dedicated preparation function for a specific control.
    """
    logger.info(f'Building run parameters for {asset.asset_id=}')
    env = silent_invocation_request.env or {}
    command = silent_invocation_request.command or []

    preparation_func = get_config_for_control(silent_invocation_request.control_name).preparation_function
    if preparation_func is not None:
        logger.info(f'Running the preparation function for {silent_invocation_request.control_name=}')
        preparation_func(
            silent_invocation_request=silent_invocation_request,
            asset=asset,
            env=env,
            command=command,
            api_token=api_token
        )

    env['IS_SILENT_INVOCATION'] = 'true'
    env['SILENT_INVOCATION_UPLOAD_FINDINGS_URL'] = generate_upload_url(
        silent_invocation_request=silent_invocation_request,
        bucket_name=SILENT_INVOCATION_UPLOAD_FINDINGS_S3_BUCKET,
        filename_suffix='findings.json',
    )
    env['SILENT_INVOCATION_UPLOAD_LOGS_URL'] = generate_upload_url(
        silent_invocation_request=silent_invocation_request,
        bucket_name=SILENT_INVOCATION_UPLOAD_LOGS_S3_BUCKET,
        filename_suffix='logs.log',
    )

    params = {
        'job_name': silent_invocation_request.job_name,
        'job_definition': silent_invocation_request.job_definition,
        'env': env,
        'command': command,
    }

    return params


@lru_cache()
def get_config_for_control(control_name: str) -> SilentInvocationControlConfig:
    """
    Returns the configuration for the given control name
    """
    controls_config = {
        'prowler': SilentInvocationControlConfig(
            asset_types=['aws_account', 'gcp_account', 'azure_account'],
            preparation_function=prepare_prowler_silent_invocation,
            asset_filtering_function=_filter_prowler_assets,
        ),
    }
    return controls_config[control_name]


def _get_assets(control_name: str, asset_types: Optional[List[str]], tenant_id: str, api_token: str) -> List[Asset]:
    """
    This function returns the assets that are relevant for the given control name
    """
    logger.info(f'Getting assets for {control_name=}, {tenant_id=}')
    all_tenant_assets = AssetService().get_all_assets(tenant_id=tenant_id, api_token=api_token)

    relevant_asset_types = get_config_for_control(control_name).asset_types

    relevant_assets = [
        asset for asset in all_tenant_assets
        if asset.asset_type in relevant_asset_types
        and asset.is_active
        and asset.is_covered
        and (not asset_types or asset.asset_type in asset_types)
    ]
    control_asset_filtering_func = get_config_for_control(control_name).asset_filtering_function
    if control_asset_filtering_func:
        logger.info(f'Running asset filtering function for {control_name=}')
        relevant_assets = control_asset_filtering_func(relevant_assets)

    logger.info(f'Found {len(relevant_assets)} relevant assets: {[asset.asset_name for asset in relevant_assets]}')
    return relevant_assets


@lru_cache()
def get_integration_file_content(tenant_id: str, api_token: str) -> Dict[str, Any]:
    return PlanService().get_integration_file_for_tenant(tenant_id=tenant_id, api_token=api_token)


@lru_cache()
def get_tenant_installations(tenant_id: str, vendor: str, api_token: str) -> List[Installation]:
    return TenantService().get_installations_by_vendor(vendor=vendor, tenant_id=tenant_id, api_token=api_token)


def generate_upload_url(silent_invocation_request: SilentInvocationRequest, bucket_name: str,
                        filename_suffix: str) -> str:
    """
    This function generates an S3 presigned URL that the entrypoint will use to upload the findings/logs to S3
    """
    logger.info(f'Generating upload url for {silent_invocation_request=}, {bucket_name=}, {filename_suffix=}')
    tenant_id = silent_invocation_request.tenant_id
    job_definition = silent_invocation_request.job_definition
    job_name = silent_invocation_request.job_name

    s3_client = S3Client()
    return s3_client.generate_put_presigned_url(
        bucket_name=bucket_name,
        key=f'{tenant_id}/{job_definition}/{job_name}-{filename_suffix}',
        expiration_seconds=SILENT_INVOCATION_UPLOAD_URL_EXPIRATION_SECONDS,
    )


def _filter_prowler_assets(assets: List[Asset]) -> List[Asset]:
    return [
        asset for asset in assets
        if asset.status == AssetStatus.CONNECTED or asset.asset_type in ['gcp_account', 'azure_account']
    ]


def prepare_prowler_silent_invocation(
        silent_invocation_request: SilentInvocationRequest, asset: Asset,
        env: Dict[str, str], command: List[str], api_token: str) -> None:
    """
    Prepares the environment variables for Prowler silent invocation
    """

    env['LOCAL_TEST_VALUE'] = json.dumps({'control-output-standardization': True})

    tenant_id = silent_invocation_request.tenant_id
    integration_file_content = get_integration_file_content(tenant_id, api_token)

    if asset.asset_type == 'aws_account':
        aws_env_params = _get_aws_env_params(tenant_id, asset, integration_file_content, api_token)
        env.update(aws_env_params)
    elif asset.asset_type == 'gcp_account':
        gcp_env_params = _get_gcp_env_params(tenant_id)
        env.update(gcp_env_params)
    elif asset.asset_type == 'azure_account':
        azure_env_params = _get_azure_env_params(tenant_id, asset)
        env.update(azure_env_params)
    else:
        raise ValueError(f'Asset type {asset.asset_type} is not supported')


def _get_aws_env_params(tenant_id: str, asset: Asset, integration_file_content: Dict[str, Any],
                        api_token: str) -> Dict[str, str]:
    """
    Returns the environment parameters for silent invocation on AWS assets.
    It gets the AWS credentials from the tenant's installation, and the regions from the integration file.
    """
    logger.info(f'Handling AWS integration for {asset.asset_id=}')

    account_id = asset.owner

    logger.info(f'Getting installation id for {asset.asset_id=}')
    installations = get_tenant_installations(tenant_id=tenant_id, vendor='aws', api_token=api_token)
    installation_id = next(
        (installation.installation_id for installation in installations
         if installation.is_active and installation.owner == asset.owner),
        None,
    )
    logger.info(f'{installation_id=}')

    logger.info(f'Getting AWS credentials for {asset.asset_id=}')
    aws_credentials = get_tenant_aws_credentials(
        tenant_id=tenant_id,
        installation_id=installation_id,
        asset_id=asset.asset_id,
        assume_role_id=asset.aws_account_id or installation_id,
        aws_external_id=asset.aws_jit_role_external_id,
        aws_jit_role_name=asset.aws_jit_role_name,
    )

    aws_env_params = {
        'AWS_ACCOUNT_ID': account_id,
        'AWS_ACCESS_KEY_ID': aws_credentials['aws_access_key_id'],
        'AWS_SECRET_ACCESS_KEY': aws_credentials['aws_secret_access_key'],
        'AWS_SESSION_TOKEN': aws_credentials['aws_session_token'],
    }

    # Get regions
    logger.info(f'Getting regions for {asset.asset_id=}')
    aws_sections = integration_file_content.get('aws', [])
    for aws_account in aws_sections:
        if aws_account['account_id'] == account_id:
            if 'regions' not in aws_account:
                raise IntegrationFileError(f'No regions found for {account_id} in integration file')
            regions: List[str] = aws_account['regions']
            aws_env_params['AWS_REGIONS'] = ','.join(regions)
            break
    else:
        raise AccountNotFoundError(f'No account {account_id=} found in integration file')

    return aws_env_params


def _get_gcp_env_params(tenant_id: str) -> Dict[str, str]:
    """
    Returns the environment parameters for silent invocation on GCP assets.
    """
    logger.info(f'Handling GCP integration for {tenant_id=}')

    gcp_credentials = get_secret_value(tenant_id=tenant_id, secret_name=GCP_CREDENTIALS_SECRET_NAME)

    gcp_env_params = {
        'GCP_CREDENTIALS': gcp_credentials,
    }

    return gcp_env_params


def _get_azure_env_params(tenant_id: str, asset: Asset) -> Dict[str, str]:
    """
    Returns the environment parameters for silent invocation on Azure assets.
    """
    logger.info(f'Handling Azure integration for {tenant_id=}')

    azure_env_params = {}
    for secret_name in AZURE_CREDENTIALS_SECRET_NAMES:
        secret_value = get_secret_value(tenant_id=tenant_id, secret_name=secret_name)
        azure_env_params[secret_name.upper()] = secret_value

    azure_env_params['AZURE_TENANT_ID'] = asset.account_id

    return azure_env_params

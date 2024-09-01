import os
from typing import Union, Optional, List

from jit_utils.aws_clients.s3 import S3Client
from jit_utils.event_models.third_party.github import WebhookPullRequestEventBody, WebhookEventBodyTypes
from jit_utils.jit_clients.asset_service.client import AssetService
from jit_utils.jit_clients.asset_service.exceptions import AssetNotFoundException
from jit_utils.jit_clients.team_service.client import TeamService
from jit_utils.jit_clients.team_service.exceptions import TeamServiceApiException
from jit_utils.jit_clients.tenant_service.client import TenantService
from jit_utils.jit_clients.tenant_service.exceptions import TenantServiceApiException
from jit_utils.logger import logger
from jit_utils.models.asset.entities import Asset
from jit_utils.models.common.responses import PaginatedResponse
from jit_utils.models.teams.entities import FilterTeamBy, TeamWithMetadata, TeamResponse
from jit_utils.models.teams.requests import GetTeamsRequestParams
from jit_utils.models.tenant.entities import Installation, TenantPreferencesTypes

from src.lib.constants import REPO
from src.lib.feature_flags import get_is_allow_controlled_pr_checks_ff


def _is_pr_checks_enabled_for_tenant(api_token: str, tenant_id: str) -> Optional[bool]:
    logger.info(f'Checking if PR scans enabled for tenant: {tenant_id}.')

    try:
        tenant_preferences = TenantService().get_preference(TenantPreferencesTypes.pr_check.name, api_token).dict()
    except TenantServiceApiException as e:
        logger.error(f'Failed to get tenant preferences. {e}')
        return None

    if (is_enabled := tenant_preferences.get("is_enabled")) is not None:
        logger.info(f'PR scans enabled={is_enabled} for this tenant.')
        return is_enabled

    logger.info('PR scans enable not configured for this tenant.')

    return None


def _has_team_with_enabled_pr_check(
        fetched_teams: Union[PaginatedResponse[TeamResponse], PaginatedResponse[TeamWithMetadata]],
        asset_teams: List[str]
) -> Optional[bool]:
    for team in fetched_teams.data:
        if team.name in asset_teams and team.is_pr_check_enabled:
            logger.info(f'PR scans enabled for {team=}.')
            return True
    return None


def _is_pr_checks_enabled_for_team(api_token: str, teams: List[str]) -> Optional[bool]:
    logger.info(f'Checking if PR scans enabled for related team. Check {len(teams)} teams')

    teams_client = TeamService()
    teams_query_params = GetTeamsRequestParams(search_key=FilterTeamBy.IS_PR_CHECK_ENABLED, search_value=True)

    should_fetch = True
    while should_fetch:
        try:
            fetched_teams = teams_client.get_teams(api_token, teams_query_params)
            if is_enabled := _has_team_with_enabled_pr_check(fetched_teams, teams):
                return is_enabled

            teams_query_params.after = fetched_teams.metadata.after
            should_fetch = bool(fetched_teams.metadata.after)
        except TeamServiceApiException as e:
            logger.error(f'Failed to get teams. {e}')
            return None

    logger.info('PR scans not enabled for any related team.')
    return None


def _is_pr_checks_enabled_for_asset(api_token: str, asset: Asset) -> bool:
    logger.info(f'Checking if PR scans enabled for asset: asset id: {asset.asset_id}.')

    if (is_enabled := _is_pr_checks_enabled_for_tenant(api_token, asset.tenant_id)) is not None:
        return is_enabled

    if is_enabled := _is_pr_checks_enabled_for_team(api_token, asset.teams):
        return is_enabled

    if is_enabled := asset.is_pr_check_enabled:
        logger.info(f'PR scans enabled for asset: asset id: {asset.asset_id}, asset name: {asset.asset_name}.')
        return is_enabled

    logger.info('PR scans are not enabled for the asset.')

    return False


def should_scan_asset(api_token: str,
                      asset: Asset,
                      tenant_id: str,
                      event_body: WebhookEventBodyTypes,
                      ) -> bool:
    if isinstance(event_body, WebhookPullRequestEventBody):
        is_allow_control_pr_checks_ff_enabled = get_is_allow_controlled_pr_checks_ff(tenant_id)
        logger.info(f'{is_allow_control_pr_checks_ff_enabled=}')

        if is_allow_control_pr_checks_ff_enabled:
            return _is_pr_checks_enabled_for_asset(api_token, asset)

    return True


def get_repo_asset_id_from_webhook_event(
        api_token: str,
        event_body: WebhookEventBodyTypes,
        installation: Installation
) -> Optional[str]:
    asset_service = AssetService()
    asset_name = event_body.repository.name
    try:

        asset = asset_service.get_asset_by_attributes(
            installation.tenant_id,
            REPO,
            installation.vendor,
            installation.owner,
            asset_name,
            api_token
        )
    except AssetNotFoundException:
        # Temporary solution for OVO: Put the asset_id in S3 bucket and append it to an object:
        if installation.tenant_id == "fd43ebc1-f4eb-40e6-aace-7dc158207e0a":
            s3_client = S3Client()
            s3_client.put_object(
                bucket_name=f"ovo-missing-assets-{os.getenv('ENV_NAME')}",
                key=f'fd43ebc1-f4eb-40e6-aace-7dc158207e0a/inactive-assets/{asset_name}',
                body=""
            )

        logger.warning(f"Asset not found(inactive/not exist) for {installation.tenant_id=}, {asset_name=}. Skipping.")
        return None

    should_scan = should_scan_asset(api_token, asset, installation.tenant_id, event_body)

    if not should_scan:
        logger.info(f'PR scans are not enabled for this asset. Skipping asset for tenant_id={installation.tenant_id}, '
                    f'{asset.asset_id=}.')
        return None

    if not asset.is_covered:
        logger.info(f'Asset is not covered, Skipping asset for '
                    f'tenant_id={installation.tenant_id}, {asset.asset_id=}')

        if installation.tenant_id == "fd43ebc1-f4eb-40e6-aace-7dc158207e0a":
            s3_client = S3Client()
            s3_client.put_object(
                bucket_name=f"ovo-missing-assets-{os.getenv('ENV_NAME')}",
                key=f'fd43ebc1-f4eb-40e6-aace-7dc158207e0a/not-covered/{asset_name}-{asset.asset_id}',
                body=""
            )

        return None

    logger.info(f'got Asset {asset_name=}, {asset.asset_id=}, for tenant_id={installation.tenant_id}')
    return asset.asset_id

from typing import Optional, Dict, Any
from uuid import uuid4

from jit_utils.event_models import JitEventName
from jit_utils.event_models.deployments.jit_deployment import DeploymentAction, DeploymentSender
from jit_utils.event_models.third_party.github import WebhookDeploymentEventBody, DeploymentJitEvent
from jit_utils.models.tenant.entities import Installation, TenantPreferences
from jit_utils.event_models.deployments import jit_deployment_type
from jit_utils.logger import logger

from src.lib.clients import AuthenticationService
from jit_utils.jit_clients.tenant_service.client import TenantService
from src.lib.cores.event_translation.utils import get_repo_asset_id_from_webhook_event
from jit_utils.jit_clients.tenant_service.exceptions import TenantServiceApiException


def get_jit_event_name_from_deployment_event(**kwargs: Any) -> JitEventName:
    # TODO: Currently there is no way to determine the deployment type from the webhook event.
    return JitEventName.NonProductionDeployment


def create_deployment_jit_execution_event(
        installation: Installation,
        event_body: WebhookDeploymentEventBody,
        **kwargs: Dict
) -> Optional[DeploymentJitEvent]:
    api_token = AuthenticationService().get_api_token(installation.tenant_id)
    asset_id = get_repo_asset_id_from_webhook_event(api_token, event_body, installation)
    if not asset_id:
        logger.warning(f"Unable to determine asset id for {installation.owner}/{event_body.repository.name}")
        return None
    tenant_preferences = get_tenant_preferences(installation.tenant_id, api_token)
    if tenant_preferences and event_body.deployment.environment not in tenant_preferences.deployment.environments:
        logger.info(f'Received a webhook event for deployment in env={event_body.deployment.environment} '
                    f'that is not in the config envs={tenant_preferences.deployment}. '
                    f'Execution events will not be triggerred.')
        return None

    # TODO: change this once we have support for other environments
    deployment_type = jit_deployment_type.JitDeploymentType.NON_PRODUCTION
    jit_event_name = get_jit_event_name_from_deployment_event()

    jit_event = DeploymentJitEvent(
        tenant_id=installation.tenant_id,
        jit_event_id=str(uuid4()),
        asset_id=asset_id,
        app_id=installation.app_id,
        installation_id=installation.installation_id,
        deployment_id=str(event_body.deployment.id),
        environment=event_body.deployment.environment,
        owner=event_body.repository.owner.login,
        vendor=installation.vendor,
        sender=DeploymentSender(
            id=str(event_body.sender.id),
            login=event_body.sender.login,
            avatar_url=event_body.sender.avatar_url
        ),
        user_vendor_id=str(event_body.sender.id),
        user_vendor_name=event_body.sender.login,
        original_repository=event_body.repository.name,
        branch_name=event_body.deployment.ref,
        commit_sha=event_body.deployment.sha,
        created_at=event_body.deployment.created_at,
        deployment_type=deployment_type,
        jit_event_name=jit_event_name,
        deployment_action=event_body.check_run and DeploymentAction(
            name=event_body.check_run.name,
            status=event_body.check_run.status,
            conclusion=event_body.check_run.conclusion,
            started_at=event_body.check_run.started_at,
            completed_at=event_body.check_run.completed_at,
            url=event_body.check_run.html_url
        )
    )

    return jit_event


def get_tenant_preferences(tenant_id: str, api_token: str) -> Optional[TenantPreferences]:
    try:
        preferences = TenantService().get_preferences(tenant_id, api_token)
        return preferences
    except TenantServiceApiException as e:
        logger.warning(f"Unable to get tenant preferences for tenant_id={tenant_id} with error={e}")
        return None

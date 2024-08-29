import uuid
from typing import Dict, Any, Optional

from jit_utils.event_models import JitEventName
from jit_utils.event_models.third_party.github import WebhookPullRequestEventBody, Commits
from jit_utils.event_models.webhooks.pull_request_webhook_event import PullRequestWebhookEvent
from jit_utils.logger import logger
from jit_utils.models.tenant.entities import Installation

from src.lib.clients import AuthenticationService
from src.lib.constants import (
    PULL_REQUEST_OPENED,
    PULL_REQUEST_SYNCHRONIZE,
    PULL_REQUEST_CLOSED,
    HEAD_SHA,
    BASE_SHA,
)
from src.lib.cores.event_translation.utils import get_repo_asset_id_from_webhook_event


def _is_merge_default_branch_event(event_body: WebhookPullRequestEventBody, event_type: str) -> bool:
    if not event_body.pull_request.base:
        logger.info(
            f"Unable to determine if PR to default branch - 'base' attribute does not exist in the event {event_body=}"
        )
        return False

    is_pr_closed_event = event_type == PULL_REQUEST_CLOSED
    is_pr_merged = event_body.pull_request.merged
    is_base_is_default_branch = event_body.repository.default_branch == event_body.pull_request.base.ref

    is_merge_default_branch_event = is_pr_closed_event and is_pr_merged and is_base_is_default_branch

    return is_merge_default_branch_event


def get_jit_event_name_from_pull_request_event(
        event_body: WebhookPullRequestEventBody,
        event_type: str,
) -> Optional[JitEventName]:
    if event_type == PULL_REQUEST_OPENED:
        return JitEventName.PullRequestCreated

    elif event_type == PULL_REQUEST_SYNCHRONIZE:
        return JitEventName.PullRequestUpdated

    elif _is_merge_default_branch_event(event_body=event_body, event_type=event_type):
        return JitEventName.MergeDefaultBranch

    return None


def _build_pr_additional_details(
        installation: Installation,
        event_body: WebhookPullRequestEventBody,
        jit_event_name: JitEventName
) -> Dict[str, Any]:
    original_repo_name = event_body.repository.name
    user_vendor_id = str(event_body.sender.id)
    user_vendor_name = event_body.sender.login
    url = event_body.pull_request.html_url
    created_at = event_body.pull_request.created_at
    updated_at = event_body.pull_request.updated_at
    user_vendor_avatar_url = event_body.sender.avatar_url
    commits_url = event_body.pull_request.commits_url
    pull_request_number = event_body.pull_request.number
    pull_request_title = event_body.pull_request.title
    head_sha = event_body.pull_request.head.sha
    base_sha = event_body.pull_request.base.sha if event_body.pull_request.base else ""
    source_branch = event_body.pull_request.head.ref

    # For merge default branch event, the branch name is the base branch
    if jit_event_name == JitEventName.MergeDefaultBranch:
        branch_name = event_body.pull_request.base and event_body.pull_request.base.ref
    # For other events, the branch name is the head branch
    else:
        branch_name = event_body.pull_request.head.ref

    return dict(
        app_id=installation.app_id,
        installation_id=installation.installation_id,
        original_repository=original_repo_name,
        vendor=installation.vendor,
        owner=installation.owner,
        branch=branch_name,
        pull_request_number=pull_request_number,
        pull_request_title=pull_request_title,
        commits=Commits(**{HEAD_SHA: head_sha, BASE_SHA: base_sha}),
        user_vendor_id=user_vendor_id,
        user_vendor_name=user_vendor_name,
        languages=[],
        url=url,
        created_at=created_at,
        updated_at=updated_at,
        user_vendor_avatar_url=user_vendor_avatar_url,
        commits_url=commits_url,
        source_branch=source_branch,
    )


def create_code_related_jit_execution_event(
        installation: Installation,
        event_body: WebhookPullRequestEventBody,
        jit_event_name: JitEventName,
        **kwargs: Dict
) -> Optional[PullRequestWebhookEvent]:
    api_token = AuthenticationService().get_api_token(installation.tenant_id)
    asset_id = get_repo_asset_id_from_webhook_event(api_token, event_body, installation)
    if not asset_id:
        logger.warning(f"Unable to determine asset id for {installation.owner}/{event_body.repository.name}")
        return None

    if not installation.centralized_repo_asset:
        logger.warning(f'Installation {installation.installation_id} does not have a centralized repo asset')
        return None

    additional_pr_details = _build_pr_additional_details(installation, event_body, jit_event_name)

    jit_event = PullRequestWebhookEvent(
        tenant_id=installation.tenant_id,
        jit_event_name=jit_event_name,
        jit_event_id=str(uuid.uuid4()),
        asset_id=asset_id,
        centralized_repo_asset_id=installation.centralized_repo_asset_id,
        centralized_repo_asset_name=installation.centralized_repo_asset.asset_name,
        **additional_pr_details,
    )

    return jit_event

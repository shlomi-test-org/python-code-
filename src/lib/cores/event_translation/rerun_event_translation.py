import os
import uuid
from typing import Any, Optional, Union, Dict

from aws_lambda_powertools.shared.constants import LAMBDA_FUNCTION_NAME_ENV
from aws_lambda_powertools.utilities.idempotency import idempotent_function, IdempotencyConfig
from aws_lambda_powertools.utilities.idempotency.exceptions import (
    IdempotencyAlreadyInProgressError,
    IdempotencyItemAlreadyExistsError,
    IdempotencyItemNotFoundError,
)
from aws_lambda_powertools.utilities.idempotency.persistence.base import DataRecord
from jit_utils.event_models import JitEventName
from jit_utils.event_models.third_party.github import (
    WebhookRerunEventBody,
    CodeRelatedJitEvent,
    Commits,
    WebhookSingleCheckRerunEventBody,
    CheckSuite,
)
from jit_utils.logger import logger
from jit_utils.models.tenant.entities import Installation
from jit_utils.utils.aws.idempotency import get_persistence_layer

from src.lib.clients import AuthenticationService
from src.lib.constants import HEAD_SHA, BASE_SHA
from src.lib.cores.event_translation.utils import get_repo_asset_id_from_webhook_event


rerun_idempotency_config = IdempotencyConfig(
    raise_on_no_idempotency_key=True,
    expires_after_seconds=30,
)

idempotency_persistence_layer = get_persistence_layer()


def get_jit_event_name_from_rerun_event(**kwargs: Any) -> JitEventName:
    return JitEventName.PullRequestUpdated


@idempotent_function(
    data_keyword_argument="check_suite",
    persistence_store=idempotency_persistence_layer,
    config=rerun_idempotency_config,
)
def _create_code_related_jit_event(
        event_body: Union[WebhookRerunEventBody, WebhookSingleCheckRerunEventBody],
        check_suite: CheckSuite,
        installation: Installation,
) -> Optional[Dict]:
    api_token = AuthenticationService().get_api_token(installation.tenant_id)
    asset_id = get_repo_asset_id_from_webhook_event(api_token, event_body, installation)
    if not asset_id:
        logger.exception(f"Unable to determine asset id for {installation.owner}/{event_body.repository.name}")
        return None

    pull_request_number = str(check_suite.pull_requests[0].number)
    head_sha = check_suite.pull_requests[0].head.sha
    base_sha = check_suite.pull_requests[0].base.sha

    logger.info("Creating the rerun code related jit event")

    return CodeRelatedJitEvent(
        tenant_id=installation.tenant_id,
        jit_event_name=JitEventName.PullRequestUpdated,
        jit_event_id=str(uuid.uuid4()),
        asset_id=asset_id,
        centralized_repo_asset_id=installation.centralized_repo_asset_id,
        centralized_repo_asset_name=installation.centralized_repo_asset.asset_name,  # type: ignore
        app_id=installation.app_id,
        installation_id=installation.installation_id,
        original_repository=event_body.repository.name,
        vendor=installation.vendor,
        owner=installation.owner,
        branch=check_suite.pull_requests[0].head.ref,
        pull_request_number=pull_request_number,
        pull_request_title=f"Rerun PR {pull_request_number}",
        commits=Commits(**{HEAD_SHA: head_sha, BASE_SHA: base_sha}),
        user_vendor_id=str(event_body.sender.id),
        user_vendor_name=event_body.sender.login,
        languages=[],
    ).dict()


def _is_duplicate_rerun_event(check_suite: CheckSuite) -> bool:
    """
    THIS IS A WORKAROUND OVER THE IDEMPOTENCY MECHANISM

    * determine if a successful rerun already handled in the given expiration window
    * why?
        * the idempotency mechanism returns the previous output of the
            _create_code_related_jit_event function (if was handled before)
        * it's not preventing us from handling the "duplicated" rerun event
    * using the idempotency mechanism persistence layer -> checking if a record for the rerun event was already created
    """
    func_full_name = f"{_create_code_related_jit_event.__module__}.{_create_code_related_jit_event.__name__}"
    # We should tell the persistence layer the name of the idempotent function, so it can generate an idempotent key
    idempotency_persistence_layer.function_name = f"{os.getenv(LAMBDA_FUNCTION_NAME_ENV, 'test-func')}.{func_full_name}"
    try:
        item: DataRecord = idempotency_persistence_layer.get_record(data=check_suite.dict())  # type: ignore
    except IdempotencyItemNotFoundError:
        logger.info(f"No idempotency record for the function={func_full_name} - continue")
        return False
    else:
        if item.is_expired:
            logger.info("We have an expired rerun handling - we can handle this rerun")
            return False
        else:
            logger.info(f"We already have handled rerun request for {check_suite=}")
            return True


def create_rerun_single_check_code_related_jit_event(
        installation: Installation,
        event_body: WebhookSingleCheckRerunEventBody,
        jit_event_name: str,
) -> Optional[CodeRelatedJitEvent]:
    logger.info(f"Before creating a jit event for single check rerun with {jit_event_name=}")

    if _is_duplicate_rerun_event(event_body.check_run.check_suite):  # type: ignore
        return None

    try:
        return CodeRelatedJitEvent(
            **_create_code_related_jit_event(
                event_body=event_body,
                check_suite=event_body.check_run.check_suite,  # type: ignore
                installation=installation,
            )
        )
    except (IdempotencyItemAlreadyExistsError, IdempotencyAlreadyInProgressError):
        logger.info(f"We already have rerun in progress for {event_body.check_run.check_suite.id}")  # type: ignore
        return None


def create_rerun_code_related_jit_event(
        installation: Installation,
        event_body: WebhookRerunEventBody,
        jit_event_name: str,
) -> Optional[CodeRelatedJitEvent]:
    logger.info(f"Before creating a jit event for suite rerun with {jit_event_name=}")

    if _is_duplicate_rerun_event(event_body.check_suite):
        return None

    try:
        return CodeRelatedJitEvent(
            **_create_code_related_jit_event(
                event_body=event_body,
                check_suite=event_body.check_suite,
                installation=installation,
            )
        )
    except (IdempotencyItemAlreadyExistsError, IdempotencyAlreadyInProgressError):
        logger.info(f"We already have rerun in progress for {event_body.check_suite.id}")
        return None

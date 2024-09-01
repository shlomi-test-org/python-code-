from uuid import uuid4

from jit_utils.event_models import JitEventName
from jit_utils.event_models.third_party.github import Sender, CodeRelatedJitEvent
from jit_utils.models.tenant.entities import Installation
from test_utils.aws import idempotency

from src.lib.cores.event_translation import rerun_event_translation
from src.lib.cores.event_translation.rerun_event_translation import create_rerun_code_related_jit_event
from tests.common import (
    WebhookRerunEventBodyFactory,
    InstallationFactory,
    CheckSuiteFactory,
    RepositoryFactory,
    AssetFactory,
)


def test_create_rerun_jit_event(mocker):
    idempotency.mock_idempotent_decorator(
        mocker=mocker,
        module_to_reload=rerun_event_translation,
        decorator_name='idempotent_function',
    )

    mock_tenant_id = str(uuid4())
    mocker.patch(
        "src.lib.cores.event_translation.rerun_event_translation.AuthenticationService.get_api_token",
        return_value="api_token",
    )
    mocker.patch(
        "src.lib.cores.event_translation.rerun_event_translation.get_repo_asset_id_from_webhook_event",
        return_value="asset_id",
    )
    mocker.patch(
        "src.lib.cores.event_translation.rerun_event_translation._is_duplicate_rerun_event",
        return_value=False,
    )
    rerun_event_body = WebhookRerunEventBodyFactory.build(
        jit_event_id="jit_event_id",
        vendor="github",
        event_type="pull_request_opened",
        check_suite=CheckSuiteFactory.build(
            head_sha="head_sha",
            pull_requests=[
                {"head": {"ref": "ref", "sha": "head_sha"}, "base": {"ref": "ref", "sha": "base_sha"}, "number": 1}
            ],
        ),
        sender=Sender(id=1, login="login", avatar_url="avatar_url"),
        repository=RepositoryFactory.build(name="name"),
    )
    installation: Installation = InstallationFactory.build(
        tenant_id=mock_tenant_id,
        app_id="app_id",
        installation_id="installation_id",
        vendor="github",
        owner="owner",
        centralized_repo_asset_id="centralized_repo_asset_id",
        centralized_repo_asset=AssetFactory().build(),
    )

    expected_rerun_jit_event = CodeRelatedJitEvent(
        centralized_repo_asset_id=installation.centralized_repo_asset_id,
        centralized_repo_asset_name=installation.centralized_repo_asset.asset_name,
        app_id="app_id",
        asset_id="asset_id",
        base_sha="base_sha",
        branch="ref",
        commits={"base_sha": "base_sha", "head_sha": "head_sha"},
        event_signature="github-owner-asset_id-head_sha-base_sha",
        head_sha="head_sha",
        installation_id="installation_id",
        jit_event_name=JitEventName.PullRequestUpdated,
        pull_request_title="Rerun PR 1",
        original_repository="name",
        owner="owner",
        pull_request_number="1",
        tenant_id="tenant_id",
        user_vendor_id="1",
        user_vendor_name="login",
        vendor="github",
        jit_event_id=str(uuid4()),
    ).dict(exclude={"tenant_id", "jit_event_id"})
    actual_jit_event = create_rerun_code_related_jit_event(
        installation, rerun_event_body, "",
    ).dict(exclude={"tenant_id", "jit_event_id"})
    assert expected_rerun_jit_event == actual_jit_event

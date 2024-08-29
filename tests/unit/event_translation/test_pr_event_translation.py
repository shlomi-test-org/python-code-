from typing import Optional

import pytest
from jit_utils.event_models import JitEventName
from jit_utils.event_models.third_party.github import Commit
from jit_utils.event_models.webhooks.pull_request_webhook_event import PullRequestWebhookEvent
from jit_utils.jit_clients.asset_service.client import AssetService
from pytest_mock import MockerFixture

from src.lib.clients import AuthenticationService
from src.lib.constants import (
    PULL_REQUEST_OPENED,
    PULL_REQUEST_SYNCHRONIZE,
    REPO,
    PULL_REQUEST_CLOSED,
)
from src.lib.cores.event_translation.pr_event_translation import (
    _build_pr_additional_details,
    _is_merge_default_branch_event,
    create_code_related_jit_execution_event,
    get_jit_event_name_from_pull_request_event,
    get_repo_asset_id_from_webhook_event
)
from src.lib.models.asset import Asset
from tests.common import DefaultSetup, AssetFactory


@pytest.mark.parametrize('jit_event_name', [
    JitEventName.PullRequestCreated,
    JitEventName.PullRequestUpdated,
    JitEventName.MergeDefaultBranch,
])
def test_build_pr_additional_details(mocker, jit_event_name):
    setup = DefaultSetup()
    setup.pull_request_event_body.pull_request.head = Commit(sha='random_head_sha', ref='random_head_ref')
    setup.pull_request_event_body.pull_request.base = Commit(sha='random_base_sha', ref='random_base_ref')

    mocker.patch('src.lib.cores.translate_core.get_installation', return_value=setup.installation)

    additional_details = _build_pr_additional_details(
        installation=setup.installation,
        event_body=setup.pull_request_event_body,
        jit_event_name=jit_event_name
    )

    assert additional_details['app_id'] == setup.app_id
    assert additional_details['installation_id'] == setup.installation_id
    assert additional_details['languages'] == []
    assert additional_details['url'] == setup.pull_request_event_body.pull_request.html_url
    assert additional_details['created_at'] == setup.pull_request_event_body.pull_request.created_at
    assert additional_details['updated_at'] == setup.pull_request_event_body.pull_request.updated_at
    assert additional_details['user_vendor_avatar_url'] == setup.pull_request_event_body.sender.avatar_url
    assert additional_details['commits_url'] == setup.pull_request_event_body.pull_request.commits_url
    assert additional_details['pull_request_number'] is not None
    assert additional_details['commits'].head_sha is not None
    assert additional_details['commits'].base_sha != ''
    assert additional_details['commits'].base_sha != ''

    if jit_event_name == JitEventName.MergeDefaultBranch:
        assert additional_details['branch'] == setup.pull_request_event_body.pull_request.base.ref
    else:
        assert additional_details['branch'] == setup.pull_request_event_body.pull_request.head.ref


def test_get_jit_event_name():
    setup = DefaultSetup()
    setup.pull_request_event_body.pull_request.head = Commit(sha='random_head_sha', ref='random_head_ref')
    setup.pull_request_event_body.pull_request.base = Commit(sha='random_base_sha', ref='random_base_ref')

    assert get_jit_event_name_from_pull_request_event(
        event_body=setup.pull_request_event_body,
        event_type=PULL_REQUEST_OPENED
    ) == JitEventName.PullRequestCreated

    assert get_jit_event_name_from_pull_request_event(
        event_body=setup.pull_request_event_body,
        event_type=PULL_REQUEST_SYNCHRONIZE
    ) == JitEventName.PullRequestUpdated

    setup.pull_request_event_body.pull_request.merged = True
    setup.pull_request_event_body.repository.default_branch = 'main'
    setup.pull_request_event_body.pull_request.base.ref = 'main'

    assert get_jit_event_name_from_pull_request_event(
        event_body=setup.pull_request_event_body,
        event_type=PULL_REQUEST_CLOSED
    ) == JitEventName.MergeDefaultBranch


@pytest.mark.parametrize('jit_event, expected_trigger_event_called', [
    (None, False),
    ("RandomEvent", False),
    (JitEventName.PullRequestCreated, True),
    (JitEventName.PullRequestUpdated, True),
    (JitEventName.MergeDefaultBranch, True),
])
def test_create_jit_execution_event(mocker, jit_event, expected_trigger_event_called):
    setup = DefaultSetup()

    mocker.patch(
        'src.lib.cores.event_translation.pr_event_translation._build_pr_additional_details',
        return_value=dict(
            original_repository="original_repo_name",
            vendor=setup.vendor,
            commits=[],
            url=setup.pull_request_event_body.pull_request.url,
            created_at=setup.pull_request_event_body.pull_request.created_at,
            updated_at=setup.pull_request_event_body.pull_request.updated_at,
            user_vendor_avatar_url=setup.pull_request_event_body.sender.avatar_url,
            commits_url=setup.pull_request_event_body.pull_request.commits_url,
            source_branch=setup.pull_request_event_body.pull_request.head.ref,
        )
    )

    api_token = 'random_api_token'
    get_token_mock = mocker.patch.object(
        AuthenticationService,
        'get_api_token',
        return_value=api_token
    )

    get_asset_id_from_webhook_event_mock = mocker.patch(
        'src.lib.cores.event_translation.pr_event_translation.get_repo_asset_id_from_webhook_event',
        return_value=setup.asset_id
    )

    jit_event = create_code_related_jit_execution_event(
        installation=setup.installation,
        event_body=setup.pull_request_event_body,
        jit_event_name=JitEventName.PullRequestCreated
    )

    isinstance(jit_event, PullRequestWebhookEvent)
    assert setup.asset_id == jit_event.asset_id

    assert get_token_mock.call_count == 1
    assert get_asset_id_from_webhook_event_mock.called
    assert get_asset_id_from_webhook_event_mock.call_args.args == (
        api_token,
        setup.pull_request_event_body,
        setup.installation
    )


@pytest.mark.parametrize('asset, should_return_asset_id', [
    (AssetFactory.build(asset_id='123', is_covered=True, is_active=True), True),
    (AssetFactory.build(asset_id='456', is_covered=False, is_active=False), False),
    (AssetFactory.build(asset_id='456', is_covered=False, is_active=True), False),
])
def test_get_asset_id_from_pr_event(mocker: MockerFixture, asset: Optional[Asset], should_return_asset_id: bool):
    setup = DefaultSetup()
    api_token = "some_token"

    get_asset_mock = mocker.patch.object(
        AssetService,
        'get_asset_by_attributes',
        return_value=asset
    )

    # Execute the function
    result = get_repo_asset_id_from_webhook_event(
        api_token=api_token,
        event_body=setup.pull_request_webhook_event.webhook_body_json,
        installation=setup.installation
    )

    assert get_asset_mock.called
    assert get_asset_mock.call_args.args == (
        setup.installation.tenant_id,
        REPO,
        setup.installation.vendor,
        setup.installation.owner,
        setup.pull_request_webhook_event.webhook_body_json.repository.name,
        api_token
    )

    if should_return_asset_id:
        assert result == asset.asset_id
    else:
        assert result is None


@pytest.mark.parametrize('event_type, is_merged, default_branch, base_ref_branch, expected_result', [
    (PULL_REQUEST_OPENED, True, 'main', 'main', False),
    (PULL_REQUEST_SYNCHRONIZE, False, 'main', 'main', False),
    (PULL_REQUEST_CLOSED, True, 'main', 'main', True),
    (PULL_REQUEST_CLOSED, False, 'main', 'main', False),
    (PULL_REQUEST_CLOSED, True, 'main', 'some_branch', False),
])
def test_is_merge_default_branch_event(event_type, is_merged, default_branch, base_ref_branch, expected_result):
    # Setup
    setup = DefaultSetup()
    setup.pull_request_event_body.pull_request.merged = is_merged
    setup.pull_request_event_body.repository.default_branch = default_branch
    setup.pull_request_event_body.pull_request.base = Commit(sha='', ref=base_ref_branch)

    # Execute the function
    result = _is_merge_default_branch_event(event_body=setup.pull_request_event_body, event_type=event_type)

    assert result == expected_result

from typing import Dict, Optional
from unittest.mock import MagicMock

import pytest
from jit_utils.event_models import JitEventName
from jit_utils.event_models.third_party.github import (
    DeploymentJitEvent,
    WebhookPullRequestEventBody,
    InstallationId,
    Owner,
    PullRequest,
    Commit,
    Repo,
    Sender,
    Repository,
)
from jit_utils.event_models.webhook import WebhookEvent
from jit_utils.models.tenant.entities import TenantPreferences, PreferencesScope
from pytest_mock import MockFixture

import src
from src.lib.cores.event_translation.common import (
    send_jit_event_from_webhook_event_for_handling,
    _extract_installation_id_from_event,
)
from src.lib.cores.event_translation.deployment_event_translation import create_deployment_jit_execution_event
from src.lib.cores.translate_core import dispatch_jit_event_from_raw_event
from tests.common import CodeRelatedJitEventFactory, WebhookDeploymentEventBodyFactory, DefaultSetup, DeploymentFactory


def test_handle_trigger_execution(mocker):
    setup = DefaultSetup()

    raw_event = {'detail': {}}
    translate_event_to_webhook_event_mock = mocker.patch(
        'src.lib.cores.translate_core._translate_event_to_webhook_event', return_value=setup.pull_request_webhook_event
    )
    get_installation_mock = mocker.patch(
        'src.lib.cores.translate_core.get_installation', return_value=setup.installation
    )

    trigger_execution_mock = mocker.patch('src.lib.cores.translate_core.send_jit_event_from_webhook_event_for_handling')

    # Execute the function

    dispatch_jit_event_from_raw_event(raw_event)

    # Assertions
    assert translate_event_to_webhook_event_mock.called
    assert translate_event_to_webhook_event_mock.call_args.args == (raw_event,)

    assert get_installation_mock.called
    assert get_installation_mock.call_args.args == (setup.pull_request_webhook_event,)

    assert trigger_execution_mock.called

    assert trigger_execution_mock.call_args.args == (
        setup.installation, setup.pull_request_webhook_event.webhook_body_json, setup.jit_event_name
    )


def test_trigger_execution(mocker):
    setup = DefaultSetup()
    jit_event = CodeRelatedJitEventFactory.build(
        jit_event_name=JitEventName.PullRequestCreated,
        tenant_id=setup.tenant_id
    )

    create_jit_execution_event_mock = MagicMock()
    create_jit_execution_event_mock.return_value = jit_event

    mocker.patch(
        'src.lib.cores.event_translation.common.EXECUTION_EVENT_CREATORS',
        {WebhookPullRequestEventBody: create_jit_execution_event_mock}
    )
    put_event_mock = mocker.patch("src.lib.cores.event_translation.common.EventBridgeClient.put_event")

    # Execute the function
    send_jit_event_from_webhook_event_for_handling(
        installation=setup.installation,
        jit_event_name=setup.jit_event_name,
        event_body=setup.pull_request_event_body
    )

    # Assertions
    assert create_jit_execution_event_mock.called
    assert create_jit_execution_event_mock.call_args.kwargs == {
        'installation': setup.installation,
        'event_body': setup.pull_request_event_body,
        'jit_event_name': JitEventName.PullRequestCreated,
    }

    assert put_event_mock.called
    assert put_event_mock.call_args.kwargs == {
        'source': "trigger-service",
        'bus_name': 'trigger-execution',
        'detail_type': 'handle-jit-event',
        'detail': jit_event.json()
    }


@pytest.mark.parametrize('config,environment,asset_id,expected_result_event,expected_jit_event_name', [
    ({}, 'staging', 'asset_id', False, None),
    (
            {
                'deployment': {
                    'scope': PreferencesScope.TENANT,
                    'environments': [
                        'staging'
                    ]
                }
            },
            'prod',
            'asset_id',
            False,
            None
    ),
    (
            {
                'deployment': {
                    'scope': PreferencesScope.TENANT,
                    'environments': [
                        'staging'
                    ]
                }
            },
            'staging',
            'asset_id',
            True,
            JitEventName.NonProductionDeployment
    ),
    (
            {
                'deployment': {
                    'scope': PreferencesScope.TENANT,
                    'environments': [
                        'staging', 'prep'
                    ]
                }
            },
            'prep',
            'asset_id',
            True,
            JitEventName.NonProductionDeployment
    ),
    (
            {
                'deployment': {
                    'scope': PreferencesScope.TENANT,
                    'environments': [
                        'staging', 'prep'
                    ]
                }
            },
            'prep',
            None,
            False,
            None
    ),
    (
            {
                'deployment': {
                    'scope': PreferencesScope.TENANT,
                    'environments': [
                        'staging', 'prep'
                    ]
                }
            },
            'prep',
            'asset_id',
            True,
            JitEventName.NonProductionDeployment
    ),
    (
            {
                'deployment': {
                    'scope': PreferencesScope.TENANT,
                    'environments': [
                        'staging', 'prod'
                    ]
                }
            },
            'prod',
            'asset_id',
            True,
            JitEventName.NonProductionDeployment
    ),
])
def test_create_deployment_jit_execution_event(
        mocker: MockFixture,
        config: Dict,
        environment: str,
        asset_id: str,
        expected_result_event: bool,
        expected_jit_event_name: Optional[JitEventName]
):
    setup = DefaultSetup()
    deployment_webhook_event_body = WebhookDeploymentEventBodyFactory.build()
    deployment_webhook_event_body.deployment = DeploymentFactory.build(environment=environment)

    get_token_mock = mocker.patch.object(
        src.lib.cores.event_translation.deployment_event_translation.AuthenticationService,
        'get_api_token',
        return_value='api_token'
    )
    get_asset_id_mock = mocker.patch(
        'src.lib.cores.event_translation.deployment_event_translation.get_repo_asset_id_from_webhook_event',
        return_value=asset_id
    )
    get_preferences_mock = mocker.patch.object(
        src.lib.cores.event_translation.deployment_event_translation.TenantService,
        'get_preferences',
        return_value=TenantPreferences(**config)
    )

    result_event = create_deployment_jit_execution_event(setup.installation, deployment_webhook_event_body)

    assert get_token_mock.called
    assert get_asset_id_mock.called
    assert get_preferences_mock.called if asset_id else not get_preferences_mock.called

    if expected_result_event:
        assert isinstance(result_event, DeploymentJitEvent)
        assert result_event.jit_event_name == expected_jit_event_name
    else:
        assert result_event is None


def test_extract_installation_id_from_event():
    # Define the installation ID
    installation_id = InstallationId(id=123)

    # Create dummy data for the required fields
    repository = Repository(name="Repo1", owner=Owner(login="test_owner"), default_branch="main")
    pull_request = PullRequest(
        number="1",
        head=Commit(sha="sha1", ref="ref1", repo=Repo(name="Repo1", url="https://test.com", id=1)),
        base=Commit(sha="sha2", ref="ref2", repo=Repo(name="Repo2", url="https://test2.com", id=2)),
        merged=True,
        title="test PR",
        created_at="2023-01-01T00:00:00Z",
        updated_at="2023-01-01T01:00:00Z",
        closed_at=None,
        merged_at=None,
        url="https://api.github.com/repos/test_owner/Repo1/pulls/1",
        commits_url="https://test.com",
        html_url="https://github.com/test_owner/Repo1/pulls/1"
    )
    sender = Sender(id=1, login="test_login", avatar_url="https://test.com")

    # Create a webhook event with a pull request event body that contains the installation ID
    webhook_event = WebhookEvent(webhook_body_json=WebhookPullRequestEventBody(
        installation=installation_id, repository=repository, pull_request=pull_request, sender=sender
    ), event_type="pr", vendor="github", app_id=1, dedupe_id=456, webhook_headers={})

    # Call the function to test
    result = _extract_installation_id_from_event(webhook_event)

    # Check the result
    assert result == "123", "The function did not return the correct installation ID"

    # Create a webhook event without a body JSON
    webhook_event = WebhookEvent(
        vendor="test_vendor",
        app_id="test_app",
        event_type="test_event",
        dedupe_id="test_dedupe",
        webhook_headers={"test_header": "test_value"}
    )

    # Call the function to test
    result = _extract_installation_id_from_event(webhook_event)

    # Check the result
    assert result is None, "The function did not return None for a webhook event without a body JSON"

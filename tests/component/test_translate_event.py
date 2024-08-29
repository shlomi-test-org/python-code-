import importlib
import os
from typing import Optional, Generator
from uuid import uuid4

import boto3
import freezegun
import moto
import pytest
from jit_utils.event_models.third_party.github import (
    Sender,
    InstallationId,
    Commit,
    Repo,
    PullRequest,
    Owner,
    Repository,
    WebhookPullRequestEventBody,
    WebhookDeploymentEventBody,
    WebhookRerunEventBody,
    Commits,
    CheckRun,
    WebhookSingleCheckRerunEventBody,
)
from jit_utils.event_models.webhook import WebhookEvent
from jit_utils.models.asset.entities import Asset
from jit_utils.models.teams.entities import FilterTeamBy, SharedBaseTeam
from jit_utils.models.teams.requests import GetTeamsRequestParams
from jit_utils.models.tenant.entities import Tenant, Installation, InstallationStatus, PrCheckPreferences
from moto import mock_s3
from mypy_boto3_dynamodb import DynamoDBServiceResource
from responses import activate
from test_utils.aws import idempotency
from test_utils.aws.mock_eventbridge import mock_eventbridge

from src.handlers import translate_event
from src.handlers.translate_event import handler
from src.lib.constants import TRIGGER_EXECUTION_BUS_NAME, RERUN_PIPELINE, CHECK_RERUN_PIPELINE
from src.lib.cores.event_translation import rerun_event_translation
from tests.common import (
    WebhookRerunEventBodyFactory,
    CheckSuiteFactory,
    RepositoryFactory,
    WebhookSingleCheckRerunEventBodyFactory,
)
from tests.component.utils.mock_responses.mock_asset_service import mock_get_asset_by_attributes_api
from tests.component.utils.mock_responses.mock_authentication_service import mock_get_internal_token_api
from tests.component.utils.mock_responses.mock_team_service import mock_get_teams_api
from tests.component.utils.mock_responses.mock_tenant_service import (
    mock_get_tenant_by_installation_id_api,
    mock_get_pr_check_preference_api,
    mock_get_preferences_api,
)

MOCK_GITHUB_APP = {
    "id": 161076,
    "slug": "jit-ci-bandit",
    "node_id": "A_kwHOBcPimM4AAnU0",
    "owner": {
        "login": "jitsecurity-bandit",
        "id": 96723608,
        "node_id": "O_kgDOBcPimA",
        "avatar_url": "https://avatars.githubusercontent.com/u/96723608?v=4",
        "gravatar_id": "",
        "url": "https://api.github.com/users/jitsecurity-bandit",
        "html_url": "https://github.com/jitsecurity-bandit",
        "followers_url": "https://api.github.com/users/jitsecurity-bandit/followers",
        "following_url": "https://api.github.com/users/jitsecurity-bandit/following{/other_user}",
        "gists_url": "https://api.github.com/users/jitsecurity-bandit/gists{/gist_id}",
        "starred_url": "https://api.github.com/users/jitsecurity-bandit/starred{/owner}{/repo}",
        "subscriptions_url": "https://api.github.com/users/jitsecurity-bandit/subscriptions",
        "organizations_url": "https://api.github.com/users/jitsecurity-bandit/orgs",
        "repos_url": "https://api.github.com/users/jitsecurity-bandit/repos",
        "events_url": "https://api.github.com/users/jitsecurity-bandit/events{/privacy}",
        "received_events_url": "https://api.github.com/users/jitsecurity-bandit/received_events",
        "type": "Organization",
        "site_admin": "False",
    }
}


@pytest.fixture
def mock_dynamodb_fixt(monkeypatch) -> Generator[DynamoDBServiceResource, None, None]:
    monkeypatch.delenv('LOCALSTACK_HOSTNAME', raising=False)

    with moto.mock_dynamodb():
        yield boto3.resource('dynamodb', region_name='us-east-1')


@pytest.fixture
def idempotency_table(monkeypatch, mock_dynamodb_fixt):
    """Setup for the tests in this module."""
    idempotency.create_idempotency_table()
    # Reload the module with the idempotency decorator to initialization under moto context
    importlib.reload(rerun_event_translation)
    importlib.reload(translate_event)  # Reload the core to update the reference to the new declared functions


# Constants
INSTALLATION_ID = 11111111
TENANT_ID = str(uuid4())
ASSET_ID = str(uuid4())
TEAM_NAME = 'team1'

MOCK_PR_WEBHOOK_EVENT = WebhookEvent[WebhookPullRequestEventBody](
    vendor='vendor', app_id='111111', event_type='pull_request_synchronize',
    dedupe_id='dedupe_id', webhook_headers={}, webhook_body_str=None,
    webhook_body_json=WebhookPullRequestEventBody(
        branch='branch',
        repository=Repository(name='repo-name', owner=Owner(login='login'), default_branch='main'),
        pull_request=PullRequest(
            number='38', head=Commit(
                sha='commit-sha', ref='ref',
                repo=Repo(name='name', url='url', id=1111111)
            ),
            base=Commit(
                sha='sha', ref='main',
                repo=Repo(name='name', url='url', id=11111111)
            ),
            merged=False, title='title',
            created_at='created_at', updated_at='updated_at',
            closed_at=None, merged_at=None, url='url', html_url='html_url',
            commits_url='commits_url'
        ),
        installation=InstallationId(id=INSTALLATION_ID),
        sender=Sender(id=11111111, login='login', avatar_url='avatar_url')
    )
)

MOCK_DEPLOYMENT_WEBHOOK_EVENT = WebhookEvent[WebhookDeploymentEventBody](
    vendor='vendor', app_id='111111', event_type='deployment_status_created',
    dedupe_id='dedupe_id', webhook_headers={}, webhook_body_str=None,
    webhook_body_json=WebhookDeploymentEventBody(
        branch='branch',
        deployment_status={'state': 'success'},
        deployment={"id": 1111111,
                    "environment": "environment",
                    "sha": "sha",
                    "ref": "ref",
                    "created_at": "created_at"},
        repository=Repository(name='repo-name', owner=Owner(login='login'), default_branch='main'),
        installation=InstallationId(id=INSTALLATION_ID),
        sender=Sender(id=11111111, login='login', avatar_url='avatar_url'),
        check_run={'id': 1111111, 'name': 'name', 'status': 'completed', 'conclusion': 'success',
                   "html_url": "html_url", "details_url": "details_url"}
    )
)


# Mock setup functions
def setup_mock_tenant(is_asset_enable_pr_checks: Optional[bool] = None, is_asset_active: Optional[bool] = True,
                      is_covered=True, tenant_id: str = TENANT_ID):
    mock_asset = Asset(
        id=ASSET_ID, asset_name='repo-name', asset_type='repo', vendor='vendor',
        owner='owner', tenant_id=tenant_id, created_at='created_at', modified_at='modified_at',
        asset_id='asset_id', vendor_response={'vendor_response': 'vendor_response'},
        is_active=is_asset_active, is_deleted=False, tags=[{"name": "team", "value": TEAM_NAME},
                                                           {"name": "team", "value": 'team2'}],
        is_covered=is_covered,
        is_pr_check_enabled=is_asset_enable_pr_checks
    )

    mock_installation = Installation(
        tenant_id=tenant_id, app_id='app_id', owner='owner', installation_id=INSTALLATION_ID,
        status=InstallationStatus.CONNECTED, is_active=True, creator='creator', vendor='vendor',
        name='name', created_at='created_at', modified_at='modified_at', installation_type='installation_type',
        centralized_repo_asset=mock_asset, vendor_response={'vendor_response': 'vendor_response'}
    )

    mock_tenant = Tenant(
        tenant_id=tenant_id, name='name', owner='owner', status='status', created_at='created_at',
        modified_at='modified_at', vendor='vendor', installations=[mock_installation],
        vendor_response={'vendor_response': 'vendor_response'}
    )

    mock_get_tenant_by_installation_id_api(mock_tenant.dict(),
                                           mock_installation.vendor,
                                           mock_installation.installation_id)
    mock_get_asset_by_attributes_api(mock_asset.dict())
    return mock_tenant, mock_asset


def setup_mock_pr_check_preference(is_pr_enabled: Optional[bool], status_code: Optional[int] = 200):
    mock_pr_check_preference = (PrCheckPreferences(scope='tenant', is_enabled=is_pr_enabled)
                                if is_pr_enabled is not None else PrCheckPreferences(scope='tenant'))
    mock_get_pr_check_preference_api(mock_pr_check_preference.dict(), status_code=status_code)
    return mock_pr_check_preference


def _generate_team_mock(team_name: Optional[str] = None, is_pr_check_enabled: Optional[bool] = None):
    return SharedBaseTeam(
        name=team_name or str(uuid4()),
        tenant_id=TENANT_ID,
        is_pr_check_enabled=is_pr_check_enabled,
        id=str(uuid4()),
        created_at="created_at",
        modified_at="modified_at",
        source="source",
    )


def setup_mock_teams(is_pr_check_enabled: Optional[bool],
                     has_teams: Optional[bool] = True,
                     status_code: Optional[int] = 200):
    mock_team = has_teams and _generate_team_mock(team_name=TEAM_NAME, is_pr_check_enabled=is_pr_check_enabled).dict()
    mock_random_teams = [_generate_team_mock().dict() for _ in range(2)]
    mock_get_teams_api(
        teams=[mock_team, *mock_random_teams] if mock_team else mock_random_teams,
        params=GetTeamsRequestParams(search_key=FilterTeamBy.IS_PR_CHECK_ENABLED.value, search_value=True).dict(),
        status_code=status_code,
    )


def _mock_is_allow_controlled_pr_checks_ff_response(mocker, is_ff_enabled: Optional[bool] = None):
    mocker.patch('src.lib.cores.event_translation.utils.get_is_allow_controlled_pr_checks_ff',
                 return_value=is_ff_enabled)


# Test function
@pytest.mark.parametrize(
    "feature_flag_enabled, tenant_pr_check_enabled, asset_pr_check_enabled, asset_active, mock_teams_status_code, "
    "mock_preferences_status_code, expected_events_count",
    [
        pytest.param(False, False, None, True, 200, 200, 1, id="PR check FF disabled"),
        pytest.param(True, True, None, True, 200, 200, 1, id="Tenant PR check enabled"),
        pytest.param(True, False, None, True, 200, 200, 0, id="Tenant PR check disabled"),
        pytest.param(True, None, True, True, 200, 200, 1, id="Team PR check enabled"),
        pytest.param(True, None, False, True, 200, 200, 0, id="Team PR check disabled"),
        pytest.param(True, None, None, False, 200, 200, 0, id="Inactive asset"),
        pytest.param(True, None, True, False, 200, 200, 0, id="PR check enabled and Inactive asset"),
        pytest.param(True, None, True, True, 200, 200, 1, id="Asset enables PR check"),
        pytest.param(True, None, True, True, 200, 500, 1, id="Failed to get preferences"),
        pytest.param(True, None, True, True, 500, 200, 1, id="Failed to get teams"),
    ],
)
@activate
def test_translate_jit_event(mocker, feature_flag_enabled, tenant_pr_check_enabled,
                             asset_pr_check_enabled, asset_active, mock_teams_status_code, mock_preferences_status_code,
                             expected_events_count):
    """
    Arrange:
        - Mock tenant, asset, preferences and teams
        - Mock is_allow_controlled_pr_checks feature flag response
    Act:
        - Call translate_jit_event
    Assert:
        - Verify that the expected number of events were generated
    """
    # Mock setup
    setup_mock_tenant(is_asset_enable_pr_checks=asset_pr_check_enabled, is_asset_active=asset_active)
    setup_mock_pr_check_preference(is_pr_enabled=tenant_pr_check_enabled, status_code=mock_preferences_status_code)
    mock_get_internal_token_api()
    setup_mock_teams(is_pr_check_enabled=asset_pr_check_enabled, status_code=mock_teams_status_code)
    _mock_is_allow_controlled_pr_checks_ff_response(mocker, is_ff_enabled=feature_flag_enabled)

    # Event processing
    with mock_eventbridge(bus_name=[TRIGGER_EXECUTION_BUS_NAME]) as get_events:
        handler({"detail": MOCK_PR_WEBHOOK_EVENT.__dict__}, {})
        processed_events = get_events[TRIGGER_EXECUTION_BUS_NAME]()

    assert len(processed_events) == expected_events_count


@pytest.fixture
def s3_client():
    with mock_s3():
        yield boto3.client("s3", region_name="us-east-1")


@pytest.mark.parametrize(
    "asset_active, is_covered",
    [
        pytest.param(False, True, id="OVO PR check enabled and Inactive asset"),
        pytest.param(True, False, id="OVO PR check enabled and not covered asset"),
    ]
)
@activate
def test_translate_jit_event_flow_with_ovo_tenant(
    mocker, s3_client, asset_active, is_covered
) -> None:
    # Mock setup
    setup_mock_tenant(is_asset_enable_pr_checks=True,
                      is_asset_active=asset_active,
                      is_covered=is_covered,
                      tenant_id="fd43ebc1-f4eb-40e6-aace-7dc158207e0a")
    setup_mock_pr_check_preference(is_pr_enabled=True, status_code=200)
    mock_get_internal_token_api()
    setup_mock_teams(is_pr_check_enabled=True, status_code=200)
    _mock_is_allow_controlled_pr_checks_ff_response(mocker, is_ff_enabled=True)

    s3_client.create_bucket(Bucket=f"ovo-missing-assets-{os.getenv('ENV_NAME')}")
    with mock_eventbridge(bus_name=[TRIGGER_EXECUTION_BUS_NAME]) as get_events:
        handler({"detail": MOCK_PR_WEBHOOK_EVENT.__dict__}, {})
        processed_events = get_events[TRIGGER_EXECUTION_BUS_NAME]()

    assert len(processed_events) == 0


@pytest.mark.parametrize(
    "is_pr_check_enabled, expected_events_count",
    [
        (True, 1),
        (False, 0),
    ],
)
@activate
def test_translate_jit_event__have_no_teams(mocker, is_pr_check_enabled, expected_events_count):
    """
    Arrange:
        - Mock tenant with an associated inactive asset.
        - Mock preferences, and internal token API.
        - Mock teams API with no teams.
    Act:
        - Call handler
    Assert:
        - Assert that the expected number of events were sent to the trigger execution bus
    """
    # Mock setup
    setup_mock_tenant(is_asset_enable_pr_checks=is_pr_check_enabled)
    setup_mock_pr_check_preference(is_pr_enabled=None)
    mock_get_internal_token_api()
    setup_mock_teams(is_pr_check_enabled=True, has_teams=False)
    _mock_is_allow_controlled_pr_checks_ff_response(mocker, is_ff_enabled=True)

    # Event processing
    with mock_eventbridge(bus_name=[TRIGGER_EXECUTION_BUS_NAME]) as get_events:
        handler({"detail": MOCK_PR_WEBHOOK_EVENT.__dict__}, {})
        processed_events = get_events[TRIGGER_EXECUTION_BUS_NAME]()

    assert len(processed_events) == expected_events_count


@activate
def test_translate_jit_event__deployment_event_not_effected_by_pr_enablement(mocker):
    """
    Arrange:
        - Mock tenant with an associated inactive asset.
        - Mock preferences, and internal token API.
    Act:
        - Trigger the event handler with MOCK_DEPLOYMENT_WEBHOOK_EVENT.
    Assert:
        - Verify that event is processed as the asset pr scans is inactive.

    """
    # Mock setup
    setup_mock_tenant(is_asset_enable_pr_checks=False, is_asset_active=True)
    setup_mock_pr_check_preference(is_pr_enabled=False)
    mock_get_preferences_api({'deployment': {'scope': 'tenant',
                                             'environments': ['environment']}})
    mock_get_internal_token_api()
    _mock_is_allow_controlled_pr_checks_ff_response(mocker, is_ff_enabled=True)

    # Event processing
    with mock_eventbridge(bus_name=[TRIGGER_EXECUTION_BUS_NAME]) as get_events:
        handler({"detail": MOCK_DEPLOYMENT_WEBHOOK_EVENT.__dict__}, {})
        processed_events = get_events[TRIGGER_EXECUTION_BUS_NAME]()

    assert len(processed_events) == 1


@activate
def test_translate_jit_event__rerun_full_suite_pr_event(mocker, idempotency_table):
    """
    Arrange:
        - Mock tenant, asset
        - Create webhook event of rerun for PR
    Act:
        - Call translate_jit_event
    Assert:
        - Verify that the expected code related jit event was sent
    """
    # Mock setup
    tenant, asset = setup_mock_tenant(is_asset_enable_pr_checks=True, is_asset_active=True)
    setup_mock_pr_check_preference(is_pr_enabled=True, status_code=200)
    mock_get_internal_token_api()
    setup_mock_teams(is_pr_check_enabled=True, status_code=200)
    _mock_is_allow_controlled_pr_checks_ff_response(mocker, is_ff_enabled=True)

    # Event processing
    with mock_eventbridge(bus_name=[TRIGGER_EXECUTION_BUS_NAME]) as get_events:
        rerun_event_body = WebhookRerunEventBodyFactory.build(
            jit_event_id="jit_event_id",
            vendor="github",
            event_type=RERUN_PIPELINE,
            check_suite=CheckSuiteFactory.build(
                app=MOCK_GITHUB_APP,
                head_sha="head_sha",
                pull_requests=[
                    {
                        "head": {"ref": "ref", "sha": "head_sha"},
                        "base": {"ref": "ref", "sha": "base_sha"},
                        "number": 1,
                    }
                ],
            ),
            sender=Sender(id=1, login="login", avatar_url="avatar_url"),
            repository=RepositoryFactory.build(name=asset.asset_name),
            installation=InstallationId(id=INSTALLATION_ID),
        )
        detail = WebhookEvent[WebhookRerunEventBody](
            vendor='vendor', app_id='111111', event_type=RERUN_PIPELINE,
            dedupe_id='dedupe_id', webhook_headers={}, webhook_body_str=None,
            webhook_body_json=rerun_event_body,
        )

        handler({"detail": detail.dict()}, None)
        processed_events = get_events[TRIGGER_EXECUTION_BUS_NAME]()

    assert len(processed_events) == 1
    processed_events[0]["detail"].pop("jit_event_id")
    assert processed_events[0]["detail"] == dict(
        tenant_id=tenant.tenant_id,
        jit_event_name="pull_request_updated",
        asset_id="asset_id",
        workflows=None,
        centralized_repo_asset_id=None,
        centralized_repo_asset_name="repo-name",
        centralized_repo_files_location=None,
        ci_workflow_files_path=None,
        app_id="app_id",
        installation_id="11111111",
        original_repository="repo-name",
        vendor="vendor",
        owner="owner",
        branch="ref",
        pull_request_number="1",
        pull_request_title="Rerun PR 1",
        commits=Commits(base_sha="base_sha", head_sha="head_sha").dict(),
        user_vendor_id="1",
        user_vendor_name="login",
        languages=[],
        event_signature="vendor-owner-asset_id-head_sha-base_sha",
    )


@activate
@pytest.mark.parametrize("second_call_after_expiration", [False, True])
def test_translate_jit_event__rerun_single_check_pr_event(mocker, idempotency_table, second_call_after_expiration):
    """
    Arrange:
        - Mock tenant, asset
        - Create webhook event of rerun for PR
    Act:
        - Call translate_jit_event
    Assert:
        - Verify that the expected code related jit event was sent
    """
    # Mock setup
    tenant, asset = setup_mock_tenant(is_asset_enable_pr_checks=True, is_asset_active=True)
    setup_mock_pr_check_preference(is_pr_enabled=True, status_code=200)
    mock_get_internal_token_api()
    setup_mock_teams(is_pr_check_enabled=True, status_code=200)
    _mock_is_allow_controlled_pr_checks_ff_response(mocker, is_ff_enabled=True)

    # Event processing
    with mock_eventbridge(bus_name=[TRIGGER_EXECUTION_BUS_NAME]) as get_events:
        rerun_event_body = WebhookSingleCheckRerunEventBodyFactory.build(
            jit_event_id="jit_event_id",
            vendor="github",
            event_type=RERUN_PIPELINE,
            check_run=CheckRun(
                name="",
                status="",
                html_url="",
                check_suite=CheckSuiteFactory.build(
                    app=MOCK_GITHUB_APP,
                    head_sha="head_sha",
                    pull_requests=[
                        {
                            "head": {"ref": "ref", "sha": "head_sha"},
                            "base": {"ref": "ref", "sha": "base_sha"},
                            "number": 1,
                        },
                    ],
                )
            ),
            sender=Sender(id=1, login="login", avatar_url="avatar_url"),
            repository=RepositoryFactory.build(name=asset.asset_name),
            installation=InstallationId(id=INSTALLATION_ID),
        )
        detail = WebhookEvent[WebhookSingleCheckRerunEventBody](
            vendor='vendor', app_id='111111', event_type=CHECK_RERUN_PIPELINE,
            dedupe_id='dedupe_id', webhook_headers={}, webhook_body_str=None,
            webhook_body_json=rerun_event_body,
        )

        with freezegun.freeze_time("2022-01-01 12:00:00") as frozen_time:
            handler({"detail": detail.dict()}, None)
            if second_call_after_expiration:
                # we should wait for the first rerun to expire, so we jump in time 31 seconds
                frozen_time.move_to("2022-01-01 12:00:31")

            handler({"detail": detail.dict()}, None)
            processed_events = get_events[TRIGGER_EXECUTION_BUS_NAME]()

    expected_rerun_events = 2 if second_call_after_expiration else 1
    assert len(processed_events) == expected_rerun_events

    if expected_rerun_events == 2:
        # assert we got different jit event ids
        assert processed_events[0]["detail"]["jit_event_id"] != processed_events[1]["detail"]["jit_event_id"]
    for i in range(0, expected_rerun_events):
        processed_events[i]["detail"].pop("jit_event_id")
        assert processed_events[i]["detail"] == dict(
            tenant_id=tenant.tenant_id,
            jit_event_name="pull_request_updated",
            asset_id="asset_id",
            workflows=None,
            centralized_repo_asset_id=None,
            centralized_repo_asset_name="repo-name",
            centralized_repo_files_location=None,
            ci_workflow_files_path=None,
            app_id="app_id",
            installation_id="11111111",
            original_repository="repo-name",
            vendor="vendor",
            owner="owner",
            branch="ref",
            pull_request_number="1",
            pull_request_title="Rerun PR 1",
            commits=Commits(base_sha="base_sha", head_sha="head_sha").dict(),
            user_vendor_id="1",
            user_vendor_name="login",
            languages=[],
            event_signature="vendor-owner-asset_id-head_sha-base_sha",
        )

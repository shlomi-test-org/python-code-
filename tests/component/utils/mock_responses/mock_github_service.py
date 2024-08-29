import re

import responses
from jit_utils.models.github.github_status import GithubStatusAlert
from pydantic_factories import ModelFactory

from tests.common import DUMMY_BASE_URL


class GithubStatusAlertFactory(ModelFactory):
    __model__ = GithubStatusAlert


def mock_get_github_status_api(status: str):
    github_status_alert: GithubStatusAlert = GithubStatusAlertFactory.build(status=status)

    responses.add(
        responses.GET,
        f"{DUMMY_BASE_URL}/github/github-status",
        json=github_status_alert.dict(),
        status=200,
    )


def mock_get_github_token(app_id: str, installation_id: str, return_code: int = 200):
    response_payload = {"token": "gh_token"} if return_code == 200 else {"message": "Not Found"}
    responses.add(
        responses.GET,
        f"{DUMMY_BASE_URL}/github/app/{app_id}/installation/{installation_id}/token",
        json=response_payload,
        status=return_code,
    )


def mock_get_pr_change_list(
        json_response: list[str],
        tenant_id='.*',
        owner='.*',
        repo='.*',
        pr_number='.*',
        status=200,
):
    """Mock the get-pr-change-list-endpoint in both github and gitlab (SCM Services)."""
    responses.add(
        responses.GET,
        re.compile(r"https://api.dummy.jit.io/(github|gitlab)/"
                   rf"internal/{tenant_id}/owners/{owner}/repos/{repo}/prs/{pr_number}/change-list"),
        json=json_response,
        status=status,
    )

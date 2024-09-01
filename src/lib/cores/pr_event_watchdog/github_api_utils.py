from typing import List, Dict

from jit_utils.requests import get_session

from src.lib.models.github_models import GithubPullRequest, GithubCheckSuite, GithubCheckRun


def _get_headers(github_token: str) -> Dict:
    return {
        'Accept': 'application/vnd.github.antiope-preview+json',
        'Authorization': f'token {github_token}'
    }


def get_pr_details(github_token: str, org: str, repo: str, pr_number: str) -> GithubPullRequest:
    url = f'https://api.github.com/repos/{org}/{repo}/pulls/{pr_number}'
    response = get_session().get(url, headers=_get_headers(github_token))
    response.raise_for_status()
    return GithubPullRequest(**response.json())


def list_check_suites(
        github_token: str, org: str, repo: str, last_commit_sha: str
) -> List[GithubCheckSuite]:
    url = f'https://api.github.com/repos/{org}/{repo}/commits/{last_commit_sha}/check-suites'
    response = get_session().get(url, headers=_get_headers(github_token))
    response.raise_for_status()
    return [GithubCheckSuite(**suite) for suite in response.json()['check_suites']]


def list_checks_for_suite(github_token: str, org: str, repo: str, check_suite_id: int) -> List[GithubCheckRun]:
    url = f'https://api.github.com/repos/{org}/{repo}/check-suites/{check_suite_id}/check-runs'
    response = get_session().get(url, headers=_get_headers(github_token))
    response.raise_for_status()
    return [GithubCheckRun(**run) for run in response.json()['check_runs']]

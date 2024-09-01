import responses


def mock_get_pull_request_api(org: str, repo: str, pr_number: str, head_sha: str):
    responses.add(
        responses.GET,
        f"https://api.github.com/repos/{org}/{repo}/pulls/{pr_number}",
        json={
            "head": {
                "ref": "adiattlan-patch-5",
                "sha": head_sha,
                "url": "https://api.github.com/repos/commits/52549b160a66b46098cdd8a51effe88b29334a48",
                "message": "Update README.md",
            },
            "base": {
                "ref": "main",
                "sha": "52549b160a66b46098cdd8a51effe88b29334a48",
                "url": "https://api.github.com/repos/commits/52549b160a66b46098cdd8a51effe88b29334a48",
                "message": "Update README.md",
            },
        },
        status=200,
    )


def mock_get_commit_check_suites_api(org: str, repo: str, commit_sha: str, jit_check_suite_id: int = 2):
    responses.add(
        responses.GET,
        f"https://api.github.com/repos/{org}/{repo}/commits/{commit_sha}/check-suites",
        json={
            'check_suites': [
                {
                    'id': 1,
                    'app': {
                        'id': 1,
                        'slug': 'github-actions',
                        'name': 'GitHub Actions',
                    }
                },
                {
                    'id': jit_check_suite_id,
                    'app': {
                        'id': jit_check_suite_id,
                        'slug': 'jit-security',
                        'name': 'Jit',
                    }
                },
            ]
        },
        status=200,
    )


def mock_get_checks_in_check_suite_api(org: str, repo: str, check_suite_id: int):
    responses.add(
        responses.GET,
        f"https://api.github.com/repos/{org}/{repo}/check-suites/{check_suite_id}/check-runs",
        json={'check_runs': [{
            'name': 'Jit Security',
            'status': 'completed',
            'conclusion': 'success',
        }]},
        status=200,
    )

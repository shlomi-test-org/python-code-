from tests.mocks.execution_mocks import MOCK_TENANT_ID

MOCK_LOG_ORCHESTRATOR_LOG = {
    "tenant_id": MOCK_TENANT_ID,
    "execution_id": "ab13c4d5-6e7f-8g9h-0i1j-2k3l4m5n6o7p",
    "jit_event_id": "ab13c4d5-6e7f-8g9h-0i1j-2k3l4m5n6o7p",
    "vendor": "my-vendor",
    "app_and_installation_id": "my-app/my-installation_id",
    "full_repo_path": 'no-one/my-repo',
    "branch": 'my-cool-branch',
    "workflow_suite_id": "3fb5b696cd7b7055a11fcd7b7055a11f",
    "workflow_id": '3fb5b696cd7b7055a11f90f7d9b5fc9b4913bffd',
    "job_name": 'linter',
    "commits": {"base_sha": 'fae273a4bfc91d8178dab1fd71159b89e95130e3',  # pragma: allowlist secret
                "head_sha": 'xae273a4bfc91d8178dab1fd71159b89e95130e7'},  # pragma: allowlist secret
    "pull_request_number": "1342432553",
    "payload": []
}

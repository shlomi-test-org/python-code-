import pytest

from src.lib.cores.fargate.common import get_batch_job_properties
from src.lib.models.execution_models import BaseExecutionIdentifiers

OLD_EVENT_ENV_EXAMPLE = [{'name': 'EVENT', 'value': '{"payload": {"tenant_id": "94761a07-939a-49f6-b5a9-9a0b10fd64c2",'
                                                    '"vendor": "domain",'
                                                    '"workflow_suite_id": "30b3b176-1ded-4fb5-a27c-c025bfc73c46", '
                                                    '"jit_event_id": "30b3b176-1ded-4fb5-a27c-c025bfc73c46", '
                                                    '"execution_id": "c483d553-fb05-4d78-82ed-bbbea2e6b5b2"}}'}]

NEW_ENV_EXAMPLE = [{'name': 'TENANT_ID', 'value': '94761a07-939a-49f6-b5a9-9a0b10fd64c2'},
                   {'name': 'JIT_EVENT_ID', 'value': '30b3b176-1ded-4fb5-a27c-c025bfc73c46'},
                   {'name': 'EXECUTION_ID', 'value': 'c483d553-fb05-4d78-82ed-bbbea2e6b5b2'}]


@pytest.mark.parametrize(
    "job_container_env_vars, expected_env_vars",
    [
        (
                OLD_EVENT_ENV_EXAMPLE,
                BaseExecutionIdentifiers(
                    tenant_id='94761a07-939a-49f6-b5a9-9a0b10fd64c2',
                    jit_event_id='30b3b176-1ded-4fb5-a27c-c025bfc73c46',
                    execution_id='c483d553-fb05-4d78-82ed-bbbea2e6b5b2',
                )
        ),
        (
                NEW_ENV_EXAMPLE,
                BaseExecutionIdentifiers(
                    tenant_id='94761a07-939a-49f6-b5a9-9a0b10fd64c2',
                    jit_event_id='30b3b176-1ded-4fb5-a27c-c025bfc73c46',
                    execution_id='c483d553-fb05-4d78-82ed-bbbea2e6b5b2',
                )
        ),
        ({}, None)
    ]
)
def test_get_batch_job_properties(job_container_env_vars, expected_env_vars):
    parsed_env_vars = get_batch_job_properties(job_container_env_vars)
    assert parsed_env_vars == expected_env_vars

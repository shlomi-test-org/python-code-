import pytest

from src.lib.models.execution_models import ExecutionEntity
from tests.mocks.execution_mocks import generate_mock_executions
from tests.unit.cores.execution_runner.test_aws_execution_runner import MOCK_TENANT_ID


@pytest.fixture
def test_execution(executions_manager):
    return generate_mock_executions(1, MOCK_TENANT_ID)[0]


def test_execution_insertion(executions_manager, test_execution):
    executions_manager.create_execution(test_execution)

    response = executions_manager.table.get_item(
        Key={
            'PK': executions_manager.get_key(tenant=test_execution.tenant_id, jit_event=test_execution.jit_event_id),
            'SK': executions_manager.get_key(execution=test_execution.execution_id)
        }
    )

    item = response['Item']

    # we don't insert GSI6 on insert
    expected_gsi_keys = [f for f in ExecutionEntity.__fields__ if f.startswith("GSI") and not f.startswith("GSI6")]
    assert all([gsi in item for gsi in expected_gsi_keys])

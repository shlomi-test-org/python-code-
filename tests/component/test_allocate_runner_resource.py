import datetime
from typing import List

import pytest
from freezegun import freeze_time

from jit_utils.models.execution import Execution, ExecutionStatus, ResourceType
from jit_utils.models.execution_context import Runner
from jit_utils.models.execution_priority import ExecutionPriority

from test_utils.aws.mock_eventbridge import mock_eventbridge

from src.lib.constants import EXECUTION_EVENT_BUS_NAME, DYNAMODB_INSERT_EVENT_TYPE
from src.lib.cores.allocate_runner_resources_core import allocate_runner_resources
from src.lib.data.executions_manager import ExecutionsManager
from src.lib.data.resources_manager import ResourcesManager
from src.lib.models.resource_models import Resource

from tests.consts import TESTS_TIME
from tests.mocks.execution_mocks import generate_mock_executions
from tests.mocks.tenant_mocks import MOCK_TENANT_ID

CI_RESOURCE = Resource(tenant_id=MOCK_TENANT_ID,
                       resource_type=ResourceType.CI,
                       max_resources_in_use=1,
                       resources_in_use=0)
CI_LOW_PRIORITY_EXECUTIONS = generate_mock_executions(2,
                                                      job_runner=Runner.CI,
                                                      priority=ExecutionPriority.LOW)
CI_LOW_PRIORITY_EXECUTION = CI_LOW_PRIORITY_EXECUTIONS[0]


@freeze_time(TESTS_TIME)
@pytest.mark.parametrize(
    'resources_to_create, executions_to_create, event_type, execution, expected_executions, expected_resources', [
        pytest.param(
            [CI_RESOURCE],
            [],
            DYNAMODB_INSERT_EVENT_TYPE,
            CI_LOW_PRIORITY_EXECUTION,
            [CI_LOW_PRIORITY_EXECUTION.copy(update={
                'status': ExecutionStatus.DISPATCHING.value,
                'execution_timeout': (TESTS_TIME + datetime.timedelta(minutes=5)).isoformat(),
            })],
            [CI_RESOURCE.copy(update={'resources_in_use': 1})],
            id='No pending executions',
        ),
        pytest.param(
            [CI_RESOURCE.copy(update={'resources_in_use': 1})],
            [],
            DYNAMODB_INSERT_EVENT_TYPE,
            CI_LOW_PRIORITY_EXECUTION,
            [CI_LOW_PRIORITY_EXECUTION.copy(update={
                'status': ExecutionStatus.PENDING.value,
            })],
            [CI_RESOURCE.copy(update={'resources_in_use': 1})],
            id='No free resources',
        ),
        pytest.param(
            [CI_RESOURCE],
            [CI_LOW_PRIORITY_EXECUTIONS[0]],
            DYNAMODB_INSERT_EVENT_TYPE,
            CI_LOW_PRIORITY_EXECUTIONS[1],
            [
                # The first execution should be updated because it is the oldest one
                CI_LOW_PRIORITY_EXECUTIONS[0].copy(update={
                    'status': ExecutionStatus.DISPATCHING.value,
                    'execution_timeout': (TESTS_TIME + datetime.timedelta(minutes=5)).isoformat(),
                }),
                CI_LOW_PRIORITY_EXECUTIONS[1].copy(update={
                    'status': ExecutionStatus.PENDING.value,
                })
            ],
            [CI_RESOURCE.copy(update={'resources_in_use': 1})],
            id='Collect previous execution',
        ),
    ])
def test_allocate_runner_resources(
        resources_manager: ResourcesManager,
        executions_manager: ExecutionsManager,
        resources_to_create: List[Resource],
        executions_to_create: List[Execution],
        event_type: str,
        execution: Execution,
        expected_executions: List[Execution],
        expected_resources: List[Resource]):
    for execution_to_create in executions_to_create:
        executions_manager.create_execution(execution_to_create)

    # We also need to create the execution in the DB because this function triggered by INSERT or MODIFY dynamodb event
    executions_manager.create_execution(execution)

    for resource in resources_to_create:
        resources_manager.create_resource(resource)

    with mock_eventbridge(bus_name=EXECUTION_EVENT_BUS_NAME):
        allocate_runner_resources(event_type=event_type, execution=execution)

    for resource in expected_resources:
        assert resources_manager.get_resource(
            tenant_id=resource.tenant_id,
            resource_type=resource.resource_type) == resource

    for expected_execution in expected_executions:
        assert executions_manager.get_execution_by_jit_event_id_and_execution_id(
            tenant_id=expected_execution.tenant_id,
            execution_id=expected_execution.execution_id,
            jit_event_id=expected_execution.jit_event_id) == expected_execution

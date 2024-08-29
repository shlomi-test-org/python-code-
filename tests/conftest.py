import json
from functools import lru_cache
from pathlib import Path
from typing import Dict
from typing import List
from typing import Tuple

import boto3
import pytest
import yaml
from jit_utils.aws_clients.config.aws_config import get_aws_config
from mypy_boto3_batch import BatchClient
from mypy_boto3_batch.type_defs import ComputeEnvironmentOrderTypeDef
from mypy_boto3_batch.type_defs import ComputeResourceTypeDef
from mypy_boto3_ec2 import EC2Client
from mypy_boto3_iam import IAMClient
from test_utils.aws.moto_wrappers import mock_dynamodb_fixt  # noqa: F401
from test_utils.aws.moto_wrappers import mock_events_fixt  # noqa: F401
from test_utils.aws.moto_wrappers import mock_sqs_fixt  # noqa: F401

from src.lib.constants import AWS_COMMON_BATCH_CLIENT_NAME
from src.lib.cores.fargate.constants import FARGATE_TASKS_BATCH_QUEUE_NAME
from src.lib.data.executions_manager import ExecutionsManager
from src.lib.data.resources_manager import ResourcesManager
from jit_utils.models.execution import Execution
from src.lib.models.execution_models import ExecutionEntity
from tests.mocks.execution_mocks import generate_mock_executions
from tests.mocks.tenant_mocks import MOCK_TENANT_ID

EXECUTIONS_TABLE_NAME = "Executions"
RESOURCES_TABLE_NAME = "Resources"

_COMPUTE_ENV_NAME = 'fargate-compute-env'
_COMPUTE_ENV_ROLE_NAME = 'AWSServiceRoleForBatch'
_COMPUTE_ENV_POLICY = 'arn:aws:iam::aws:policy/aws-service-role/BatchServiceRolePolicy'


@lru_cache()
def get_table_conf(table_name):
    with open(Path(__file__).parent.parent / "serverless.yml", 'r') as f:
        conf = yaml.safe_load(f)
        schema = conf["resources"]["Resources"][table_name]
        # Required by moto when using dynamodb streams
        if schema["Properties"].get("StreamSpecification", None):
            schema["Properties"]["StreamSpecification"]["StreamEnabled"] = True

        table_properties = schema['Properties']
        # exclude PointInTimeRecoverySpecification from table properties
        # because it requires another api call to the update_continuous_backups api
        # and it is not needed for the tests
        # exclude TimeToLiveSpecification from table properties
        table_properties.pop('TimeToLiveSpecification', None)
        table_properties.pop('PointInTimeRecoverySpecification', None)
    return table_properties


def create_table(db, table_name):
    table_properties = get_table_conf(table_name)
    return db.create_table(**table_properties)


@pytest.fixture
def executions_table(mock_dynamodb_fixt):  # noqa: F811
    table = create_table(mock_dynamodb_fixt, EXECUTIONS_TABLE_NAME)

    # Wait until the table exists.
    table.meta.client.get_waiter('table_exists').wait(TableName=EXECUTIONS_TABLE_NAME)
    assert table.table_status == 'ACTIVE'

    yield mock_dynamodb_fixt


@pytest.fixture
def resources_table(mock_dynamodb_fixt):  # noqa: F811
    table = create_table(mock_dynamodb_fixt, RESOURCES_TABLE_NAME)

    # Wait until the table exists.
    table.meta.client.get_waiter('table_exists').wait(TableName=RESOURCES_TABLE_NAME)
    assert table.table_status == 'ACTIVE'

    yield mock_dynamodb_fixt


@pytest.fixture
def executions_manager(executions_table) -> ExecutionsManager:
    """
    Fixture to create an instance of the ExecutionsManager class.
    """
    return ExecutionsManager()


@pytest.fixture(scope="function")
def mock_create_executions(executions_manager):
    """
    Fixture that creates executions and returns them
    """
    mock_executions = generate_mock_executions(20, MOCK_TENANT_ID)
    with executions_manager.table.batch_writer() as batch:
        for execution in mock_executions:
            executions_record = convert_execution_to_execution_entity(execution)
            batch.put_item(Item=executions_record.dict(exclude_none=True))
    return mock_executions


@pytest.fixture
def resources_manager(resources_table) -> ResourcesManager:
    """
    Fixture to create an instance of the ExecutionsManager class.
    """
    return ResourcesManager()


def get_key(**kwargs):
    return '#'.join(f'{key.upper()}#{str(value).lower()}' for key, value in kwargs.items())


def convert_execution_to_execution_entity(execution: Execution) -> ExecutionEntity:
    # Partitions
    pk = gsi9pk_tenant_id_jit_event_id = gsi7pk_tenant_jit_event_id = get_key(
        tenant=execution.tenant_id, jit_event=execution.jit_event_id
    )  # high cardinality
    gsi2pk = gsi8pk_tenant_id_status = get_key(
        tenant=execution.tenant_id, status=execution.status
    )  # medium cardinality
    gsi3pk = get_key(tenant=execution.tenant_id, plan_item=execution.plan_item_slug)  # medium cardinality
    gsi4pk = get_key(
        tenant=execution.tenant_id, plan_item=execution.plan_item_slug, status=execution.status
    )  # medium-high cardinality
    gsi5pk = get_key(
        tenant=execution.tenant_id,
        runner=execution.job_runner,
        status=execution.status,
    )  # medium-high cardinality

    # sort keys
    sk = get_key(execution=execution.execution_id)
    gsi2sk = gsi3sk = gsi4sk = gsi7sk_created_at = execution.created_at
    gsi5sk = get_key(priority=execution.priority, created_at=execution.created_at)
    gsi8sk_asset_id_created_at = get_key(asset_id=execution.asset_id, created_at=execution.created_at)
    gsi9sk_job_name_created_at = get_key(job_name=execution.job_name, created_at=execution.created_at)
    return ExecutionEntity(
        PK=pk,
        SK=sk,
        GSI2PK=gsi2pk,
        GSI2SK=gsi2sk,
        GSI3PK=gsi3pk,
        GSI3SK=gsi3sk,
        GSI4PK=gsi4pk,
        GSI4SK=gsi4sk,
        GSI5PK=gsi5pk,
        GSI5SK=gsi5sk,
        GSI7PK_TENANT_JIT_EVENT_ID=gsi7pk_tenant_jit_event_id,
        GSI7SK_CREATED_AT=gsi7sk_created_at,
        GSI8PK_TENANT_ID_STATUS=gsi8pk_tenant_id_status,
        GSI8SK_ASSET_ID_CREATED_AT=gsi8sk_asset_id_created_at,
        GSI9PK_TENANT_ID=gsi9pk_tenant_id_jit_event_id,
        GSI9SK_JIT_EVENT_ID_JOB_NAME_CREATED_AT=gsi9sk_job_name_created_at,
        **execution.dict(exclude_none=True)
    )


def _get_subnets_and_security_groups(aws_config: Dict) -> Tuple[List[str], List[str]]:
    ec2_client: EC2Client = boto3.client('ec2', **aws_config)
    subnets = [subnet['SubnetId'] for subnet in ec2_client.describe_subnets()['Subnets']]
    security_groups = [security_group['GroupId']
                       for security_group in ec2_client.describe_security_groups()['SecurityGroups']]
    return subnets, security_groups


def _create_iam_role(aws_config: Dict) -> str:
    iam_client: IAMClient = boto3.client('iam', **aws_config)
    try:
        role = iam_client.get_role(RoleName=_COMPUTE_ENV_ROLE_NAME)
        return role['Role']['Arn']
    except Exception:
        pass

    policy = iam_client.get_policy(
        PolicyArn=_COMPUTE_ENV_POLICY
    )

    doc = iam_client.get_policy_version(
        PolicyArn=_COMPUTE_ENV_POLICY,
        VersionId=policy['Policy']['DefaultVersionId']
    )['PolicyVersion']['Document']

    resp = iam_client.create_role(RoleName=_COMPUTE_ENV_ROLE_NAME, AssumeRolePolicyDocument=json.dumps(doc))
    return resp['Role']['Arn']


def create_batch_queue():
    aws_config = get_aws_config()

    subnets, security_groups = _get_subnets_and_security_groups(aws_config)
    role_arn = _create_iam_role(aws_config)

    batch_client: BatchClient = boto3.client(AWS_COMMON_BATCH_CLIENT_NAME, **aws_config)

    batch_client.delete_job_queue(jobQueue=FARGATE_TASKS_BATCH_QUEUE_NAME)
    batch_client.delete_compute_environment(computeEnvironment=_COMPUTE_ENV_NAME)

    compute_env = batch_client.create_compute_environment(
        computeEnvironmentName=_COMPUTE_ENV_NAME,
        type='MANAGED',
        state='ENABLED',
        serviceRole=role_arn,
        computeResources=ComputeResourceTypeDef(
            type='FARGATE',
            maxvCpus=256,
            subnets=subnets,
            securityGroupIds=security_groups
        )
    )

    batch_client.create_job_queue(
        jobQueueName=FARGATE_TASKS_BATCH_QUEUE_NAME,
        state='ENABLED',
        priority=1,
        computeEnvironmentOrder=[
            ComputeEnvironmentOrderTypeDef(
                computeEnvironment=compute_env['computeEnvironmentArn'],
                order=0
            )
        ],
    )


@pytest.fixture()
def prepare_env_vars(monkeypatch):
    monkeypatch.setenv("DEPLOYMENT_STAGE", "dev")
    monkeypatch.setenv("API_HOST", "api.dummy.jit.io")
    # Remove the environment variable, so mock_dynamodb2 will take over
    monkeypatch.delenv('AWS_SERVICE_URL', raising=False)
    monkeypatch.delenv('LOCALSTACK_HOSTNAME', raising=False)

    monkeypatch.setenv("AWS_ACCOUNT_ID", "1234567890")
    monkeypatch.setenv("AWS_REGION_NAME", "us-east-1")

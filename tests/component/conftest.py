from pathlib import Path

import boto3
import pytest
from moto import mock_dynamodb
from moto.s3 import mock_s3
from test_utils.aws.mock_dynamodb import create_table

from src.lib.constants import S3_EXECUTION_OUTPUTS_BUCKET_NAME


@pytest.fixture(autouse=True)
def prepare_env_vars(monkeypatch):
    monkeypatch.setenv('API_HOST', 'api.dummy.jit.io')

    # Remove the environment variable, so mock_dynamodb will take over
    monkeypatch.delenv('AWS_SERVICE_URL', raising=False)
    monkeypatch.delenv('LOCALSTACK_HOSTNAME', raising=False)


@pytest.fixture
def mocked_tables():
    with mock_dynamodb():
        serverless_yml_file_path = (Path(__file__).parent.parent.parent / 'serverless.yml').as_posix()
        yield {
            'executions': create_table('Executions', serverless_yml_file_path),
            'resources': create_table('Resources', serverless_yml_file_path),
        }


@pytest.fixture
def mocked_s3_executions_outputs_bucket():
    with mock_s3():
        s3_client = boto3.client('s3')
        s3_client.create_bucket(Bucket=S3_EXECUTION_OUTPUTS_BUCKET_NAME)

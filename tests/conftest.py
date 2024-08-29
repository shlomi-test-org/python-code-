import json
import os
from pathlib import Path

import boto3
import pytest
import yaml
from jit_utils.lambda_decorators import set_request_token
from moto import mock_firehose, mock_dynamodb
from moto.s3 import mock_s3

from src.lib.constants import PK, SK
from src.lib.data.saved_filters import FindingsDynamoManager
from src.lib.data.upload_findings_status import UploadFindingsStatusManager

FINDINGS_TABLE = 'Findings'
UPLOAD_FINDINGS_STATUS_TABLE = 'UploadFindingsStatus'
OLD_ZAP_FINDINGS_JSON_FILE = 'tests/raw/old_zap_finding.json'
ZAP_FINDINGS_JSON_FILE = 'tests/raw/zap_finding.json'
S3_FILE_NAME = 'findings_file.json'
S3_BUCKET_NAME = 'bucket_name'
S3_FILE_CONTENT = json.dumps({'test': 'test'})

os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
os.environ['AWS_ACCOUNT_ID'] = '123456789'
os.environ['AWS_REGION_NAME'] = 'us-east-1'


@pytest.fixture(scope="session", autouse=True)
def prepare_env_vars():
    os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
    os.environ['AWS_ACCOUNT_ID'] = '123456789'
    os.environ['AWS_REGION_NAME'] = 'us-east-1'


# This fixture run before each test automatically - in order to clear the request token between tests
@pytest.fixture(scope="function", autouse=True)
def clear_context_request_token():
    set_request_token(None)


def _create_idempotency_table(db):
    """Create the IdempotencyTable.
    Useful for unit/component tests which execute a lambda function that uses idempotency handling.
    """
    return db.create_table(
        TableName='IdempotencyTable',
        BillingMode='PAY_PER_REQUEST',
        KeySchema=[
            {
                'AttributeName': 'id',
                'KeyType': 'HASH'
            },
        ],
        AttributeDefinitions=[
            {
                'AttributeName': 'id',
                'AttributeType': 'S'
            },
        ],
    )


@pytest.fixture
def upload_findings_status_table():
    dynamodb = boto3.resource('dynamodb', endpoint_url="http://localhost:4566", region_name='us-east-1')
    table = dynamodb.Table('UploadFindingsStatus')
    yield table
    clear_table(table)


def clear_table(table):
    scan = table.scan()
    with table.batch_writer() as batch:
        for item in scan['Items']:
            batch.delete_item(
                Key={PK: item['PK'], SK: item['SK']}
            )


def _create_findings_table(db):
    with open(Path(__file__).parent.parent / 'serverless.yml', 'r') as f:
        conf = yaml.safe_load(f)
        print(conf)
        schema = conf["resources"]["Resources"]['Findings']
        schema["Properties"]["TableName"] = FINDINGS_TABLE
        table_properties = schema['Properties']
        # exclude PointInTimeRecoverySpecification from table properties
        # because it requires another api call to the update_continuous_backups api
        # and it is not needed for the tests
        table_properties.pop('PointInTimeRecoverySpecification', None)

    return db.create_table(**table_properties)


def _create_upload_status_table(db):
    with open(Path(__file__).parent.parent / 'serverless.yml', 'r') as f:
        conf = yaml.safe_load(f)
        print(conf)
        schema = conf["resources"]["Resources"]['UploadFindingsStatus']
        schema["Properties"]["TableName"] = UPLOAD_FINDINGS_STATUS_TABLE
        table_properties = schema['Properties']
        table_properties.pop('PointInTimeRecoverySpecification', None)
        table_properties.pop('TimeToLiveSpecification', None)
        table_properties.pop('StreamSpecification', None)
    return db.create_table(**table_properties)


@pytest.fixture
def dynamodb(monkeypatch):
    # Remove the environment variable, so mock_dynamodb2 will take over
    if os.getenv('LOCALSTACK_HOSTNAME'):
        monkeypatch.delenv('LOCALSTACK_HOSTNAME')
    with mock_dynamodb():
        db = boto3.resource('dynamodb', region_name='us-east-1')
        findings_table = _create_findings_table(db)
        findings_status_table = _create_upload_status_table(db)
        # Wait until the table exists.
        findings_table.meta.client.get_waiter('table_exists').wait(TableName=FINDINGS_TABLE)
        findings_status_table.meta.client.get_waiter('table_exists').wait(TableName=UPLOAD_FINDINGS_STATUS_TABLE)
        assert findings_table.table_status == 'ACTIVE'
        assert findings_status_table.table_status == 'ACTIVE'
        yield db


@pytest.fixture
def env_variables():
    os.environ['FINDINGS_COLLECTION_NAME'] = 'findings'
    os.environ['IGNORE_RULES_COLLECTION_NAME'] = 'ignore_rules'
    os.environ['DB_NAME'] = 'test'
    os.environ['DB_INSTANCE_NAME'] = 'localhost'


@pytest.fixture
def mocked_tables(monkeypatch):
    if os.getenv('LOCALSTACK_HOSTNAME'):
        monkeypatch.delenv('LOCALSTACK_HOSTNAME')
    with mock_dynamodb():
        db = boto3.resource('dynamodb', region_name='us-east-1')
        tables = (_create_findings_table(db), _create_upload_status_table(db))
        idempotency_table = _create_idempotency_table(db)

        # Wait until the tables exists.
        for table in tables:
            table.meta.client.get_waiter('table_exists')
            assert table.table_status == 'ACTIVE'

        idempotency_table.meta.client.get_waiter('table_exists')
        assert idempotency_table.table_status == 'ACTIVE'

        yield tables


@pytest.fixture
def s3_client():
    with mock_s3():
        s3_client = boto3.client('s3', region_name='us-east-1')
        yield s3_client


@pytest.fixture
def create_firehose_mock(s3_client):
    with mock_firehose():
        s3_client.create_bucket(Bucket=S3_BUCKET_NAME)
        os.environ['ENV_NAME'] = 'prod'
        firehose = boto3.client('firehose', region_name='us-east-1')
        os.environ['FIREHOSE_NAME'] = 'firehose'
        firehose.create_delivery_stream(
            DeliveryStreamName='firehose',
            S3DestinationConfiguration={
                'RoleARN': 'arn:aws:iam::123456789012:role/firehose_delivery_role',
                'BucketARN': 'arn:aws:s3:::' + S3_BUCKET_NAME,
                'Prefix': 'myPrefix',
                'BufferingHints': {
                    'SizeInMBs': 1,
                    'IntervalInSeconds': 60
                },
                'CompressionFormat': 'UNCOMPRESSED',
            })
        yield firehose


@pytest.fixture
def saved_filters_manager(monkeypatch, dynamodb):
    # Set table name to be 'FindingsTests'
    monkeypatch.setattr(FindingsDynamoManager, 'TABLE_NAME', FINDINGS_TABLE)

    return FindingsDynamoManager()


@pytest.fixture
def upload_findings_status_manager(monkeypatch, dynamodb):
    # Set table name to be 'FindingsTests'
    monkeypatch.setattr(UploadFindingsStatusManager, 'TABLE_NAME', UPLOAD_FINDINGS_STATUS_TABLE)

    return UploadFindingsStatusManager()

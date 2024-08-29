import json
from http import HTTPStatus
from uuid import uuid4

import boto3
import pytest
import responses
from moto import mock_s3

from src.handlers.control_output_files import zipball
from src.lib.constants import S3_EXECUTION_OUTPUTS_BUCKET_NAME
from src.lib.cores.control_output_files import get_output_file_key_name
from tests.component.fixtures import get_handler_event

ZIP_BODY = b'PK...'


def _get_mock_event(tenant_id: str, jit_event_id: str, execution_id: str):
    return get_handler_event(
        tenant_id=tenant_id,
        path_parameters={"jit_event_id": jit_event_id, "execution_id": execution_id},
    )


@pytest.fixture
def s3_client():
    with mock_s3():
        yield boto3.client('s3', **{'region_name': 'us-east-1'})


@pytest.fixture
def create_s3_bucket(s3_client):
    s3_client.create_bucket(Bucket=S3_EXECUTION_OUTPUTS_BUCKET_NAME)


@pytest.fixture
def zip_file_in_s3(create_s3_bucket, s3_client):
    def inner(tenant_id: str, event_id: str, execution_id: str):
        s3_client.put_object(
            Bucket=S3_EXECUTION_OUTPUTS_BUCKET_NAME,
            Key=get_output_file_key_name(tenant_id, event_id, execution_id, 'public.zip'),
            Body=ZIP_BODY,
        )

    return inner


@responses.activate
def test_create_zip_for_control_outputs(zip_file_in_s3):
    tenant_id = str(uuid4())
    jit_event_id = str(uuid4())
    execution_id = str(uuid4())

    zip_file_in_s3(tenant_id, jit_event_id, execution_id)

    event = _get_mock_event(tenant_id, jit_event_id, execution_id)
    response = zipball(event, {})  # type: ignore
    assert response['statusCode'] == HTTPStatus.OK
    body = json.loads(response['body'])
    assert "download_url" in body


@responses.activate
@pytest.mark.usefixtures("create_s3_bucket")
def test_get_zip_for_control_outputs__no_zip_in_s3():
    tenant_id = str(uuid4())
    jit_event_id = str(uuid4())
    execution_id = str(uuid4())

    event = _get_mock_event(tenant_id, jit_event_id, execution_id)
    response = zipball(event, {})  # type: ignore
    assert response['statusCode'] == HTTPStatus.NOT_FOUND

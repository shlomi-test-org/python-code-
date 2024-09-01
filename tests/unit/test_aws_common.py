import os
from unittest.mock import patch
from uuid import uuid4

import pytest
from jit_utils.jit_clients.authentication_service.client import AuthenticationService
from jit_utils.models.asset.entities import AssetStatus

from src.lib.aws_common import assume_role
from src.lib.aws_common import AwsLogicError
from src.lib.aws_common import get_aws_credentials
from src.lib.aws_common import get_job_definition
from src.lib.aws_common import send_installation_partial_update_event_error
from src.lib.aws_common import update_asset_status
from src.lib.constants import AWS_COMMON_SESSION_SECONDS_DURATION
from src.lib.constants import AWS_JIT_ROLE
from src.lib.models.tenants_models import InstallationStatus


class MockStsClient:
    access_key = 'mock_access_key'
    secret_access_key = 'mock_secret_access_key'
    session_token = 'mock_session_token'
    called_args = None

    def assume_role(self, *args, **kwargs):
        self.called_args = args, kwargs
        return {
            'Credentials': {
                'AccessKeyId': self.access_key,
                'SecretAccessKey': self.secret_access_key,
                'SessionToken': self.session_token,
            }
        }


def test_get_aws_credentials():
    sts_assume_role_response = {'Credentials': {
        'AccessKeyId': '_access_key_',
        'SecretAccessKey': '_secret_key_',
        'SessionToken': '_session_key_'
    }}
    response = get_aws_credentials(sts_assume_role_response)
    assert response == {'aws_access_key_id': '_access_key_',
                        'aws_secret_access_key': '_secret_key_',
                        'aws_session_token': '_session_key_'}


@patch('src.lib.aws_common.EventsClient.put_event')
def test_send_installation_partial_update_event_error(mock_put_event):
    tenant_id = str(uuid4())
    installation_id = str(uuid4())
    external_id = str(uuid4())
    response = send_installation_partial_update_event_error(tenant_id=tenant_id, installation_id=installation_id,
                                                            external_id=external_id)
    assert response.status == InstallationStatus.ERROR
    assert response.status_details['error_type'] == 'ACCESS_FAILURE'
    assert mock_put_event.called


def test_assume_role_with_no_given_specific_params(mocker):
    tenant_id = str(uuid4())
    installation_id = str(uuid4())
    asset_id = str(uuid4())
    assume_role_id = str(uuid4())
    mock_client = MockStsClient()
    mocker.patch('boto3.client', return_value=mock_client)
    update_asset_status = mocker.patch('src.lib.aws_common.update_asset_status')
    mock_calculate_external_id = mocker.patch('src.lib.aws_common._calculate_external_id', return_value='external_id')

    response = assume_role(tenant_id, installation_id, asset_id, assume_role_id)
    assert mock_calculate_external_id.called
    assert response == {'aws_access_key_id': MockStsClient.access_key,
                        'aws_secret_access_key': MockStsClient.secret_access_key,
                        'aws_session_token': MockStsClient.session_token, 'region_name': os.getenv('AWS_REGION_NAME')}
    assert mock_client.called_args[1] == {'DurationSeconds': AWS_COMMON_SESSION_SECONDS_DURATION,
                                          'ExternalId': 'external_id',
                                          'RoleArn': f'arn:aws:iam::{assume_role_id}:role/{AWS_JIT_ROLE}',
                                          'RoleSessionName': AWS_JIT_ROLE}
    assert update_asset_status.called
    assert update_asset_status.call_args[0][2] == AssetStatus.CONNECTED


def test_assume_role_with_credential_parameters(mocker):
    tenant_id = str(uuid4())
    installation_id = str(uuid4())
    asset_id = str(uuid4())
    assume_role_id = str(uuid4())
    external_id = str(uuid4())
    aws_jit_role = str(uuid4())

    mock_client = MockStsClient()
    mocker.patch('boto3.client', return_value=mock_client)
    update_asset_status = mocker.patch('src.lib.aws_common.update_asset_status')

    mock_calculate_external_id = mocker.patch('src.lib.aws_common._calculate_external_id')

    response = assume_role(tenant_id, installation_id, asset_id, assume_role_id, external_id, aws_jit_role)
    assert not mock_calculate_external_id.called

    assert response == {'aws_access_key_id': MockStsClient.access_key,
                        'aws_secret_access_key': MockStsClient.secret_access_key,
                        'aws_session_token': MockStsClient.session_token,
                        'region_name': os.getenv('AWS_REGION_NAME')}
    assert mock_client.called_args[1] == {'DurationSeconds': AWS_COMMON_SESSION_SECONDS_DURATION,
                                          'ExternalId': external_id,
                                          'RoleArn': f'arn:aws:iam::{assume_role_id}:role/{aws_jit_role}',
                                          'RoleSessionName': aws_jit_role}
    assert update_asset_status.called
    assert update_asset_status.call_args[0][2] == AssetStatus.CONNECTED


def test_assume_role_on_exception(mocker):
    mocked_update_asset_status = mocker.patch('src.lib.aws_common.update_asset_status')
    mocked_send_installation_partial_update_event_error = mocker.patch(
        target='src.lib.aws_common.send_installation_partial_update_event_error'
    )
    with pytest.raises(Exception):
        assume_role('', '', '', '')

    assert mocked_update_asset_status.called
    assert mocked_send_installation_partial_update_event_error.called


def test_update_asset_status_without_status_details(mocker):
    mock_get_api_token = mocker.patch.object(
        AuthenticationService, "get_api_token", return_value=uuid4().hex
    )

    mock_update_asset = mocker.patch('src.lib.aws_common.AssetService.update_asset')
    tenant_id = str(uuid4())
    asset_id = str(uuid4())
    status = AssetStatus.CONNECTED
    update_asset_status(tenant_id, asset_id, status)
    assert mock_get_api_token.called
    assert mock_update_asset.called
    assert mock_update_asset.call_args[0][0] == tenant_id
    assert mock_update_asset.call_args[0][1] == asset_id

    update_asset_request = mock_update_asset.call_args[0][2]
    assert update_asset_request.status == status
    assert update_asset_request.status_details is None


def test_update_asset_status_with_status_details(mocker):
    mock_get_api_token = mocker.patch.object(
        AuthenticationService, "get_api_token", return_value=uuid4().hex
    )

    mock_update_asset = mocker.patch('src.lib.aws_common.AssetService.update_asset')
    tenant_id = str(uuid4())
    asset_id = str(uuid4())
    status = AssetStatus.FAILED
    status_details = 'status_details error'
    update_asset_status(tenant_id, asset_id, status, status_details)
    assert mock_get_api_token.called
    assert mock_update_asset.called
    assert mock_update_asset.call_args[0][0] == tenant_id
    assert mock_update_asset.call_args[0][1] == asset_id

    update_asset_request = mock_update_asset.call_args[0][2]
    assert update_asset_request.status == status
    assert update_asset_request.status_details is status_details


@pytest.mark.parametrize("image, expected", [
    ["121169888995.dkr.ecr.us-east-1.amazonaws.com/github-branch-protection:main", "github-branch-protection__main"],
    ["121169888995.dkr.ecr.us-east-1.amazonaws.com/some_image:latest", "some_image__latest"],
    ["ghcr.io/jitsecurity-controls/control-mfa-github-alpine:latest", "control-mfa-github-alpine__latest"],
])
def test_get_job_definition(image, expected):
    output = get_job_definition(image)
    assert output == expected


@pytest.mark.parametrize("image, message", [
    [
        "github-branch-protection:main",
        "Illegal image ecr path github-branch-protection:main, no ECR ARN",
    ],
    [
        "121169888995.dkr.ecr.us-east-1.amazonaws.com/some_image",
        "Illegal image ecr path 121169888995.dkr.ecr.us-east-1.amazonaws.com/some_image, no tag",
    ],
    [
        "abc/inner/",
        "Illegal image ecr path abc/inner/, no tag",
    ],
    [
        "abc/inner/aaaaa",
        "Illegal image ecr path abc/inner/aaaaa, no tag",
    ],
    [
        "aaa",
        "Illegal image ecr path aaa, no ECR ARN",
    ],
])
def test_get_job_definition__illegal_image(image, message):
    with pytest.raises(AwsLogicError) as exc:
        get_job_definition(image)

    assert exc.value.args[0] == message

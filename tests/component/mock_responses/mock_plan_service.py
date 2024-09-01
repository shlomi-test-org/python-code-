import responses
from jit_utils.service_discovery import get_service_url


def mock_get_integration_file_for_tenant_api():
    responses.add(
        responses.GET,
        f"{get_service_url('plan-service')['service_url']}/integration-file",
        json={
            'content': {
                'aws': [
                    {
                      'account_id': '123456789012',
                      'regions': ['eu-west-1', 'eu-west-2'],
                    },
                ]
            }
        },
        status=200,
    )

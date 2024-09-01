import responses
from jit_utils.service_discovery import get_service_url


def mock_get_internal_token_api():
    responses.add(
        responses.POST,
        f"{get_service_url('authentication-service')['service_url']}/token/internal",
        json="mocked_token",
        status=200,
    )

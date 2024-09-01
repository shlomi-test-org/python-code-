import responses

from tests.common import DUMMY_BASE_URL


def mock_get_internal_token_api():
    responses.add(
        responses.POST,
        f"{DUMMY_BASE_URL}/authentication/token/internal",
        json="mocked_token",
        status=200,
    )

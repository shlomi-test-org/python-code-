import responses


def mock_get_internal_token_api():
    responses.add(responses.POST, 'https://api.dummy.jit.io/authentication/token/internal', json='token',
                  status=200)

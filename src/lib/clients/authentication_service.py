from jit_utils.requests import get_session
from jit_utils.logger import logger
from jit_utils.service_discovery import get_service_url

from src.lib.awsv4_sign_requests import sign
from src.lib.endpoints import AUTH_SERVICE_GENERATE_LAMBDA_API_TOKEN


class AuthenticationService:
    def __init__(self) -> None:
        self.service = get_service_url('authentication-service')['service_url']

    def get_api_token(self, tenant_id: str) -> str:
        logger.info(f'Getting an api token from authentication service for tenant {tenant_id}')
        url = AUTH_SERVICE_GENERATE_LAMBDA_API_TOKEN.format(authentication_service=self.service)
        response = get_session(allow_post_retry=True).post(url=url, auth=sign(url), json={'tenant_id': tenant_id})
        response.raise_for_status()  # We expect a 201 response

        return response.json()

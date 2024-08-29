from jit_utils.models.github.github_status import GithubStatusAlert
from jit_utils.requests import get_session

from jit_utils.logger import logger
from jit_utils.service_discovery import get_service_url

from src.lib.clients import AuthenticationService
from src.lib.endpoints import GET_GITHUB_STATUS_URL


class GithubServiceClient:
    def __init__(self) -> None:
        self.service = get_service_url('github-service')['service_url']

    def get_latest_github_status_alert(self, tenant_id: str) -> GithubStatusAlert:
        logger.info("Getting github status")
        url = GET_GITHUB_STATUS_URL.format(base=self.service)
        api_token = AuthenticationService().get_api_token(tenant_id)
        response = get_session().get(url=url, headers={'Authorization': f'Bearer {api_token}'})
        response.raise_for_status()
        logger.info(f"Got response: {response.json()=}")
        alert = GithubStatusAlert(**response.json())
        return alert

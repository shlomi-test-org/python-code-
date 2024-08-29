from typing import Union

from jit_utils.logger import logger
from jit_utils.models.execution import DispatchExecutionEvent
from jit_utils.models.execution import GithubOidcDispatchExecutionEvent
from jit_utils.requests import get_session
from jit_utils.service_discovery import get_service_url

from src.lib.awsv4_sign_requests import sign
from src.lib.constants import TENANT_HEADER, MAX_API_GATEWAY_TIMEOUT_SECONDS
from src.lib.endpoints import GITHUB_SERVICE_DISPATCH

GITHUB_SERVICE = None


class GithubService:
    def __init__(self):
        self.service = get_service_url('github-service')['service_url']

    def dispatch(self, tenant_id: str, event: Union[DispatchExecutionEvent, GithubOidcDispatchExecutionEvent]) -> None:
        logger.info("Dispatching execution to github workflows")
        url = GITHUB_SERVICE_DISPATCH.format(github_service=self.service)
        response = get_session().post(
            url=url,
            auth=sign(url),
            headers={TENANT_HEADER: tenant_id},
            data=event.json(exclude_none=True),
            timeout=MAX_API_GATEWAY_TIMEOUT_SECONDS,
        )

        logger.info(f"called github dispatch {response=}")
        response.raise_for_status()

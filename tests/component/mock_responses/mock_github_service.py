from typing import Optional

import responses
from jit_utils.models.github.github_api_objects import GetVendorExecutionFailureResponse
from jit_utils.service_discovery import get_service_url

from src.lib.endpoints import GITHUB_SERVICE_DISPATCH


def mock_get_github_status_api(app_id: str, installation_id: str, token: Optional[str]) -> None:
    url = f"http://github-service/app/{app_id}/installation/{installation_id}/token"
    if token:
        responses.add(responses.GET, url, json={"token": token}, status=200)
    else:
        responses.add(responses.GET, url, status=500)


def mock_github_service_dispatch() -> None:
    responses.add(
        method=responses.POST,
        url=GITHUB_SERVICE_DISPATCH.format(
            github_service=get_service_url("github-service")["service_url"]
        ),
        json="api_token",
    )


def mock_get_vendor_failure(execution_id: str, failure_reason: GetVendorExecutionFailureResponse) -> None:
    url = f"http://github-service/execution/{execution_id}/failure"
    responses.add(responses.GET, url, json=failure_reason.dict(), status=200)

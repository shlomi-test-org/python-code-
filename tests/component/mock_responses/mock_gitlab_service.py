from http import HTTPStatus
from typing import List, Optional

import responses

from jit_utils.models.execution import Execution
from jit_utils.service_discovery import get_service_url
from jit_utils.models.gitlab.requests_models import GitlabDispatchResponse
from jit_utils.jit_clients.gitlab_service.endpoints import DISPATCH_ENDPOINT


def mock_gitlab_service_dispatch(executions: Optional[List[Execution]]) -> None:
    if executions:
        responses.add(
            method=responses.POST,
            url=DISPATCH_ENDPOINT.format(
                gitlab_service=get_service_url("gitlab-service")["service_url"]
            ),
            json=GitlabDispatchResponse(pipeline_id=0).dict(),
        )
    else:
        responses.add(
            method=responses.POST,
            url=DISPATCH_ENDPOINT.format(
                gitlab_service=get_service_url("gitlab-service")["service_url"]
            ),
            status=HTTPStatus.INTERNAL_SERVER_ERROR,
        )

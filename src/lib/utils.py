import json
from functools import lru_cache
from typing import Any, Union, Dict

from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from pydantic.main import BaseModel

from src.lib.clients import AuthenticationService


class JSONEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, BaseModel):
            return json.loads(obj.json())

        return json.JSONEncoder.default(self, obj)


def get_old_runner_format(runner: Union[str, Dict]) -> str:
    # This function getting the old runner format for supporting the old runner format
    # getting the old string from the RunnerConfig, should be removed after all controls are using context.
    if isinstance(runner, Dict):
        return runner["type"]
    return runner


def get_tenant_id_from_api_gw_request(event: APIGatewayProxyEvent) -> str:
    return event.request_context.authorizer['tenant_id']  # type: ignore


@lru_cache()
def get_tenant_api_token(tenant_id: str) -> str:
    return AuthenticationService().get_api_token(tenant_id)

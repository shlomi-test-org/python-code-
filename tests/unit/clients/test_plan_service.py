import json

import pytest
import responses
from requests import Response

from src.lib.clients import PlanService
from src.lib.constants import ITEMS


class RequestsResponseMock(Response):
    def __init__(self, status_code, content):
        super().__init__()
        self.status_code = status_code
        self._content = json.dumps(content).encode("utf-8")


@responses.activate()
def test_get_plan_items_configurations_by_env_trigger() -> None:
    expected_res = [{'plan_item_slug': 'plan_item_slug'}]
    responses.add(responses.GET, 'http://plan-service/plan-items-configurations/trigger/trigger/tag/env',
                  json=expected_res)
    client = PlanService()

    response = client.get_plan_items_configurations_by_env_trigger('env', 'trigger', 'api_token', 'tenant_id')
    assert response == expected_res


@responses.activate()
def test_get_plan_items_configurations_by_env_trigger__failure_response() -> None:
    client = PlanService()
    responses.add(responses.GET, 'http://plan-service/plan-items-configurations/trigger/trigger/tag/env',
                  status=400)
    response = client.get_plan_items_configurations_by_env_trigger('env', 'trigger', 'api_token', 'tenant_id')
    assert response == []


@responses.activate()
def test_get_full_plan_success() -> None:
    expected_response = {ITEMS: {'plan_item_slug': 'plan_item_slug'}}
    responses.add(responses.GET, 'http://plan-service/jit-plan/content-full', json=expected_response)
    plan_service_client = PlanService()
    res = plan_service_client.get_full_plan(tenant_id="tenant_id",
                                            api_token="api_token")

    assert res == expected_response


@responses.activate()
def test_get_full_plan__success__old_api() -> None:
    expected_response = {ITEMS: {'plan_item_slug': 'workflow'}}
    responses.add(responses.GET, 'http://plan-service/jit-plan/content-full', json=expected_response)
    plan_service_client = PlanService()
    res = plan_service_client.get_full_plan(tenant_id="tenant_id", api_token="api_token")
    assert res == expected_response


@responses.activate()
def test_get_full_plan_failure() -> None:
    responses.add(responses.GET, 'http://plan-service/jit-plan/content-full', status=500)
    with pytest.raises(Exception):
        plan_service_client = PlanService()
        plan_service_client.get_full_plan(tenant_id="tenant_id", api_token="api_token")


@pytest.mark.parametrize("expected_response, status_code", [
    ({"content": {"drata": {"workspace": "Drata Partners", "user_email": "jit@dratapartners.com"}}}, 200),
    ({"content": None}, 200),
    ({}, 404),
])
@responses.activate()
def test_get_integration_file_for_tenant(expected_response, status_code) -> None:
    responses.add(responses.GET, 'http://plan-service/integration-file', json=expected_response, status=status_code)
    plan_service_client = PlanService()
    res = plan_service_client.get_integration_file_for_tenant(tenant_id="tenant_id", api_token="api_token")
    expected = (expected_response['content'] or {}) if status_code == 200 else {}
    assert res == expected

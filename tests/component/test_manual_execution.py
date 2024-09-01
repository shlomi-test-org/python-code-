import json
from http import HTTPStatus
from typing import Dict
from uuid import uuid4

import pytest
import responses
from jit_utils.aws_clients.events import EventBridgeClient
from jit_utils.event_models import ManualExecutionJitEvent
from jit_utils.lambda_decorators import RateLimiter
from jit_utils.models.common.responses import ErrorResponse
from jit_utils.models.trigger.requests import AssetTriggerFilters, ManualExecutionRequest, AssetTriggerId
from jit_utils.models.trigger.responses import ManualExecutionResponse

from src.handlers.manual_execution import handler
from src.lib.models.asset import Asset
from tests.component.utils.mock_responses.mock_asset_service import mock_get_assets_api
from tests.component.utils.mock_responses.mock_authentication_service import mock_get_internal_token_api
from tests.component.utils.mock_responses.mock_plan_service_api import mock_get_plan_api
from tests.component.utils.mocks.mock_plan import MOCK_PLAN

MOCK_TENANT_ID = str(uuid4())


def wrap_http_request(request: ManualExecutionRequest, tenant_id: str) -> Dict:
    return {
        "httpMethod": "POST",
        "body": request.json(),
        "requestContext": {
            "authorizer": {
                "tenant_id": tenant_id,
            },
        },
    }


def api_event(request: ManualExecutionRequest, tenant_id: str) -> Dict:
    return {
        'body': request.json(),
        'httpMethod': 'GET',
        'headers': {
            'Authorization': 'Bearer ************',
            'Host': 'api.jit.io',
            'Tenant': tenant_id
        },
        'requestContext': {
            'resourceId': 'ofrydy',
            'authorizer': {
                'tenant_id': MOCK_TENANT_ID,
                'roles': "['admin']",
                'token': 'woot'
            },
            'resourcePath': '/pipelines',
            'httpMethod': 'GET',
            'extendedRequestId': 'GgTjDEnkIAMFiZg=',
            'requestTime': '14/Jun/2023:10:41:10 +0000',
            'path': '/pipeline/pipelines',
            'accountId': '899025839375',
            'protocol': 'HTTP/1.1',
            'stage': 'prod',
            'domainPrefix': 'api',
            'requestTimeEpoch': 1686739270488,
            'requestId': '90cf91bf-e702-4ed5-b05e-9fb8ce6c691f',
            'identity': {
                'cognitoIdentityPoolId': None,
            },
            'domainName': 'api.jit.io',
            'apiId': 'demds5s377'
        },
        'resource': '/pipelines',
        'path': '/pipeline/pipelines'
    }


"""
Here we create the tenant setup:
    * 5 assets
    * asset[0] and asset[1] has the same name but different type
    * plan item item-branch-protection-scm has no manual trigger
"""
test_asset = Asset(
    asset_type="repo",
    asset_id="asset-id-1",
    tenant_id="tenant-id-1",
    vendor="vendor-1",
    owner="owner-1",
    asset_name="asset-name-1",
    is_active=True,
    created_at="2021-01-01T00:00:00Z",
    modified_at="2021-01-01T00:00:00Z",
)
all_assets = [
    test_asset,
    test_asset.copy(update={"asset_type": "org", "asset_id": "asset-id-2"}),
    test_asset.copy(update={"asset_name": "asset-name-3", "asset_id": "asset-id-3"}),
    test_asset.copy(update={"asset_name": "asset-name-4", "asset_id": "asset-id-4"}),
    test_asset.copy(update={"asset_name": "asset-name-5", "asset_id": "asset-id-5"}),
]
plan = MOCK_PLAN.copy()
content = plan["items"]["item-branch-protection-scm"]["workflow_templates"][0]["content"]
content_with_no_manual_trigger = content.replace("  - manual_execution\n", "")
plan["items"]["item-branch-protection-scm"]["workflow_templates"][0]["content"] = content_with_no_manual_trigger


class TestManualExecution:
    @staticmethod
    def setup_method():
        mock_get_assets_api(assets=[asset.dict() for asset in all_assets])
        mock_get_internal_token_api()
        mock_get_plan_api(plan=plan)

    @responses.activate
    def test_manual_execution__input_type_asset_trigger_filters__valid_request(self, mocker):
        put_event_mock = mocker.patch.object(EventBridgeClient, "put_event")
        mock_rate_limiter = mocker.MagicMock(spec=RateLimiter)
        mocker.patch('jit_utils.lambda_decorators.rate_limiter.RateLimiter', return_value=mock_rate_limiter)
        request = ManualExecutionRequest(
            plan_item_slug="item-code-vulnerability",
            assets=[
                AssetTriggerFilters(name=all_assets[2].asset_name),
                AssetTriggerFilters(name=all_assets[3].asset_name),
                AssetTriggerFilters(name=all_assets[4].asset_name),
            ],
        )
        event = api_event(request, MOCK_TENANT_ID)
        response = handler(event, {})

        # Check that update_rate_limit_counter method was called
        mock_rate_limiter.update_rate_limit_counter.assert_called_once()
        assert response["statusCode"] == HTTPStatus.CREATED
        assert put_event_mock.call_count == 1
        assert json.loads(put_event_mock.call_args[1]["detail"]) == ManualExecutionJitEvent(
            tenant_id=MOCK_TENANT_ID,
            jit_event_id=ManualExecutionResponse(**json.loads(response["body"])).jit_event_id,
            asset_ids_filter=[all_assets[2].asset_id, all_assets[3].asset_id, all_assets[4].asset_id],
            plan_item_slug="item-code-vulnerability",
        ).dict()

    @responses.activate
    @pytest.mark.parametrize("request_object, message", [
        [
            ManualExecutionRequest(
                plan_item_slug="",
                assets=[
                    AssetTriggerFilters(name="not-exists-asset"),
                ],
            ),
            "Plan item slug is mandatory",
        ],
        [
            ManualExecutionRequest(
                plan_item_slug="item-code-vulnerability",
                assets=[],
            ),
            "Assets not specified",
        ],
        [
            ManualExecutionRequest(
                plan_item_slug="item-code-vulnerability",
                assets=[
                    AssetTriggerFilters(name="not-exists-asset"),
                ],
            ),
            "Asset with name not-exists-asset does not exist",
        ],
        [
            ManualExecutionRequest(
                plan_item_slug="item-code-vulnerability",
                assets=[
                    AssetTriggerFilters(name=all_assets[2].asset_name, type="gcp_account"),
                ],
            ),
            f"Asset with name {all_assets[2].asset_name} and type gcp_account does not exist",
        ],
        [
            ManualExecutionRequest(
                plan_item_slug="item-code-vulnerability",
                assets=[
                    AssetTriggerFilters(name=all_assets[0].asset_name, type="api"),
                ],
            ),
            f"Asset with name {all_assets[0].asset_name} and type api does not exist",
        ],
        [
            ManualExecutionRequest(
                plan_item_slug="item-code-vulnerability",
                assets=[
                    AssetTriggerFilters(name=all_assets[0].asset_name),
                ],
            ),
            (
                    f"Found more than one asset with name={all_assets[0].asset_name}. "
                    "Please specify a type from "
                    "(\'repo\', \'org\', \'aws_account\', 'gcp_account', 'azure_account', \'web\', \'api\')"
            )
        ],
        [
            ManualExecutionRequest(
                plan_item_slug="item-not-in-plan",
                assets=[
                    AssetTriggerFilters(name=all_assets[2].asset_name),
                ],
            ),
            "Plan item item-not-in-plan is inactive",
        ],
        [
            ManualExecutionRequest(
                plan_item_slug="item-branch-protection-scm",
                assets=[
                    AssetTriggerFilters(name=all_assets[2].asset_name),
                    AssetTriggerFilters(name=all_assets[3].asset_name),
                    AssetTriggerFilters(name=all_assets[4].asset_name),
                ],
            ),
            "Plan item has no workflow with manual (api) trigger",
        ],
        [
            ManualExecutionRequest(
                plan_item_slug="item-web-app-scanner",
                assets=[
                    AssetTriggerFilters(name=all_assets[2].asset_name),
                    AssetTriggerFilters(name=all_assets[3].asset_name),
                    AssetTriggerFilters(name=all_assets[4].asset_name),
                ],
            ),
            (
                    "Plan item item-web-app-scanner has no workflows to execute for assets="
                    f"['{all_assets[2].asset_name}', '{all_assets[3].asset_name}', '{all_assets[4].asset_name}']"
            ),
        ],
        [
            ManualExecutionRequest(
                plan_item_slug="item-web-app-scanner",
                assets=[
                    AssetTriggerFilters(name=all_assets[2].asset_name),
                ],
            ),
            f"Plan item item-web-app-scanner has no workflows to execute for asset={all_assets[2].asset_name}"
        ],
    ])
    def test_manual_execution__input_type_asset_trigger_filters__bad_request(self, mocker, request_object, message):
        put_event_mock = mocker.patch.object(EventBridgeClient, "put_event")
        response = handler(wrap_http_request(request_object, MOCK_TENANT_ID), {})
        assert response["statusCode"] == HTTPStatus.BAD_REQUEST
        assert ErrorResponse(**json.loads(response["body"])).message == message
        assert put_event_mock.call_count == 0

    @responses.activate
    def test_manual_execution__input_type_asset_trigger_id__valid_request(self, mocker):
        put_event_mock = mocker.patch.object(EventBridgeClient, "put_event")
        mock_rate_limiter = mocker.MagicMock(spec=RateLimiter)
        mocker.patch('jit_utils.lambda_decorators.rate_limiter.RateLimiter', return_value=mock_rate_limiter)
        request = ManualExecutionRequest(
            plan_item_slug="item-code-vulnerability",
            assets=[
                AssetTriggerId(id=all_assets[2].asset_id),
                AssetTriggerId(id=all_assets[3].asset_id),
                AssetTriggerId(id=all_assets[4].asset_id),
            ],
        )
        event = api_event(request, MOCK_TENANT_ID)
        response = handler(event, {})

        # Check that update_rate_limit_counter method was called
        mock_rate_limiter.update_rate_limit_counter.assert_called_once()
        assert response["statusCode"] == HTTPStatus.CREATED
        assert put_event_mock.call_count == 1
        assert json.loads(put_event_mock.call_args[1]["detail"]) == ManualExecutionJitEvent(
            tenant_id=MOCK_TENANT_ID,
            jit_event_id=ManualExecutionResponse(**json.loads(response["body"])).jit_event_id,
            asset_ids_filter=[all_assets[2].asset_id, all_assets[3].asset_id, all_assets[4].asset_id],
            plan_item_slug="item-code-vulnerability",
        ).dict()

    @responses.activate
    @pytest.mark.parametrize("request_object, message", [
        [
            ManualExecutionRequest(
                plan_item_slug="",
                assets=[
                    AssetTriggerId(id="not-exists-asset"),
                ],
            ),
            "Plan item slug is mandatory",
        ],
        [
            ManualExecutionRequest(
                plan_item_slug="item-code-vulnerability",
                assets=[],
            ),
            "Assets not specified",
        ],
        [
            ManualExecutionRequest(
                plan_item_slug="item-code-vulnerability",
                assets=[
                    AssetTriggerId(id="not-exists-asset"),
                ],
            ),
            "Asset with id not-exists-asset does not exist",
        ],
        [
            ManualExecutionRequest(
                plan_item_slug="item-branch-protection-scm",
                assets=[
                    AssetTriggerId(id=all_assets[2].asset_id),
                    AssetTriggerId(id=all_assets[3].asset_id),
                    AssetTriggerId(id=all_assets[4].asset_id),
                ],
            ),
            "Plan item has no workflow with manual (api) trigger",
        ],
        [
            ManualExecutionRequest(
                plan_item_slug="item-web-app-scanner",
                assets=[
                    AssetTriggerId(id=all_assets[2].asset_id),
                    AssetTriggerId(id=all_assets[3].asset_id),
                    AssetTriggerId(id=all_assets[4].asset_id),
                ],
            ),
            (
                    "Plan item item-web-app-scanner has no workflows to execute for assets="
                    f"['{all_assets[2].asset_name}', '{all_assets[3].asset_name}', '{all_assets[4].asset_name}']"
            ),
        ],
        [
            ManualExecutionRequest(
                plan_item_slug="item-web-app-scanner",
                assets=[
                    AssetTriggerId(id=all_assets[2].asset_id),
                ],
            ),
            f"Plan item item-web-app-scanner has no workflows to execute for asset={all_assets[2].asset_name}"
        ],
    ])
    def test_manual_execution__input_type_asset_trigger_id__bad_request(self, mocker, request_object, message):
        put_event_mock = mocker.patch.object(EventBridgeClient, "put_event")
        response = handler(wrap_http_request(request_object, MOCK_TENANT_ID), {})
        assert response["statusCode"] == HTTPStatus.BAD_REQUEST
        assert ErrorResponse(**json.loads(response["body"])).message == message
        assert put_event_mock.call_count == 0

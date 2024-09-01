import os
import responses
from http import HTTPStatus

from responses import matchers

from src.lib.endpoints import PLAN_SERVICE_GET_PLAN_ITEMS_CONFIGURATIONS, PLAN_SERVICE_GET_APPLICATIONS_CONFIGURATIONS
from tests.common import DUMMY_BASE_URL
from tests.component.utils.mocks.mock_plan import MOCK_PLAN
from tests.component.utils.mocks.mocks import MOCK_JIT_CENTRALIZED_REPO_FILES_METADATA
from typing import List


def mock_get_centralized_repo_files_metadata(tenant_id: str) -> responses.BaseResponse:
    url = f"https://{os.environ['API_HOST']}/plan/centralized-repo-files-metadata/tenant-id/{tenant_id}"
    resp = responses.add(
        responses.GET,
        url,
        json=MOCK_JIT_CENTRALIZED_REPO_FILES_METADATA.dict(),
        status=HTTPStatus.OK,
    )
    return resp


def mock_get_plan_api(plan: dict = MOCK_PLAN):
    responses.add(
        responses.GET,
        f"{DUMMY_BASE_URL}/plan/jit-plan/content-full",
        json=plan,
        status=200,
    )


def mock_get_plan_item_configurations(plan_item_configurations: List[dict] = [], tag: str = "staging"):
    url = PLAN_SERVICE_GET_PLAN_ITEMS_CONFIGURATIONS.substitute(
        base=f"{DUMMY_BASE_URL}/plan",
        trigger="deployment",
        tag=tag,
    )
    responses.add(
        responses.GET,
        url,
        json=plan_item_configurations,
        status=200,
    )


def mock_get_application_configurations(plan_item_configurations: List[dict] = [], tag: str = "staging"):
    url = PLAN_SERVICE_GET_APPLICATIONS_CONFIGURATIONS.substitute(
        base=f"{DUMMY_BASE_URL}/plan",
        trigger="deployment",
        tag=tag,
    )
    responses.add(
        responses.GET,
        url,
        json=plan_item_configurations,
        status=200,
    )


def mock_get_configuration_file_api(configuration_file: dict = {}):
    responses.add(
        responses.GET,
        f"{DUMMY_BASE_URL}/plan/configuration-file",
        json={"content": configuration_file},
        status=200,
    )


def mock_get_integration_file_api(integration_file: dict = {}):
    responses.add(
        responses.GET,
        f"{DUMMY_BASE_URL}/plan/integration-file",
        json={"content": integration_file},
        status=200,
    )


def mock_get_scopes_api(workflow_slug: str, job_name: str, plan_item_slugs: List[str]):
    params = {"workflow_slug": workflow_slug, "job_name": job_name}
    if plan_item_slugs and plan_item_slugs[0] in ["item-aws-ftr-secret-detection", "item-secret-detection"]:
        plan_item_slugs = ["item-aws-ftr-secret-detection", "item-secret-detection"]

    responses.add(
        responses.GET,
        f"{DUMMY_BASE_URL}/plan/template/scopes",
        match=[matchers.query_param_matcher(params)],
        json=[
            {
                "scopes": {},
                "plan_item_slug": plan_item_slug,
                "workflow_slug": workflow_slug,
                "job_name": job_name,
            }
            for plan_item_slug in plan_item_slugs
        ],
        status=HTTPStatus.OK,
    )

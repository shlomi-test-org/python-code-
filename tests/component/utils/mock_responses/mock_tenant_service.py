import responses
from typing import List

from jit_utils.jit_clients.tenant_service.endpoints import GET_PREFERENCE, GET_PREFERENCES

from tests.common import DUMMY_BASE_URL


def mock_get_github_installations_api(installations: List[dict] = []):
    responses.add(
        responses.GET,
        f"{DUMMY_BASE_URL}/tenant/vendor/github/installation",
        json=installations,
        status=200,
    )


def mock_get_all_installations_api(installations: List[dict] = []):
    responses.add(
        responses.GET,
        f"{DUMMY_BASE_URL}/tenant/installations",
        json=installations,
        status=200,
    )


def mock_get_tenant_by_installation_id_api(tenant: dict, vendor: str, installation_id: str):
    responses.add(
        responses.GET,
        f"{DUMMY_BASE_URL}/tenant/vendor/{vendor}/installation/{installation_id}",
        json=tenant,
        status=200,
    )


def mock_get_pr_check_preference_api(preference: dict, status_code: int = 200):
    url = GET_PREFERENCE.format(base_url=f"{DUMMY_BASE_URL}/tenant", preference_type="pr_check")
    responses.add(
        responses.GET,
        url,
        json=preference,
        status=status_code,
    )


def mock_get_preferences_api(preferences: dict, status_code: int = 200):
    url = GET_PREFERENCES.format(base_url=f"{DUMMY_BASE_URL}/tenant")
    responses.add(
        responses.GET,
        url,
        json=preferences,
        status=status_code,
    )


def mock_get_aws_installations_api(installations: List[dict] = []):
    responses.add(
        responses.GET,
        f"{DUMMY_BASE_URL}/tenant/vendor/aws/installation",
        json=installations,
        status=200,
    )


def mock_get_domain_installations_api(installations: List[dict] = []):
    responses.add(
        responses.GET,
        f"{DUMMY_BASE_URL}/tenant/vendor/domain/installation",
        json=installations,
        status=404,
    )

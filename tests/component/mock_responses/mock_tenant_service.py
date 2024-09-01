from typing import List

import responses
from jit_utils.models.tenant.entities import Installation
from jit_utils.service_discovery import get_service_url


def mock_get_installations_by_vendor_api(tenant_id: str, vendor: str):
    url = f"{get_service_url('tenant-service')['service_url']}/vendor/{vendor}/installation"

    installations = [
        Installation(
            installation_id='installation1',
            is_active=True,
            owner='123456789012',
            app_id='app1',
            created_at='2021-01-01T00:00:00.000Z',
            creator='creator1',
            modified_at='2021-01-01T00:00:00.000Z',
            name='installation1',
            tenant_id=tenant_id,
            vendor=vendor,
        ).dict(),
    ]

    responses.add(responses.GET, url, json=installations, status=200)


def mock_get_installations_api(installations: List[Installation]):
    url = f"{get_service_url('tenant-service')['service_url']}/installations"
    responses.add(responses.GET, url, json=[installation.dict() for installation in installations], status=200)

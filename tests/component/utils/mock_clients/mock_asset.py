from typing import List, Optional

import responses
from jit_utils.jit_clients.asset_service.endpoints import ASSET_SERVICE_GET_ALL_ASSETS

from tests.component.utils.get_mocked_asset import get_mocked_asset


def mock_get_asset_api(asset_id: str, tags: Optional[List[dict]] = []) -> None:
    responses.add(responses.GET, f'https://api.dummy.jit.io/asset/asset/{asset_id}',
                  json=get_mocked_asset(tags=tags), status=200)


def mock_get_all_assets(tenant_id: str) -> None:
    responses.add(
        responses.GET,
        ASSET_SERVICE_GET_ALL_ASSETS.format(asset_service="https://api.dummy.jit.io/asset"),
        json=[get_mocked_asset(tenant_id=tenant_id)],
    )

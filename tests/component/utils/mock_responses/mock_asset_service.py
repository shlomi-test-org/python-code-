from typing import List

import responses
from jit_utils.jit_clients.asset_service.endpoints import ASSET_SERVICE_GET_ALL_ASSETS
from jit_utils.models.asset.entities import Asset

from tests.common import DUMMY_BASE_URL


def mock_get_assets_api(assets: List[dict] = []):
    responses.add(
        responses.GET,
        f"{DUMMY_BASE_URL}/asset/",
        json=assets,
        status=200 if assets else 404,
    )


def mock_get_assets_by_ids_api(assets: List[Asset], asset_ids: List[str] = []):
    # Convert asset_ids list to a set for more efficient lookups
    asset_ids_set = set(asset_ids)

    # Filter assets to include only those whose 'asset_id' is in asset_ids_set
    filtered_assets = [asset.dict() for asset in assets if asset.asset_id in asset_ids_set]

    # Convert asset_ids list back to a comma-separated string for the URL
    asset_ids_str = ",".join(asset_ids)

    # Setup the mock response with filtered assets
    responses.add(
        responses.GET,
        f"{DUMMY_BASE_URL}/asset/{asset_ids_str}",
        json=filtered_assets,
        status=200 if filtered_assets else 404,
    )


def mock_get_asset_by_attributes_api(asset: dict):
    responses.add(
        responses.GET,
        ASSET_SERVICE_GET_ALL_ASSETS.format(asset_service=f"{DUMMY_BASE_URL}/asset"),
        json=[asset] if asset.get("is_active") else [],
        status=200 if asset.get("is_active") else 404,
    )

from typing import Optional

import responses
from jit_utils.models.asset.entities import Asset, AssetStatus
from jit_utils.service_discovery import get_service_url


def mock_get_all_assets_api(tenant_id: str):
    responses.add(
        responses.GET,
        f"{get_service_url('asset-service')['service_url']}/",
        json=[
            Asset(
                asset_id='asset1',
                tenant_id=tenant_id,
                asset_type='aws_account',
                vendor='aws',
                owner='123456789012',
                asset_name='asset1',
                aws_account_id='123456789012',
                created_at='2021-01-01T00:00:00.000Z',
                is_active=True,
                is_covered=True,
                modified_at='2021-01-01T00:00:00.000Z',
                status=AssetStatus.CONNECTED,
                aws_jit_role_external_id='external_id',
                aws_jit_role_name='role_name',
            ).dict()
        ],
        status=200,
    )


def mock_get_asset_by_id(asset_id: Optional[str], is_active: bool = True, is_covered: bool = True):
    valid_response_json = Asset(
        asset_id=asset_id,
        tenant_id='tenant_id',
        asset_type='aws_account',
        vendor='aws',
        owner='123456789012',
        asset_name='asset1',
        aws_account_id='123456789012',
        created_at='2021-01-01T00:00:00.000Z',
        is_active=is_active,
        is_covered=is_covered,
        modified_at='2021-01-01T00:00:00.000Z',
        status=AssetStatus.CONNECTED,
        aws_jit_role_external_id='external_id',
        aws_jit_role_name='role_name',
    ).dict()
    not_found_response_json = {
        "message": f"Asset with id {asset_id} not found",
    }
    responses.add(
        responses.GET,
        f"{get_service_url('asset-service')['service_url']}/asset/{asset_id}",
        json=valid_response_json if is_active else not_found_response_json,
        status=200 if is_active else 404,
    )

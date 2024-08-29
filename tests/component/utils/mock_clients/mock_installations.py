import responses
from jit_utils.models.asset.entities import LimitedAsset
from jit_utils.models.tenant.entities import Installation


def mock_get_installations_by_vendor_api(tenant_id: str, vendor: str, installations_count: int = 1):
    url = f'https://api.dummy.jit.io/tenant/vendor/{vendor}/installation'

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
            centralized_repo_asset_id='asset1-id',
            centralized_repo_asset=LimitedAsset(
                asset_id='asset1-id',
                tenant_id=tenant_id,
                asset_type='repo',
                vendor=vendor,
                owner='123456789012',
                is_active=True,
                created_at='2021-01-01T00:00:00.000Z',
                modified_at='2021-01-01T00:00:00.000Z',
                asset_name='asset1',
            )
        ).dict()
        for _ in range(installations_count)]

    responses.add(responses.GET, url, json=installations, status=200)

    return installations

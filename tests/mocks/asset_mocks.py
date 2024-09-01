from jit_utils.models.asset.entities import Asset

from tests.mocks.tenant_mocks import MOCK_TENANT_ID

MOCK_ASSET_ID = "bc4eba46-54cf-44cd-869b-c47daf9b5356"

MOCK_ASSET = Asset(
    asset_id=MOCK_ASSET_ID,
    tenant_id=MOCK_TENANT_ID,
    asset_type="repo",
    vendor="github",
    owner="test_owner",
    asset_name="test_repo",
    is_active=True,
    created_at="2020-01-01T00:00:00Z",
    modified_at="2020-01-02T00:00:00Z",
)

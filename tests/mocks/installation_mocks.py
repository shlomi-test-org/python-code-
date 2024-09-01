from jit_utils.models.oauth.entities import VendorEnum
from jit_utils.models.tenant.entities import Installation

from tests.mocks.asset_mocks import MOCK_ASSET
from tests.mocks.tenant_mocks import MOCK_TENANT_ID

MOCK_INSTALLATION_ID = '686154ad-93a8-43d6-8bdb-34b3145f1537'

MOCK_INSTALLATION = Installation(
    tenant_id=MOCK_TENANT_ID,
    app_id="app_id",
    owner="owner",
    installation_id=MOCK_INSTALLATION_ID,
    is_active=True,
    creator="creator",
    vendor=VendorEnum.GITHUB,
    name="name",
    created_at="created_at",
    modified_at="modified_at",
    centralized_repo_asset=MOCK_ASSET,
)

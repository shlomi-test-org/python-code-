from typing import Dict, List

DEFAULT_ASSET_ID = "12345"
DEFAULT_TENANT_ID = "67890"


def get_mocked_asset(asset_id: str = DEFAULT_ASSET_ID, tenant_id: str = DEFAULT_TENANT_ID,
                     tags: List[Dict] = [], priority_score: int = 0) -> Dict:
    return {
        "asset_id": asset_id,
        "tenant_id": tenant_id,
        "vendor": "github",
        "owner": "John Doe",
        "asset_type": "repo",
        "asset_name": "Server1",
        "is_active": True,
        "is_covered": True,
        "created_at": "",
        "modified_at": "",
        "tags": tags,
        "priority_score": priority_score,
    }

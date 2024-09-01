from typing import Dict
from typing import Optional

from src.lib.aws_common import assume_role


def get_tenant_aws_credentials(tenant_id, installation_id, asset_id: str, assume_role_id,
                               aws_external_id: Optional[str] = None,
                               aws_jit_role_name: Optional[str] = None) -> Dict:
    assumed_role = assume_role(tenant_id, installation_id, asset_id, assume_role_id, aws_external_id, aws_jit_role_name)
    return assumed_role

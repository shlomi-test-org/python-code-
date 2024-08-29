from typing import List

from jit_utils.models.tenant.entities import Installation

from src.lib.constants import GITHUB, GITLAB


def has_valid_scm_installation(installations: List[Installation]) -> bool:
    for installation in installations:
        # verify that the installation SCM and is active and has a centralized repo asset
        if installation.vendor in (GITHUB, GITLAB) and installation.is_active and (
                installation.centralized_repo_asset and installation.centralized_repo_asset.asset_name):
            return True
    return False

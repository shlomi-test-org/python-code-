from typing import List

import pytest
from jit_utils.models.tenant.entities import Installation

from src.lib.constants import GITHUB, GITLAB, AWS
from src.lib.cores.jit_event_handlers.scm_validation import has_valid_scm_installation
from tests.common import InstallationFactory, LimitedAssetFactory


@pytest.mark.parametrize("installations, is_valid", [
    pytest.param([], False, id="No installations"),
    pytest.param([InstallationFactory.build(vendor=AWS, is_active=False, centralized_repo_asset=None)], False,
                 id="No SCM installation"),
    pytest.param([InstallationFactory.build(vendor=GITHUB, is_active=False, centralized_repo_asset=None)], False,
                 id="Not active SCM installation"),
    pytest.param([InstallationFactory.build(vendor=GITHUB, is_active=True, centralized_repo_asset=None)], False,
                 id="SCM installation without centralized repo asset"),
    pytest.param([InstallationFactory.build(vendor=GITHUB, is_active=True,
                                            centralized_repo_asset=LimitedAssetFactory.build(asset_name="Asset"))],
                 True, id="Valid SCM (GitHub) installation"),
    pytest.param([InstallationFactory.build(vendor=GITLAB, is_active=True,
                                            centralized_repo_asset=LimitedAssetFactory.build(asset_name="Asset"))],
                 True, id="Valid SCM (GitLab) installation"),
    pytest.param([InstallationFactory.build(vendor=GITHUB, is_active=True,
                                            centralized_repo_asset=LimitedAssetFactory.build(asset_name="Asset")),
                  InstallationFactory.build(vendor=AWS, is_active=False, centralized_repo_asset=None)], True,
                 id="Multiple installations with valid SCM installation"),
])
def test_has_valid_scm_installation(installations: List[Installation],
                                    is_valid: bool):
    assert has_valid_scm_installation(installations) == is_valid

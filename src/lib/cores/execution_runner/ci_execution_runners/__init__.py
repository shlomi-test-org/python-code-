from typing import Type, Dict

from jit_utils.jit_clients.authentication_service.client import AuthenticationService
from jit_utils.jit_clients.tenant_service.client import TenantService
from jit_utils.models.execution import Execution
from jit_utils.models.oauth.entities import VendorEnum

from src.lib.cores.execution_runner.ci_execution_runners.ci_execution_runner import CiExecutionRunner
from src.lib.cores.execution_runner.ci_execution_runners.github_action_execution_runner import (
    GithubActionExecutionRunner,
)
from src.lib.cores.execution_runner.ci_execution_runners.gitlab_execution_runner import GitlabExecutionRunner

VENDOR_TO_RUNNER: Dict[str, Type[CiExecutionRunner]] = {
    VendorEnum.GITHUB: GithubActionExecutionRunner,
    VendorEnum.GITLAB: GitlabExecutionRunner,
}


class VendorTypeNotSupportedException(Exception):
    def __init__(self):
        self.message = f"There is no active installation of vendor type {list(VENDOR_TO_RUNNER.keys())}"
        super().__init__(self.message)


def _get_installation_vendor(tenant_id: str) -> VendorEnum:
    api_token = AuthenticationService().get_api_token(tenant_id=tenant_id)
    installations = TenantService().get_installations(tenant_id=tenant_id, api_token=api_token)
    for installation in installations:
        if installation.is_active and installation.vendor in VENDOR_TO_RUNNER:
            return VendorEnum(installation.vendor)
    raise VendorTypeNotSupportedException()


def get_ci_execution_runner_type(execution: Execution) -> Type[CiExecutionRunner]:
    vendor = execution.vendor
    if not vendor or vendor not in VENDOR_TO_RUNNER:
        vendor = _get_installation_vendor(execution.tenant_id)

    return VENDOR_TO_RUNNER[vendor]

from typing import List, Optional

from jit_utils.models.asset.entities import AssetType


class ManualExecutionException(Exception):
    def __init__(self, *, message: str):
        self.message = message
        super().__init__(self.message)


class EmptyPlanItemSlug(ManualExecutionException):
    def __init__(self) -> None:
        super().__init__(message="Plan item slug is mandatory")


class NoAssetsException(ManualExecutionException):
    def __init__(self) -> None:
        super().__init__(message="Assets not specified")


class InactivePlanItemException(ManualExecutionException):
    def __init__(self, *, plan_item_slug: str) -> None:
        super().__init__(message=f"Plan item {plan_item_slug} is inactive")


class NoManualWorkflowsForPlanItemException(ManualExecutionException):
    def __init__(self) -> None:
        super().__init__(message="Plan item has no workflow with manual (api) trigger")


class AssetWithNoWorkflowException(ManualExecutionException):
    def __init__(self, *, plan_item_slug: str, asset_names: List[str]) -> None:
        message = f"Plan item {plan_item_slug} has no workflows to execute for"
        if len(asset_names) == 1:
            message = f"{message} asset={asset_names[0]}"
        else:
            message = f"{message} assets={asset_names}"
        super().__init__(message=message)


class AssetNotExistsException(ManualExecutionException):
    def __init__(
            self, *, asset_name: Optional[str] = None, asset_type: Optional[AssetType] = None,
            asset_id: Optional[str] = None
    ) -> None:
        message = "Asset with"
        if asset_name:
            message = f"{message} name {asset_name}"
        if asset_type:
            message = f"{message} and type {asset_type}"
        if asset_id:
            message = f"{message} id {asset_id}"
        message = f"{message} does not exist"
        super().__init__(message=message)


class AssetConflictException(ManualExecutionException):
    def __init__(self, *, asset_name: Optional[str] = None, asset_id: Optional[str] = None) -> None:
        message = "Found more than one asset with"
        if asset_name:
            message = f"{message} name={asset_name}"
        if asset_id:
            message = f"{message} id={asset_id}"

        asset_types = AssetType.__args__  # type: ignore
        if asset_name:
            message = f"{message}. Please specify a type from {asset_types}"
        super().__init__(message=message)

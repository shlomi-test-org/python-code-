from jit_utils.models.asset.entities import Asset as AssetModel


class Asset(AssetModel):
    # this attr is being used in the tests, and it requires a lot of refactoring to remove it
    asset_type: str  # type: ignore

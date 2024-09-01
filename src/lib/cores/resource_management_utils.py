"""
This is a utility file for jit-config.yml resource management related functions
"""
from jit_utils.models.jit_files.jit_config import ResourceManagement
from jit_utils.models.trigger.requests import AssetTriggerFilters
from jit_utils.models.asset.entities import Asset


def _is_asset_match_resource(asset: Asset, resource: AssetTriggerFilters) -> bool:
    if resource.type:
        return asset.asset_type == resource.type and asset.asset_name == resource.name

    return asset.asset_name == resource.name


def is_asset_excluded_from_plan_item_slug(
    asset: Asset, plan_item_slug: str, resource_management: ResourceManagement
) -> bool:
    """
    Check if the given asset is excluded from the given plan item slug
    """
    exclude_section = resource_management.exclude
    if not exclude_section:
        return False
    plan_item_excluding_section = exclude_section.plan_items or {}

    if plan_item_slug in plan_item_excluding_section:
        return any(
            _is_asset_match_resource(asset, resource)
            for resource in plan_item_excluding_section[plan_item_slug].resources
        )

    return False

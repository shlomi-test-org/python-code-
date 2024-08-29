from jit_utils.lambda_decorators.feature_flags import evaluate_feature_flag

from src.lib.constants import (FEATURE_FLAG_ALLOW_CONTROLLED_PR_CHECKS, FEATURE_FLAG_ASSETS_IN_SCALE,
                               FEATURE_FLAG_DISMISS_ITEM_ACTIVATED_EVENT)


def get_is_allow_controlled_pr_checks_ff(tenant_id: str) -> bool:
    return evaluate_feature_flag(
        feature_flag_key=FEATURE_FLAG_ALLOW_CONTROLLED_PR_CHECKS,
        payload={"key": tenant_id},
        local_test_value=False,
        default_value=False,
    )


def get_asset_in_scale_ff(tenant_id: str) -> bool:
    return evaluate_feature_flag(
        feature_flag_key=FEATURE_FLAG_ASSETS_IN_SCALE,
        payload={"key": tenant_id},
        local_test_value=False,
        default_value=False,
    )


def get_dismiss_item_activated_event_ff(tenant_id: str) -> bool:
    return evaluate_feature_flag(
        feature_flag_key=FEATURE_FLAG_DISMISS_ITEM_ACTIVATED_EVENT,
        payload={"key": tenant_id},
        local_test_value=False,
        default_value=False,
    )

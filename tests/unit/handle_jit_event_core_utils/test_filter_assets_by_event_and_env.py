import copy

import pytest as pytest

from src.lib.cores.handle_jit_event_core_utils.workflows_templates_filters import filter_assets_by_event_type_and_env
from jit_utils.event_models.common import TriggerFilterAttributes
from tests.common import AssetFactory
import src


@pytest.mark.parametrize(
    'env,trigger,should_be_called',
    [
        ('staging', 'deployment', True),
        (None, 'deployment', False),
        ('prod', 'scheduled', True),
        (None, 'scheduled', False),
    ]
)
def test_filter_assets_by_event_type_and_env(mocker, env, trigger, should_be_called):
    res = mocker.patch.object(
        src.lib.cores.handle_jit_event_core_utils.workflows_templates_filters.FiltersEvaluatorsManager,
        'filter',
        return_value=[]
    )

    assets = [
        AssetFactory.build(
            asset_id="asset-1", asset_name="asset-1", asset_type="repo", vendor="vendor-1", owner="owner-1"
        ),
        AssetFactory.build(
            asset_id="asset-2", asset_name="asset-2", asset_type="repo", vendor="vendor-1", owner="owner-2"
        ),
    ]

    params = {
        'asset_envs': {env} if env else None,
        'triggers': {trigger} if trigger else None
    }
    no_null_params = {key: value for key, value in params.items() if value is not None}
    trigger_filter_attributes = TriggerFilterAttributes(**no_null_params)
    trigger_filter_attributes_copy = copy.deepcopy(trigger_filter_attributes)
    filter_assets_by_event_type_and_env(
        assets=assets,
        asset_envs=trigger_filter_attributes.asset_envs,
        triggers=trigger_filter_attributes.triggers,
        tenant_id='',
        api_token=''
    )

    if should_be_called:
        assert res.call_count == 1
        assert res.call_args.args[0] == trigger
        assert res.call_args.args[1] == env
    else:
        assert res.call_count == 0

    assert trigger_filter_attributes == trigger_filter_attributes_copy

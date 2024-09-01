import src
from src.lib.cores.filter_evaluators.filter_evaluators_manager import FiltersEvaluatorsManager
from tests.common import AssetFactory


def test_filter__no_matching_evaluators():
    assets = [
        AssetFactory.build(
            asset_id="asset-1", asset_name="asset-1", asset_type="repo", vendor="vendor-1", owner="owner-1"
        ),
        AssetFactory.build(
            asset_id="asset-2", asset_name="asset-2", asset_type="repo", vendor="vendor-1", owner="owner-2"
        ),
    ]
    manager = FiltersEvaluatorsManager('', '')
    new_assets = manager.filter('', '', assets)
    assert assets == new_assets


def test_filter__no_received_application_configurations(mocker):
    mocker.patch.object(
        src.lib.clients.plan_service.PlanService,
        'get_plan_item_configurations_applications_according_to_env_trigger',
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
    manager = FiltersEvaluatorsManager('', '')
    new_assets = manager.filter('deployment', 'staging', assets)
    assert len(new_assets) == 0


def test_filter__received_application_configuration_that_fits_asset_1(mocker):
    mocker.patch.object(
        src.lib.clients.plan_service.PlanService,
        'get_plan_item_configurations_applications_according_to_env_trigger',
        return_value=[{
            'type': 'web',
            'application_name': 'app1',
            'target_url': 'https://meshi-bucket.s3.amazonaws.com/openapi.json',
        }, ]
    )
    assets = [
        AssetFactory.build(
            asset_id="asset-1", asset_name="app1", asset_type="web", vendor="zap", owner="owner-1"
        ),
        AssetFactory.build(
            asset_id="asset-2", asset_name="app2", asset_type="web", vendor="zap", owner="owner-1"
        ),
        AssetFactory.build(
            asset_id="asset-3", asset_name="app2", asset_type="api", vendor="zap", owner="owner-2"
        ),
    ]
    manager = FiltersEvaluatorsManager('', '')
    new_assets = manager.filter('deployment', 'staging', assets)
    assert new_assets == assets[:1]


def test_filter__received_applications_configurations_that_fit_assets_1_3(mocker):
    mocker.patch.object(
        src.lib.clients.plan_service.PlanService,
        'get_plan_item_configurations_applications_according_to_env_trigger',
        return_value=[
            {
                'type': 'web',
                'application_name': 'app1',
                'target_url': 'target_url',
            },
            {
                'type': 'api',
                'application_name': 'app2',
                'target_url': 'target_url',
            }
        ]
    )
    assets = [
        AssetFactory.build(
            asset_id="asset-1", asset_name="app1", asset_type="web", vendor="zap", owner="owner-1"
        ),
        AssetFactory.build(
            asset_id="asset-2", asset_name="app2", asset_type="web", vendor="zap", owner="owner-1"
        ),
        AssetFactory.build(
            asset_id="asset-3", asset_name="app2", asset_type="api", vendor="zap", owner="owner-2"
        ),
    ]
    manager = FiltersEvaluatorsManager('', '')
    new_assets = manager.filter('deployment', 'staging', assets)
    assert new_assets == assets[:1] + assets[2:]

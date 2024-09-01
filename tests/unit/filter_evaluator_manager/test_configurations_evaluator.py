import pytest

from src.lib.clients.plan_service_models import ApplicationConfiguration, AwsApplicationConfiguration
from src.lib.constants import AWS_ACCOUNT
from src.lib.cores.filter_evaluators.configurations_evaluator import (
    get_configuration_evaluator,
    AssetNameEqualsApplicationNameEvaluator,
    AssetAccountIdInAwsConfigIdsEvaluator,
)
from src.lib.models.asset import Asset


@pytest.mark.parametrize(
    "application_configuration, result",
    [
        (ApplicationConfiguration(type="not_supported", application_name="application_name"), None),
        (ApplicationConfiguration(type="web", application_name="app1"), AssetNameEqualsApplicationNameEvaluator),
        (ApplicationConfiguration(type="api", application_name="app2"), AssetNameEqualsApplicationNameEvaluator),
        (
            AwsApplicationConfiguration(
                type="aws_configuration", application_name="app3", account_ids=["123456789012"]
            ),
            AssetAccountIdInAwsConfigIdsEvaluator,
        ),
        (
            AwsApplicationConfiguration(type="aws_configuration", application_name="app3"),
            None,
        ),
    ],
)
def test_get_configuration_evaluator(application_configuration, result):
    app_config = application_configuration
    evaluator = get_configuration_evaluator(app_config)

    if result:
        assert isinstance(evaluator, result)
        assert evaluator.application_configuration.application_name == application_configuration.application_name
        assert evaluator.application_configuration.type == application_configuration.type
    else:
        assert evaluator == result


@pytest.mark.parametrize(
    "assets, result",
    [
        ([], 0),
        (
            [
                Asset(
                    asset_id="",
                    tenant_id="",
                    asset_type="web",
                    vendor="",
                    owner="",
                    asset_name="app1",
                    is_active=True,
                    created_at="",
                    modified_at="",
                )
            ],
            1,
        ),
        (
            [
                Asset(
                    asset_id="",
                    tenant_id="",
                    asset_type="api",
                    vendor="",
                    owner="",
                    asset_name="app1",
                    is_active=True,
                    created_at="",
                    modified_at="",
                )
            ],
            0,
        ),
        (
            [
                Asset(
                    asset_id="",
                    tenant_id="",
                    asset_type="web",
                    vendor="",
                    owner="",
                    asset_name="app2",
                    is_active=True,
                    created_at="",
                    modified_at="",
                )
            ],
            0,
        ),
    ],
)
def test_asset_name_equals_application_name_evaluator(assets, result):
    evaluator = AssetNameEqualsApplicationNameEvaluator(ApplicationConfiguration(application_name="app1", type="web"))
    res = evaluator.evaluate(assets)
    assert len(res) == result


@pytest.mark.parametrize(
    "assets, result",
    [
        (
            [
                Asset(
                    asset_id="",
                    tenant_id="",
                    asset_type=AWS_ACCOUNT,
                    vendor="",
                    owner="",
                    asset_name="app",
                    is_active=True,
                    aws_account_id="111111111111",
                    created_at="",
                    modified_at="",
                )
            ],
            {},
        ),
        (
            [
                Asset(
                    asset_id="abcd",
                    tenant_id="",
                    asset_type=AWS_ACCOUNT,
                    vendor="",
                    owner="",
                    asset_name="app",
                    is_active=True,
                    aws_account_id="123456789012",
                    created_at="",
                    modified_at="",
                ),
                Asset(
                    asset_id="efgh",
                    tenant_id="",
                    asset_type="aws_configuration",
                    vendor="",
                    owner="",
                    asset_name="",
                    is_active=True,
                    aws_account_id="123456780915",
                    created_at="",
                    modified_at="",
                ),
            ],
            {
                "abcd": Asset(
                    asset_id="abcd",
                    tenant_id="",
                    asset_type=AWS_ACCOUNT,
                    vendor="",
                    owner="",
                    asset_name="app",
                    is_active=True,
                    aws_account_id="123456789012",
                    created_at="",
                    modified_at="",
                )
            },
        ),
        (
            [
                Asset(
                    asset_id="a",
                    tenant_id="",
                    asset_type=AWS_ACCOUNT,
                    vendor="",
                    owner="",
                    asset_name="app",
                    is_active=True,
                    aws_account_id="123456789012",
                    created_at="",
                    modified_at="",
                ),
            ],
            {
                "a": Asset(
                    asset_id="a",
                    tenant_id="",
                    asset_type=AWS_ACCOUNT,
                    vendor="",
                    owner="",
                    asset_name="app",
                    is_active=True,
                    aws_account_id="123456789012",
                    created_at="",
                    modified_at="",
                ),
            },
        ),
    ],
)
def test_asset_account_id_in_aws_config_ids_evaluator(assets, result):
    evaluator = AssetAccountIdInAwsConfigIdsEvaluator(
        AwsApplicationConfiguration(
            application_name="app", type=AWS_ACCOUNT, account_ids=["123456789012", "123456789013"]
        )
    )
    res = evaluator.evaluate(assets)
    assert res == result

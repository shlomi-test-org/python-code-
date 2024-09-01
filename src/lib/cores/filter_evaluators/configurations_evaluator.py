from abc import ABC
from typing import List, Optional, Dict, Union

import pydantic

from src.lib.clients.plan_service_models import (
    ApplicationConfiguration,
    AwsApplicationConfiguration,
)
from src.lib.constants import (
    WEB_ASSET,
    API_ASSET,
    AWS_ACCOUNT,
    AWS_CONFIGURATION,
)
from jit_utils.models.asset.entities import Asset
from jit_utils.logger import logger


class ConfigurationEvaluator(ABC):
    def evaluate(self, assets: List[Asset]) -> Dict[str, Asset]:
        raise NotImplementedError


class AssetNameEqualsApplicationNameEvaluator(ConfigurationEvaluator):
    def __init__(
        self,
        application_configuration: ApplicationConfiguration,
    ) -> None:
        self.application_configuration = application_configuration

    def evaluate(self, assets: List[Asset]) -> Dict[str, Asset]:
        logger.info(
            f"Evaluating the relevancy of assets according to application name: "
            f"{self.application_configuration.application_name} and type: {self.application_configuration.type} "
        )
        should_be_handled_assets = dict()
        for asset in assets:
            if (
                asset.asset_name == self.application_configuration.application_name
                and asset.asset_type == self.application_configuration.type
            ):
                should_be_handled_assets[asset.asset_id] = asset

        return should_be_handled_assets


class AssetAccountIdInAwsConfigIdsEvaluator(ConfigurationEvaluator):
    def __init__(
        self,
        application_configuration: AwsApplicationConfiguration,
    ) -> None:
        self.application_configuration = application_configuration

    def evaluate(self, assets: List[Asset]) -> Dict[str, Asset]:
        logger.info(
            f"Evaluating the relevancy of assets according to application name: "
            f"{self.application_configuration.application_name} and type: {self.application_configuration.type} "
        )
        should_be_handled_assets = dict()

        for asset in assets:
            if (
                asset.asset_type == AWS_ACCOUNT
                and asset.aws_account_id
                and self.application_configuration.account_ids
                and asset.aws_account_id in self.application_configuration.account_ids
            ):
                should_be_handled_assets[asset.asset_id] = asset

        return should_be_handled_assets


def get_configuration_evaluator(
    application_configuration: ApplicationConfiguration,
) -> Optional[Union[AssetNameEqualsApplicationNameEvaluator, AssetAccountIdInAwsConfigIdsEvaluator]]:
    if application_configuration.type in {WEB_ASSET, API_ASSET}:
        return AssetNameEqualsApplicationNameEvaluator(application_configuration)
    elif application_configuration.type == AWS_CONFIGURATION:
        try:
            return AssetAccountIdInAwsConfigIdsEvaluator(
                AwsApplicationConfiguration(**application_configuration.dict())
            )
        except pydantic.ValidationError as validation_error:
            logger.error(f"Received corrupt configuration with aws type {validation_error}")
            return None
    return None

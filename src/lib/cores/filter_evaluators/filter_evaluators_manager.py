from typing import List, Dict

from src.lib.cores.filter_evaluators.deployment_filter_evaluator import DeploymentFilterEvaluator
from src.lib.cores.filter_evaluators.filter_evaluator import FilterEvaluator
from jit_utils.models.asset.entities import Asset
from jit_utils.logger import logger


class FiltersEvaluatorsManager:
    def __init__(self, api_token: str, tenant_id: str) -> None:
        self.tenant_id = tenant_id
        self.api_token = api_token
        self.filters_evaluators: List[FilterEvaluator] = [DeploymentFilterEvaluator()]

    def filter(self, trigger_type: str, tag: str, assets: List[Asset]) -> List[Asset]:
        logger.info(f"Starting evaluating relevant assets according to: {trigger_type=} {tag=}")
        any_evaluator_activated = False
        evaluated_assets: Dict[str, Asset] = dict()
        for evaluator in self.filters_evaluators:
            if evaluator.should_filter(trigger_type=trigger_type):
                logger.info(f"evaluator: {evaluator.get_name()}, has detected that it should run")
                any_evaluator_activated = True
                temp_assets = evaluator.filter(
                    trigger_type=trigger_type,
                    tag=tag,
                    assets=assets,
                    api_token=self.api_token,
                    tenant_id=self.tenant_id
                )
                logger.info(f"evaluator: {evaluator.get_name()}, has found {len(temp_assets)} relevant assets")
                evaluated_assets = {**evaluated_assets, **temp_assets}

        if any_evaluator_activated:
            logger.info(f"Some evaluators ran, and submitted their assets, we return {len(evaluated_assets)} assets")
            return list(evaluated_assets.values())
        else:
            logger.info("No evaluator was triggered, so we return the assets as received")
            return assets

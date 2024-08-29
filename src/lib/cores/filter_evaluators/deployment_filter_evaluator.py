from typing import List, Dict

from src.lib.clients import PlanService
from src.lib.clients.plan_service_models import ApplicationConfiguration
from src.lib.constants import DEPLOYMENT
from src.lib.cores.filter_evaluators.configurations_evaluator import get_configuration_evaluator
from src.lib.cores.filter_evaluators.filter_evaluator import FilterEvaluator
from jit_utils.models.asset.entities import Asset


class DeploymentFilterEvaluator(FilterEvaluator):
    def should_filter(self, trigger_type: str) -> bool:
        return trigger_type == DEPLOYMENT

    def filter(
            self, trigger_type: str, tag: str, assets: List[Asset], api_token: str, tenant_id: str
    ) -> Dict[str, Asset]:
        application_configs = PlanService().get_plan_item_configurations_applications_according_to_env_trigger(
            env=tag, trigger=trigger_type, api_token=api_token, tenant_id=tenant_id
        )
        should_be_handled_assets: Dict[str, Asset] = dict()
        for application_config in application_configs:
            application_config_model = ApplicationConfiguration(**application_config)
            application_evaluator = get_configuration_evaluator(application_config_model)
            if not application_evaluator:
                raise Exception(f"Supported application config, doesn't have a matching configuration evaluator, "
                                f"{application_config_model.dict()}")
            should_be_handled_assets = {**should_be_handled_assets, **application_evaluator.evaluate(assets)}
        return should_be_handled_assets

    def get_name(self) -> str:
        return "DeploymentFilterEvaluator"

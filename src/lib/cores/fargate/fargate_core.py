import copy
import json
import math
from typing import List

import botocore
from aws_lambda_typing.events import EventBridgeEvent
from jit_utils.logger import logger

from src.lib.aws_common import get_prices
from src.lib.aws_common import get_task_definition
from src.lib.constants import EXECUTION_ID_ENV_VAR
from src.lib.constants import JIT_EVENT_ID_ENV_VAR
from src.lib.constants import TENANT_ID_ENV_VAR
from src.lib.cores.arithmetic_evaluator import eval_expr
from src.lib.exceptions import EventMissingStartOrFinish
from src.lib.exceptions import NonJitTaskError
from src.lib.helpers import parse_jsonpath
from src.lib.helpers import parse_timestamp_iso8601
from src.lib.models.ecs_models import CPUArchitecture
from src.lib.models.ecs_models import ECSTaskData
from src.lib.models.pricing_models import LINUX_ARM_CALCULATION
from src.lib.models.pricing_models import LINUX_X86_CALCULATION
from src.lib.models.pricing_models import PRICING_DEFAULTS
from src.lib.models.pricing_models import SKU_TO_PRICING_MAPPING
from src.lib.models.pricing_models import STORAGE_CALCULATION
from src.lib.models.pricing_models import WINDOWS_CALCULATION


class FargateHandler:
    def parse_ecs_event(self, ecs_event: EventBridgeEvent) -> ECSTaskData:
        jit_event_id = self.__get_env_var(ecs_event, JIT_EVENT_ID_ENV_VAR)
        tenant_id = self.__get_env_var(ecs_event, TENANT_ID_ENV_VAR)
        execution_id = self.__get_env_var(ecs_event, EXECUTION_ID_ENV_VAR)

        definition_arn = ecs_event.get("detail", {}).get("taskDefinitionArn")
        container_path = "[*]"
        if definition_arn:
            essential_container_name = (
                FargateHandler.get_essential_container_name_from_task_arn(
                    definition_arn
                )
            )
            if essential_container_name:
                container_path = f'[?(@.name == "{essential_container_name}")]'

        exit_code = parse_jsonpath(
            f"$.detail.containers{container_path}.exitCode",
            ecs_event,
        )

        essential_container_image = parse_jsonpath(
            f"$.detail.containers{container_path}.image",
            ecs_event,
        )

        image_digest = parse_jsonpath(
            f"$.detail.containers{container_path}.imageDigest",
            ecs_event,
        )

        is_linux = (
            "windows"
            not in ecs_event.get("detail", {}).get("platformFamily", "").lower()
        )

        start_time = ecs_event.get("detail", {}).get("pullStartedAt", None)
        end_time = ecs_event.get("detail", {}).get("stoppedAt", None)

        if not start_time or not end_time:
            raise EventMissingStartOrFinish(event=ecs_event)

        start_time = parse_timestamp_iso8601(start_time)
        end_time = parse_timestamp_iso8601(end_time)
        duration = math.ceil((end_time - start_time).total_seconds())
        priced_duration = duration / 60  # hours

        if is_linux:
            priced_duration = max(
                priced_duration, 1
            )  # Minimum billable duration is 1 minute in linux
        else:
            priced_duration = max(
                priced_duration, 15
            )  # Minimum billable duration is 15 minutes in windows

        storage_gb = (
            ecs_event.get("detail", {}).get("ephemeralStorage", {}).get("sizeInGiB", 20)
        )
        billable_storage_gb = max(0, storage_gb - 20)  # first 20 GB is free

        vcpu = ecs_event.get("detail", {}).get("cpu", None)
        if vcpu:
            vcpu = float(vcpu) / 1024
        memory = ecs_event.get("detail", {}).get("memory", None)
        if memory:
            memory = float(memory) / 1024

        return ECSTaskData(
            tenant_id=tenant_id,
            execution_id=execution_id,
            jit_event_id=jit_event_id,
            cpu_architecture=parse_jsonpath(
                "$.detail.attributes[?(@.name == 'ecs.cpu-architecture')].value",
                ecs_event,
            ),
            region=ecs_event.get("region", None),
            start_time=start_time,
            event_time=end_time,
            duration_seconds=duration,
            vcpu=vcpu,
            memory_gb=memory,
            storage_gb=storage_gb,
            billable_storage_gb=billable_storage_gb,
            is_linux=is_linux,
            billable_duration_minutes=priced_duration,
            exit_code=exit_code,
            container_image=essential_container_image,
            image_digest=image_digest,
        )

    def calculate_task_price(self, task_data: ECSTaskData):
        pricing_list = self.__extract_pricing_from_aws()

        # get relevant calculation formulas according to OS / cpu / etc..
        os_pricing_formula = WINDOWS_CALCULATION
        if task_data.is_linux:
            if task_data.cpu_architecture == CPUArchitecture.x86_64:
                os_pricing_formula = LINUX_X86_CALCULATION
            elif task_data.cpu_architecture == CPUArchitecture.arm64:
                os_pricing_formula = LINUX_ARM_CALCULATION
            else:  # Should not happen, as it is validated in ECSTaskData
                raise Exception(
                    f"Invalid CPU architecture '{task_data.cpu_architecture}' for ECS task."
                )

        os_pricing_formula = f"{os_pricing_formula} + {STORAGE_CALCULATION}"

        # loop over data members + prices to replace the formula
        task_data_dict = vars(task_data)
        for key in task_data_dict.keys():
            if f"[{key}]" in os_pricing_formula:
                os_pricing_formula = os_pricing_formula.replace(
                    f"[{key}]", str(task_data_dict[key])
                )
        for key in pricing_list:
            if f"<{key}>" in os_pricing_formula:
                os_pricing_formula = os_pricing_formula.replace(
                    f"<{key}>", str(pricing_list[key])
                )

        return eval_expr(os_pricing_formula)

    def __extract_pricing_from_aws(self):
        prices_dict = copy.deepcopy(PRICING_DEFAULTS)
        try:
            prices = get_prices()
        except Exception as e:
            logger.warning(
                f"Could not find pricing lists in AWS, using default. Error: {e}"
            )
            return prices_dict

        prices_list = self.__prepare_pricing_list(prices)
        if not prices_list:
            logger.warning(
                "Could not find pricing lists in AWS, the API returned empty results, Using default."
            )
            return prices_dict

        pricing_found_counter = 0
        for price_data in prices_list:
            product_sku = parse_jsonpath("$.product.sku", price_data)
            if not product_sku:
                continue
            product_pricing = SKU_TO_PRICING_MAPPING.get(product_sku, None)
            if not product_pricing:
                continue
            found_price = product_pricing.get_price(price_data)
            if not found_price:
                found_price = PRICING_DEFAULTS[product_pricing.name]
            else:
                pricing_found_counter += 1

            prices_dict[product_pricing.name] = found_price

        if len(PRICING_DEFAULTS) != pricing_found_counter:
            logger.warning(
                f"{pricing_found_counter}/{len(PRICING_DEFAULTS)} pricing were found. "
                f"Using defaults for the rest, Check if all pricing exist here: {prices_list}"
            )

        return prices_dict

    @staticmethod
    def get_essential_container_name_from_task_arn(task_arn: str):
        try:
            res = get_task_definition(task_arn)
            for container in res.get("taskDefinition", {}).get(
                "containerDefinitions", []
            ):
                if container.get("essential", False):
                    return container.get("name", None)
        except botocore.exceptions.ClientError as e:
            logger.warning(
                f"Error querying for task {task_arn}, error: '{e}'. "
                f"Selecting first container's exit code."
            )
            return None

    def __prepare_pricing_list(self, pricing_data: dict) -> List[dict]:
        prices_list = []
        for price in pricing_data.get("PriceList", []):
            prices_list.append(json.loads(price))
        return prices_list

    @staticmethod
    def __get_env_var(ecs_event: EventBridgeEvent, env_var_name: str):
        val = parse_jsonpath(
            f"$.detail.overrides.containerOverrides[*].environment[?(@.name == "
            f'"{env_var_name}")].value',
            ecs_event,
        )
        if not val:
            raise NonJitTaskError(event=ecs_event, extra_msg=f"{env_var_name} environment variable is missing")
        return val

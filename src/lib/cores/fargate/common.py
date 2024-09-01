import json
from typing import Dict
from typing import List
from typing import Optional

import pydantic
from jit_utils.logger import logger
from jit_utils.models.execution import BaseExecutionIdentifiers
from mypy_boto3_batch.type_defs import KeyValuePairTypeDef

from src.lib.constants import ENV_VAR_NAME_TO_FIELD_NAME
from src.lib.constants import EXECUTION_ID_ENV_VAR
from src.lib.constants import JIT_EVENT_ID_ENV_VAR
from src.lib.constants import TENANT_ID_ENV_VAR
from src.lib.cores.fargate.constants import ENTRYPOINT_EVENT_ENV_NAME


def get_batch_job_properties(job_container_env_vars: List[KeyValuePairTypeDef]) -> Optional[BaseExecutionIdentifiers]:
    # The old behavior for backward compatibility
    event_job_properties = next((
        env_var
        for env_var in job_container_env_vars
        if env_var.get("name", "") == ENTRYPOINT_EVENT_ENV_NAME), None
    )

    if event_job_properties:
        job_property_values: Dict = json.loads(event_job_properties["value"])
        return BaseExecutionIdentifiers(**job_property_values["payload"])

    # The new behavior
    required_job_properties = (TENANT_ID_ENV_VAR, JIT_EVENT_ID_ENV_VAR, EXECUTION_ID_ENV_VAR)

    job_properties_dict = {
        ENV_VAR_NAME_TO_FIELD_NAME[env_var["name"]]: env_var["value"] for env_var in job_container_env_vars
        if env_var["name"] in required_job_properties
    }

    try:
        job_properties = BaseExecutionIdentifiers(**job_properties_dict)
    except pydantic.error_wrappers.ValidationError:
        logger.error("Failed to parse job properties as one or more is missing", extra=job_properties_dict)
        return None

    return job_properties

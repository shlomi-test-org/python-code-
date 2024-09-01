import os
from http import HTTPStatus
from typing import Dict, Tuple, List

from aws_lambda_powertools.utilities.idempotency import idempotent, IdempotencyConfig
from aws_lambda_typing.context import Context
from jit_utils.lambda_decorators import exception_handler
from jit_utils.logger import logger, logger_customer_id
from jit_utils.utils.aws.idempotency import get_persistence_layer

from src.lib.constants import IS_SILENT_INVOCATION_ENV_VAR
from src.lib.cores.silent_invocation import execute_silent_invocation
from src.lib.models.execution_models import SilentInvocationRequest


@logger_customer_id(auto=True)
@exception_handler()
@idempotent(
    persistence_store=get_persistence_layer(),
    config=IdempotencyConfig(
        event_key_jmespath="id",
        raise_on_no_idempotency_key=True,
    ),
)
def handler(event, context: Context) -> Tuple[int, Dict[str, List[Dict[str, str]]]]:
    logger.info(f'Starting a silent invocation. {event=}')
    silent_invocation_request = SilentInvocationRequest(**event)

    try:
        os.environ[IS_SILENT_INVOCATION_ENV_VAR] = 'true'
        jobs = execute_silent_invocation(silent_invocation_request)
        logger.info(f'Silent invocation started (dry_run={silent_invocation_request.is_dry_run}). {jobs=}')
        return HTTPStatus.OK, {'jobs': jobs}
    finally:
        del os.environ[IS_SILENT_INVOCATION_ENV_VAR]

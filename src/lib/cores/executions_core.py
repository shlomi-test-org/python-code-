import json
import os
from datetime import datetime
from time import sleep
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

import boto3
from jit_utils.aws_clients.config.aws_config import get_aws_config
from jit_utils.jit_clients.asset_service.client import AssetService
from jit_utils.jit_clients.asset_service.exceptions import AssetNotFoundException
from jit_utils.jit_clients.authentication_service.client import AuthenticationService
from jit_utils.logger import alert
from jit_utils.logger import logger
from jit_utils.logger.logger import add_label
from jit_utils.models.execution import (
    ExecutionStatus,
    ExecutionError,
    BaseExecutionIdentifiers,
    VendorExecutionFailureMetricsEvent,
)
from jit_utils.models.findings.events import UploadFindingsStatusEvent
from jit_utils.models.github.github_api_objects import GetVendorExecutionFailureResponse
from jit_utils.utils.encoding import MultiTypeJSONEncoder
from jit_utils.aws_clients.events import EventBridgeClient

from src.lib.clients.eventbridge import EventsClient
from src.lib.constants import (
    ALLOCATE_RUNNER_RESOURCES_RETRY_COUNT,
    EXECUTION_DISPATCH_ERROR_ALERT,
    PULL_REQUESTS_RELATED_JIT_EVENTS,
    EXECUTION_RETRY_LIMIT,
    EXECUTION_MAX_RETRIES_ALERT,
    EXECUTION_EVENT_SOURCE,
    EXECUTION_EVENT_BUS_NAME,
    EXECUTION_FAILURE_METRIC_DETAIL_TYPE,
)
from src.lib.constants import EXECUTION_COMPLETE_EVENT_DETAIL_TYPE
from src.lib.constants import EXECUTION_DISPATCH_EXECUTION_STATUS_EVENT_DETAIL_TYPE
from src.lib.constants import EXECUTION_REGISTER_EVENT_DETAIL_TYPE
from src.lib.cores.execution_events import send_execution_event
from src.lib.cores.execution_events import send_task_completion_event
from src.lib.cores.execution_runner import get_execution_runner, map_runner_to_runner_type
from src.lib.cores.execution_runner.execution_runner import ExecutionRunnerDispatchError
from src.lib.cores.resources_core import free_resource
from src.lib.cores.utils.multithreading import execute_function_concurrently_with_args_list
from src.lib.cores.utils.truncate import truncate_and_clean_traceback
from src.lib.data.executions_manager import ExecutionsManager
from src.lib.exceptions import BadAccessPatternException, ExecutionNotExistException
from jit_utils.models.execution import Execution
from src.lib.models.execution_models import (
    ExecutionDispatchUpdateEvent,
    MultipleExecutionsIdentifiers,
    UpdateAttributes,
)
from src.lib.models.execution_models import GetExecutionsFilters
from src.lib.models.execution_models import UpdateRequest
from src.lib.models.execution_models import VendorJobIDUpdateRequest

FREE_RESOURCE_RETRY_SLEEP_SECS = 1


def register_execution(register_request: UpdateRequest) -> Execution:
    """
    register an execution.
    :param register_request: Tenant id.
    :return: Execution object.
    """
    executions_manager = ExecutionsManager()
    execution = executions_manager.get_execution_by_jit_event_id_and_execution_id(
        tenant_id=register_request.tenant_id,
        jit_event_id=register_request.jit_event_id,
        execution_id=register_request.execution_id
    )

    if not execution:
        raise Exception(
            f'Could not find execution for tenant {register_request.tenant_id} '
            f'and jit_event_id {register_request.jit_event_id} '
            f'and execution_id {register_request.execution_id}')

    runner = get_execution_runner(execution)
    register_request.execution_timeout = runner.get_watchdog_timeout(ExecutionStatus.RUNNING)

    updated_attributes = executions_manager.update_execution(
        register_request, execution.plan_item_slug, execution.job_runner
    )
    logger.info(f'{updated_attributes=}')
    updated_execution = Execution(**{**execution.dict(), **updated_attributes.dict(exclude_none=True)})
    logger.info(f'Updated execution: {updated_execution}')

    send_execution_event(
        json.dumps(
            {
                **updated_execution.dict(exclude_none=True),
                'original_request': register_request.original_request
            },
            cls=MultiTypeJSONEncoder,
        ),
        EXECUTION_REGISTER_EVENT_DETAIL_TYPE)
    return updated_execution


def complete_execution(complete_request: UpdateRequest, execution: Execution) -> Execution:
    """
    execution is optional and can be passed only if we already have it. Otherwise, we will query for the execution
    using the tenant_id, jit_event_id and execution_id from `complete_request`.
    """
    executions_manager = ExecutionsManager()

    if complete_request.status != ExecutionStatus.CANCELED:
        # CANCELED can only happen for PENDING executions which don't hold resource so no need to free resource

        for i in range(ALLOCATE_RUNNER_RESOURCES_RETRY_COUNT):
            try:
                free_resource(tenant_id=execution.tenant_id,
                              jit_event_id=execution.jit_event_id,
                              execution_id=execution.execution_id,
                              resource_type=execution.resource_type)
                break
            except Exception as e:
                logger.info(e)
                sleep(FREE_RESOURCE_RETRY_SLEEP_SECS)
        else:
            logger.exception(f"Could not free the resource of Tenant: {complete_request.tenant_id}, with "
                             f"jit_event_id: {complete_request.jit_event_id}, "
                             f"and execution_id: {complete_request.execution_id}. "
                             f"Investigation Required!")

    # In case the event received without completed_at field (In event from update-control-status) - update it
    current_time = datetime.utcnow()
    complete_request.completed_at = complete_request.completed_at or current_time.isoformat()
    complete_request.completed_at_ts = complete_request.completed_at_ts or int(current_time.strftime("%s"))

    updated_attributes = executions_manager.update_execution(
        update_request=complete_request,
        plan_item_slug=execution.plan_item_slug,
        job_runner=execution.job_runner,
    )
    logger.info(f'{updated_attributes=}')
    updated_execution = Execution(**{**execution.dict(), **updated_attributes.dict(exclude_none=True)})
    logger.info(f'Updating execution: {updated_execution}')
    send_execution_event(updated_execution.json(exclude_none=True, ), EXECUTION_COMPLETE_EVENT_DETAIL_TYPE)
    return updated_execution


def update_upload_findings_status(request: UploadFindingsStatusEvent) -> Optional[Execution]:
    """
    Update execution with findings upload status.
    :param request: data of an execution to update with the new upload findings status.
    :return: Execution object.
    """
    executions_manager = ExecutionsManager()
    execution = executions_manager.update_findings_upload_status(
        tenant_id=request.tenant_id,
        jit_event_id=request.jit_event_id,
        execution_id=request.execution_id,
        upload_findings_status=request.status,
        plan_items_with_findings=request.plan_items_with_findings,
        # fail_on_findings represents whether the execution should fail if there are open findings
        has_findings=request.fail_on_findings
    )
    logger.info(f"Execution after update: {execution}")
    return execution


def update_control_status(request: UpdateRequest) -> Execution:
    """
    Update execution with control status.
    :param request: data of an execution to update with the new control status.
    :return: Execution object.
    """
    logger.info(
        f'Updating executions control status to status: {request.status} and has_findings: {request.has_findings}')

    # Truncate error_body and stderr
    stderr = truncate_and_clean_traceback(request.stderr)
    error_body = truncate_and_clean_traceback(request.error_body)

    executions_manager = ExecutionsManager()
    if request.has_findings:
        # Given that findings were detected during execution, we can safely assume the execution status is complete.
        # Initially, it was marked as Failed due to control status tech debt in the entrypoint.
        request.status = ExecutionStatus.COMPLETED
    execution = executions_manager.update_control_completed_data(
        request.tenant_id,
        request.jit_event_id,
        request.execution_id,
        request.status,
        request.has_findings,
        error_body,
        request.job_output,
        stderr,
        request.errors,
    )
    logger.info(f"Execution after update: {execution}")
    return execution


def update_execution_run_id(request: VendorJobIDUpdateRequest) -> None:
    """
    Update execution with run_id.
    :param request: data of an execution to update with the new run_id.
    """
    logger.info(f'Updating execution with run_id: {request.vendor_job_id}')

    executions_manager = ExecutionsManager()
    executions_manager.update_execution_run_id(
        request.tenant_id,
        request.jit_event_id,
        request.execution_id,
        request.vendor_job_id,
    )


def get_executions_by_filter(tenant_id: str, filters: GetExecutionsFilters) -> Tuple[List[Execution], Dict]:
    """
    Get executions by filter.
    :param tenant_id: Tenant id.
    :param filters: Execution filters.
    :return: List of executions and last_key
    """
    executions_manager = ExecutionsManager()
    params = {**filters.dict(exclude_none=True), "tenant_id": tenant_id}

    if filters.status and filters.plan_item_slug:
        logger.info("Get executions by status and plan_item_slug")
        return executions_manager.get_executions_by_tenant_id_and_plan_item_slug_and_status(**params)
    if filters.status and filters.asset_id:
        logger.info("Get executions by status and asset_id")
        return executions_manager.get_executions_by_tenant_id_and_asset_id_and_status(**params)
    elif filters.status:
        logger.info("Get executions by status")
        return executions_manager.get_executions_by_tenant_id_and_status(**params)
    elif filters.plan_item_slug:
        logger.info("Get executions by plan_item_slug")
        return executions_manager.get_executions_by_tenant_id_and_plan_item_slug(**params)
    elif filters.jit_event_id and filters.job_name:
        logger.info("Get executions by jit_event_id and job_name")
        return executions_manager.get_executions_by_tenant_id_and_jit_event_id_and_job_name(**params)
    elif filters.jit_event_id:
        logger.info("Get executions by jit_event_id")
        return executions_manager.get_executions_by_tenant_id_and_jit_event(**params)
    else:
        raise BadAccessPatternException(tenant_id=tenant_id, filters=filters)


def get_all_executions_by_filter(tenant_id: str, filters: GetExecutionsFilters) -> List[Execution]:
    executions = []
    should_continue = True
    while should_continue:
        logger.info(f"Getting executions with {filters=}")
        fetched_executions, last_key = get_executions_by_filter(tenant_id, filters)
        executions.extend(fetched_executions)
        filters.start_key = last_key
        should_continue = bool(last_key)

    return executions


def get_execution_by_id(tenant_id: str, jit_event_id: str, execution_id: str) -> Optional[Execution]:
    executions_manager = ExecutionsManager()
    return executions_manager.get_execution_by_jit_event_id_and_execution_id(tenant_id=tenant_id,
                                                                             jit_event_id=jit_event_id,
                                                                             execution_id=execution_id)


def update_execution(execution: Execution, update_request: UpdateRequest) -> Execution:
    """
    Update an execution.
    """
    updated_attributes = ExecutionsManager().update_execution(
        update_request=update_request,
        plan_item_slug=execution.plan_item_slug,
        job_runner=execution.job_runner,
    )

    updated_execution = Execution(**{**execution.dict(), **updated_attributes.dict(exclude_none=True)})
    logger.info(f"Updated execution: {updated_execution}")
    return updated_execution


def dispatch_executions(executions: List[Execution]) -> None:
    """
    Dispatch execution(s) in a single runner.dispatch() operation.
    All executions under the dispatched 'jit_event_id' are handled by the same runner type,
    this means all dispatched executions arrive to the same destination (GitHub / GitLab / Fargate / etc.)
    """
    logger.info(f'Dispatching {len(executions)} executions...')
    should_cancel_execution = not _is_asset_exist_for_execution(executions[0])  # all executions are on the same asset
    if should_cancel_execution:
        logger.warning("Skipping dispatching execution & Canceling execution")
        _fail_executions(
            executions=executions,
            reason="Asset not found"
        )
        return

    runner_type = map_runner_to_runner_type(executions[0])
    try:  # dispatch success flow - notify to update the execution to DISPATCHED and save the run_id if exists
        callback_token = AuthenticationService().get_api_token(tenant_id=executions[0].tenant_id)
        run_id = runner_type.dispatch(executions, callback_token)

    except ExecutionRunnerDispatchError as exc:  # dispatch fail flow - notify to update execution and free resource
        alert(f'Error during dispatch operation {exc}', alert_type=EXECUTION_DISPATCH_ERROR_ALERT)
        _fail_executions(
            executions=executions,
            reason=str(exc)
        )
    else:
        logger.info(f'Dispatch for type={runner_type} with {run_id=}')
        _send_dispatch_update_event(executions=executions, run_id=run_id)


def _is_asset_exist_for_execution(execution: Execution) -> bool:
    try:
        api_token = AuthenticationService().get_api_token(execution.tenant_id)
        asset = AssetService().get_asset(tenant_id=execution.tenant_id, asset_id=execution.asset_id,
                                         api_token=api_token)
        if not asset.is_active or not asset.is_covered:  # we check for 'is_active' just in case
            return False
    except AssetNotFoundException:  # Asset is not found if it was deleted or not 'is_active'
        return False

    return True


def _fail_single_execution(execution: Execution, reason: str) -> None:
    send_task_completion_event(
        completion_status=ExecutionStatus.FAILED,
        tenant_id=execution.tenant_id,
        execution_id=execution.execution_id,
        jit_event_id=execution.jit_event_id,
        error_message=reason,
    )


def _fail_executions(executions: List[Execution], reason: str) -> None:
    logger.info(f"Starting to fail {len(executions)} executions...")
    args_list = [(execution, reason) for execution in executions]
    execute_function_concurrently_with_args_list(
        function_to_execute=_fail_single_execution,
        list_of_argument_tuples=args_list,
        max_workers=6
    )
    logger.info(f"Finished failing operation for all {len(executions)} executions.")


def dispatched_request_core(event: ExecutionDispatchUpdateEvent) -> Execution:
    """
    Update execution with dispatched status.
    :param event: data of an execution to update with the new dispatched status.
    :return: Execution object.
    """
    executions_manager = ExecutionsManager()
    execution = executions_manager.get_execution_by_jit_event_id_and_execution_id(
        tenant_id=event.tenant_id,
        jit_event_id=event.jit_event_id,
        execution_id=event.execution_id,
        raise_=True,
    )

    now = datetime.utcnow()
    runner = get_execution_runner(execution)
    updated_request = UpdateRequest(
        tenant_id=event.tenant_id,
        jit_event_id=event.jit_event_id,
        execution_id=event.execution_id,

        status=ExecutionStatus.DISPATCHED,
        dispatched_at=now.isoformat(),
        dispatched_at_ts=int(now.timestamp()),
        run_id=event.run_id,
        execution_timeout=runner.get_watchdog_timeout(ExecutionStatus.DISPATCHED),
    )
    updated_attributes = executions_manager.update_execution(
        update_request=updated_request,
        plan_item_slug=execution.plan_item_slug,
        job_runner=execution.job_runner,
    )
    logger.info(f'{updated_attributes=}')
    updated_execution = Execution(**{**execution.dict(), **updated_attributes.dict(exclude_none=True)})
    logger.info(f'Updated execution: {updated_execution}')
    return updated_execution


def _send_single_dispatch_update_event(execution: Execution, run_id: Optional[str]) -> None:
    send_execution_event(
        ExecutionDispatchUpdateEvent(
            tenant_id=execution.tenant_id,
            jit_event_id=execution.jit_event_id,
            execution_id=execution.execution_id,
            run_id=run_id,
        ).json(),
        EXECUTION_DISPATCH_EXECUTION_STATUS_EVENT_DETAIL_TYPE,
    )


def _send_dispatch_update_event(executions: List[Execution], run_id: Optional[str]) -> None:
    logger.info(f"Starting to send dispatch update events for {len(executions)} executions...")
    args_list = [(execution, run_id) for execution in executions]
    execute_function_concurrently_with_args_list(
        function_to_execute=_send_single_dispatch_update_event,
        list_of_argument_tuples=args_list,
        max_workers=6
    )
    logger.info(f"Finished sending dispatch update events for all {len(executions)} executions.")


def retry_execution_if_needed(
        execution: Execution,
        update_errors: List[ExecutionError],
) -> (bool, Optional[GetVendorExecutionFailureResponse]):
    """
    Determine if we should retry the execution.
    """
    all_execution_errors = update_errors + execution.errors
    if execution.jit_event_name in PULL_REQUESTS_RELATED_JIT_EVENTS and all_execution_errors:
        logger.info("Execution has errors and is related to a pull request")
        base_ids = BaseExecutionIdentifiers(
            tenant_id=execution.tenant_id,
            jit_event_id=execution.jit_event_id,
            execution_id=execution.execution_id,
        )
        if execution.retry_count < EXECUTION_RETRY_LIMIT:
            for error in all_execution_errors:
                if error.is_retryable:
                    logger.info(f"Invoking execution retry for execution {base_ids=}")
                    add_label('RETRY', str(execution.retry_count))
                    _invoke_retry_execution(base_ids)
                    return True, None
        else:
            logger.info(f"Execution {execution.execution_id} has reached the retry limit, completing execution")
            alert(
                f'Execution reached max retries {base_ids=}, could not recover from errors,'
                f' error: {execution.error_body}',
                alert_type=EXECUTION_MAX_RETRIES_ALERT
            )
            return False, get_vendor_failure(execution)
    return False, None


def _invoke_retry_execution(payload: BaseExecutionIdentifiers) -> None:
    lambda_client = boto3.client("lambda", **get_aws_config())
    function_name = os.getenv("RETRY_EXECUTION_LAMBDA_ARN", "retry-execution")
    # Serializing the payload to JSON formatted string as the Lambda function expects a string
    response = lambda_client.invoke(
        FunctionName=function_name,
        InvocationType='Event',
        Payload=payload.json()
    )
    logger.info(f"Invoked retry execution for {payload=}, got response {response=}")


def fetch_execution_from_base_execution_ids(exec_base_ids: BaseExecutionIdentifiers) -> Execution:
    execution = ExecutionsManager().get_execution_by_jit_event_id_and_execution_id(
        tenant_id=exec_base_ids.tenant_id,
        jit_event_id=exec_base_ids.jit_event_id,
        execution_id=exec_base_ids.execution_id,
    )
    if not execution:
        # Monitor how many times this happens and if needed we'll remove it
        add_label('COMPLETE_EXECUTION_NOT_IN_DB', 'True')
        raise ExecutionNotExistException(
            tenant_id=exec_base_ids.tenant_id,
            jit_event_id=exec_base_ids.jit_event_id,
            execution_id=exec_base_ids.execution_id,
        )
    return execution


def _handle_vendor_execution_failure(
        execution: Execution, failure: GetVendorExecutionFailureResponse
) -> Optional[Execution]:
    updated_execution = ExecutionsManager().partially_update_execution(
        tenant_id=execution.tenant_id,
        jit_event_id=execution.jit_event_id,
        execution_id=execution.execution_id,
        update_attributes=UpdateAttributes(
            error_body=failure.json(),
            run_id=failure.run_id,
        ),
    )
    return updated_execution or execution


def update_execution_with_vendor_failure(execution: Execution) -> Execution:
    failure = get_vendor_failure(execution)
    if failure:
        return _handle_vendor_execution_failure(execution, failure)
    return execution


def get_vendor_failure(execution: Execution) -> Optional[GetVendorExecutionFailureResponse]:
    """
    Get the vendor failure response for the execution.
    """
    runner = get_execution_runner(execution)
    failure = runner.get_execution_failure_reason()
    if not failure:
        logger.info(f"Couldn't find failure reason for {execution.execution_id=}, not updating the execution")
        return None
    send_vendor_failure_metric(execution, failure)
    return failure


def send_vendor_failure_metric(execution: Execution, failure: GetVendorExecutionFailureResponse) -> None:
    event_client = EventsClient()
    event_client.put_event(
        source=EXECUTION_EVENT_SOURCE,
        bus_name=EXECUTION_EVENT_BUS_NAME,
        detail_type=EXECUTION_FAILURE_METRIC_DETAIL_TYPE,
        detail=VendorExecutionFailureMetricsEvent(
            tenant_id=execution.tenant_id,
            jit_event_id=execution.jit_event_id,
            execution_id=execution.execution_id,
            execution_context=execution.context,
            vendor=execution.vendor,
            reason=failure.reason,
            error_body=failure.error_body,
        ).json(),
    )


def put_dispatch_execution_events(
    executions: List[Execution],
    detail_type: str,
) -> None:
    """ Puts the given execution identifiers to the event bus in a format that can be consumed by EventBridge """
    grouped_identifiers = MultipleExecutionsIdentifiers.group_by_jit_event_id(executions)
    execution_identifiers_json = [identifiers_group.json() for identifiers_group in grouped_identifiers]

    EventBridgeClient().put_events(
        source=EXECUTION_EVENT_SOURCE,
        bus_name=EXECUTION_EVENT_BUS_NAME,
        detail_type=detail_type,
        details=execution_identifiers_json,
    )

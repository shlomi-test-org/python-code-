import json
from datetime import datetime
from typing import Optional

from jit_utils.event_models.trigger_event import TriggerExecutionEvent
from jit_utils.logger.logger import add_label, health_metric
from jit_utils.logger import logger
from jit_utils.models.execution import ExecutionStatus, TriggerExecutionFailedUpdateEvent
from jit_utils.utils.encoding import MultiTypeJSONEncoder

from src.lib.clients.eventbridge import get_events_client
from src.lib.constants import EXECUTION_COMPLETE_EVENT_DETAIL_TYPE, EXECUTION_METRIC_NAME, \
    EXECUTION_DISPATCH_METRIC_DETAIL_TYPE
from src.lib.constants import EXECUTION_DEPROVISIONED_EXECUTION_EVENT_DETAIL_TYPE
from src.lib.constants import EXECUTION_EVENT_BUS_NAME
from src.lib.constants import EXECUTION_EVENT_SOURCE
from src.lib.constants import RESOURCE_ALLOCATION_INVOKED_METRIC_DETAIL_TYPE
from src.lib.models.execution_models import ControlStatusDetails
from jit_utils.models.execution import Execution
from src.lib.models.execution_models import UpdateRequest


def send_task_completion_event(
        completion_status: ExecutionStatus,
        tenant_id: str,
        execution_id: str,
        jit_event_id: str,
        error_message: Optional[str] = None,
):
    update_request = UpdateRequest(
        tenant_id=tenant_id,
        jit_event_id=jit_event_id,
        execution_id=execution_id,
        status=completion_status,
        status_details=ControlStatusDetails(message=error_message) if error_message else None,
        error_body=error_message or None,
    )

    logger.warning(f"Sending immediate completion event for execution {update_request}")
    send_execution_event(
        execution_event=update_request.json(exclude_none=True),
        detail_type=EXECUTION_DEPROVISIONED_EXECUTION_EVENT_DETAIL_TYPE,
    )


def send_trigger_execution_failed_event(trigger_event: TriggerExecutionEvent) -> None:
    send_execution_event(
        execution_event=TriggerExecutionFailedUpdateEvent(
            tenant_id=trigger_event.context.jit_event.tenant_id,
            jit_event_id=trigger_event.context.jit_event.jit_event_id,
            plan_item_slug=trigger_event.plan_item_slug,
            affected_plan_items=trigger_event.affected_plan_items,
            vendor=trigger_event.context.asset.vendor,
            workflow_slug=trigger_event.context.workflow.slug,
            job_name=trigger_event.context.job.job_name,
            status=ExecutionStatus.FAILED,
            asset_id=trigger_event.context.asset.asset_id,
            jit_event_name=trigger_event.context.jit_event.jit_event_name,
            error_body="Failed to trigger the execution",
            control_type=trigger_event.control_type,
        ).json(),
        detail_type=EXECUTION_COMPLETE_EVENT_DETAIL_TYPE,
    )


def send_execution_event(execution_event: str, detail_type: str) -> None:
    """
    Send an execution event.
    :param execution_event: Execution object.
    :param detail_type: Event type.
    """
    tenant_id = json.loads(execution_event)["tenant_id"]
    health_metric_data = {
        **json.loads(execution_event),
        "event_type": detail_type,
    }
    health_metric(metric_name=EXECUTION_METRIC_NAME, tenant_id=tenant_id, data=health_metric_data)

    events_client = get_events_client()
    events_client.put_event(
        source=EXECUTION_EVENT_SOURCE,
        bus_name=EXECUTION_EVENT_BUS_NAME,
        detail_type=detail_type,
        detail=execution_event,
    )


def send_allocation_invoked_metric_event(execution: Execution) -> None:
    """
    Send an allocation invoked metric event.
    """

    seconds_to_invoke_allocation = (datetime.now() - datetime.fromisoformat(execution.created_at)).seconds
    add_label("seconds_to_invoke_allocation", str(seconds_to_invoke_allocation))

    events_client = get_events_client()
    detail = {
        **execution.dict(),
        "seconds_to_invoke_allocation": seconds_to_invoke_allocation,
    }
    events_client.put_event(
        source=EXECUTION_EVENT_SOURCE,
        bus_name=EXECUTION_EVENT_BUS_NAME,
        detail_type=RESOURCE_ALLOCATION_INVOKED_METRIC_DETAIL_TYPE,
        detail=json.dumps(detail, cls=MultiTypeJSONEncoder),
    )


def send_execution_dispatched_metric_event(execution: Execution) -> None:
    """
    Send an execution dispatched metric event.
    """
    seconds_to_execution_dispatch = (datetime.now() - datetime.fromisoformat(execution.created_at)).seconds
    add_label("seconds_to_execution_dispatch", str(seconds_to_execution_dispatch))

    events_client = get_events_client()
    detail = {
        **execution.dict(),
        "duration_seconds": seconds_to_execution_dispatch,
    }
    events_client.put_event(
        source=EXECUTION_EVENT_SOURCE,
        bus_name=EXECUTION_EVENT_BUS_NAME,
        detail_type=EXECUTION_DISPATCH_METRIC_DETAIL_TYPE,
        detail=json.dumps(detail, cls=MultiTypeJSONEncoder),
    )

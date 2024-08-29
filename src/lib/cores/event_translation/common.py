from typing import Optional, Dict

from jit_utils.aws_clients.events import EventBridgeClient
from jit_utils.event_models import JitEventName
from jit_utils.event_models.third_party.github import (
    WebhookDeploymentEventBody,
    WebhookPullRequestEventBody,
    WebhookRerunEventBody,
    WebhookSingleCheckRerunEventBody,
    WebhookEventBodyTypes,
)
from jit_utils.event_models.webhook import WebhookEvent
from jit_utils.logger import logger
from jit_utils.jit_clients.tenant_service.client import TenantService
from jit_utils.logger.logger import add_label
from jit_utils.models.tenant.entities import Installation
from pydantic import parse_obj_as, ValidationError

from src.lib.constants import (
    TRIGGER_SERVICE, TRIGGER_EXECUTION_BUS_NAME, TRIGGER_EXECUTION_DETAIL_TYPE_HANDLE_EVENT
)
from src.lib.cores.event_translation.deployment_event_translation import (
    get_jit_event_name_from_deployment_event,
    create_deployment_jit_execution_event
)

from src.lib.cores.event_translation.pr_event_translation import (
    get_jit_event_name_from_pull_request_event,
    create_code_related_jit_execution_event
)
from src.lib.cores.event_translation.rerun_event_translation import (
    get_jit_event_name_from_rerun_event,
    create_rerun_code_related_jit_event,
    create_rerun_single_check_code_related_jit_event,
)

EVENT_NAME_FINDERS: Dict = {
    WebhookDeploymentEventBody: get_jit_event_name_from_deployment_event,
    WebhookPullRequestEventBody: get_jit_event_name_from_pull_request_event,
    WebhookRerunEventBody: get_jit_event_name_from_rerun_event,
    WebhookSingleCheckRerunEventBody: get_jit_event_name_from_rerun_event,
}

EXECUTION_EVENT_CREATORS: Dict = {
    WebhookPullRequestEventBody: create_code_related_jit_execution_event,
    WebhookDeploymentEventBody: create_deployment_jit_execution_event,
    WebhookRerunEventBody: create_rerun_code_related_jit_event,
    WebhookSingleCheckRerunEventBody: create_rerun_single_check_code_related_jit_event,
}


def _extract_installation_id_from_event(webhook_event: WebhookEvent) -> Optional[str]:
    """
    Extract the installation ID from a given webhook event.

    Args:
        webhook_event (WebhookEvent): The webhook event to extract the installation ID from.

    Returns:
        Optional[str]: The installation ID if it exists, None otherwise.
    """
    if webhook_event.webhook_body_json is not None:
        for EventBodyType in [
            WebhookPullRequestEventBody,
            WebhookDeploymentEventBody,
            WebhookRerunEventBody,
            WebhookSingleCheckRerunEventBody,
        ]:
            try:
                event_body = parse_obj_as(EventBodyType, webhook_event.webhook_body_json)  # type: ignore
                return str(event_body.installation.id)  # type: ignore
            except (ValidationError, AttributeError):
                # If parsing failed or the installation attribute was not found, proceed to the next type
                pass
    # the body JSON was either None or didn't match any event body type
    return None


def _get_installation_by_id(installation_id: str, vendor: str) -> Optional[Installation]:
    tenant = TenantService().get_tenant_by_installation_id(vendor, installation_id)
    for installation in (tenant.installations or []):
        if installation.installation_id == installation_id:
            logger.info(f"Got installation for {installation_id=}: tenant_id={installation.tenant_id}")
            return installation

    return None


def get_installation(webhook_event: WebhookEvent) -> Installation:
    """
    Get the tenant's installation by the installation_id and vendor of the webhook event.
    """
    installation_id = _extract_installation_id_from_event(webhook_event)
    if installation_id:
        installation = _get_installation_by_id(installation_id, webhook_event.vendor)

        if installation:
            logger.info(f'Found installation based on webhook event {installation=}')
            return installation

    # Installation not found
    raise Exception(f"Installation not found for {installation_id=} and vendor={webhook_event.vendor}")


def get_jit_event_name(
        event_body: Optional[WebhookEventBodyTypes],
        event_type: str
) -> Optional[JitEventName]:
    """
    This method computes the relevant jit event name for the webhook event, based on the webhook event.
    It depends on the specific implementations of the event name finders (per each type of webhook event body).
    """
    try:
        jit_event_name = EVENT_NAME_FINDERS[type(event_body)](
            event_body=event_body,
            event_type=event_type
        )

        logger.info(f"Found jit event name {jit_event_name=} for event type {type(event_body)}")

        return jit_event_name
    except (KeyError, TypeError):
        logger.info(f"Unsupported event {event_type=} and {event_body=}")
        return None


def send_jit_event_from_webhook_event_for_handling(
        installation: Installation,
        event_body: WebhookEventBodyTypes,
        jit_event_name: JitEventName,
) -> None:
    """
    This method receives a webhook event, creates a JIT event based on it (according to its type),
    and sends it to the trigger service handle-jit-event lambda.
    """
    jit_event = EXECUTION_EVENT_CREATORS[type(event_body)](
        installation=installation,
        event_body=event_body,
        jit_event_name=jit_event_name
    )

    if not jit_event:
        logger.info(f"No jit event created for {event_body=}")
        return

    logger.info(f"Result jit event that will be dispatched for handling {jit_event=}")

    # we only extract those in this stage, so we cannot have them in the beginning of the lambda invocation
    add_label('customer_id', jit_event.tenant_id)
    add_label('jit_event_name', jit_event.jit_event_name)

    EventBridgeClient().put_event(
        source=TRIGGER_SERVICE,
        bus_name=TRIGGER_EXECUTION_BUS_NAME,
        detail_type=TRIGGER_EXECUTION_DETAIL_TYPE_HANDLE_EVENT,
        detail=jit_event.json(),
    )

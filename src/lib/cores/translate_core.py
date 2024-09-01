from aws_lambda_typing.events import EventBridgeEvent
from typing import Dict, Optional

from jit_utils.event_models.third_party.github import (
    WebhookPullRequestEvent,
    WebhookDeploymentEvent,
    WebhookRerunEvent,
    WebhookSingleCheckRerunEvent,
)
from jit_utils.event_models.webhook import WebhookEvent
from jit_utils.logger import logger

from src.lib.constants import (
    WEBHOOK_HEADERS,
    WEBHOOK_BODY_JSON,
    WEBHOOK_BODY,
    DEPLOYMENT_STATUS_UPDATED,
    PULL_REQUEST_OPENED,
    PULL_REQUEST_SYNCHRONIZE,
    PULL_REQUEST_CLOSED,
    RERUN_PIPELINE,
    CHECK_RERUN_PIPELINE,
)
from src.lib.cores.event_translation.common import (get_installation, get_jit_event_name,
                                                    send_jit_event_from_webhook_event_for_handling)

WEBHOOK_EVENT_CLASSES_BY_EVENT_TYPE: Dict[str, type] = {
    PULL_REQUEST_OPENED: WebhookPullRequestEvent,
    PULL_REQUEST_SYNCHRONIZE: WebhookPullRequestEvent,
    PULL_REQUEST_CLOSED: WebhookPullRequestEvent,
    DEPLOYMENT_STATUS_UPDATED: WebhookDeploymentEvent,
    RERUN_PIPELINE: WebhookRerunEvent,
    CHECK_RERUN_PIPELINE: WebhookSingleCheckRerunEvent,
}


def _translate_event_to_webhook_event(event: EventBridgeEvent) -> Optional[WebhookEvent]:
    detail = event["detail"]
    webhook_event_type: str = detail.get('event_type', '')
    headers = detail[WEBHOOK_HEADERS]
    body = detail[WEBHOOK_BODY_JSON]
    params = {
        **detail,
        WEBHOOK_HEADERS: headers,
        WEBHOOK_BODY: body,
    }

    webhook_class = WEBHOOK_EVENT_CLASSES_BY_EVENT_TYPE.get(webhook_event_type)

    if not webhook_class:
        logger.info(f"No webhook class found for event type {webhook_event_type=}")
        return None

    return webhook_class(**params)


def dispatch_jit_event_from_raw_event(raw_event: EventBridgeEvent) -> None:
    """
    This function first translates the incoming raw event to a suitable webhook event.
    Then, it fetches the installation and jit event name based on the webhook event.
    Finally, it creates a jit event based on the webhook event (plus the additional data), and sends for handling
    in the same service, but in different lambda (handle-jit-event).
    """

    webhook_event = _translate_event_to_webhook_event(raw_event)
    if not webhook_event or not webhook_event.webhook_body_json:
        logger.info("No suitable webhook body found for original event")
        return

    logger.info(f"Got webhook event to translate to jit event {webhook_event=}")
    installation = get_installation(webhook_event)

    jit_event_name = get_jit_event_name(
        event_type=webhook_event.event_type,
        event_body=webhook_event.webhook_body_json
    )

    if not jit_event_name:
        logger.info(f"Skipping translate of unhandled {webhook_event.event_type=}")
        return

    send_jit_event_from_webhook_event_for_handling(installation, webhook_event.webhook_body_json, jit_event_name)

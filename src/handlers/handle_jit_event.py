from aws_lambda_typing.context import Context
from aws_lambda_typing.events import EventBridgeEvent
from jit_utils.event_models import JitEventTypes, JitEventName, CodeRelatedJitEvent
from jit_utils.jit_clients.asset_service.client import AssetService
from jit_utils.jit_clients.authentication_service.client import AuthenticationService
from jit_utils.lambda_decorators import exception_handler, lambda_warmup_handler, feature_flags_init_client
from jit_utils.logger import logger, logger_customer_id, CustomLabel, custom_labels
from jit_utils.logger.logger import add_label, alert
from jit_utils.models.trigger.jit_event_life_cycle import JitEventStatus
from pydantic import parse_obj_as

from src.lib.constants import REPO
from src.lib.cores.jit_event_handlers.jit_event_assets_orchestrator import JitEventAssetsOrchestrator
from src.lib.cores.jit_event_handlers.jit_event_resources_processor import JitEventResourcesProcessor
from src.lib.cores.jit_event_life_cycle.jit_event_life_cycle_handler import JitEventLifeCycleHandler
from src.lib.feature_flags import get_asset_in_scale_ff, get_dismiss_item_activated_event_ff
from src.lib.models.trigger import JitEventAssetsOrchestratorStatus, JitEventProcessingResources


@feature_flags_init_client()
@exception_handler()
@lambda_warmup_handler
@logger_customer_id(auto=True)
@custom_labels(
    [
        CustomLabel(
            field_name='jit_event_id',
            label_name='jit_event_id',
            auto=True,
        ),
        CustomLabel(
            field_name='jit_event_name',
            label_name='jit_event_name',
            auto=True,
        ),
    ]
)
def handler(event: EventBridgeEvent, _: Context) -> None:
    """
    The legacy handle jit event runs if the scale FF is closed OR if the jit event does not have asset_ids
    This is done because the new flow currently supports only jit events with asset_ids
    """
    logger.info(f"event: {event}")
    raw_jit_event = event["detail"]
    jit_event: JitEventTypes = parse_obj_as(JitEventTypes, raw_jit_event)  # type: ignore
    logger.info(f"jit event: {repr(jit_event)}")

    if (jit_event.jit_event_name == JitEventName.ItemActivated and
            get_dismiss_item_activated_event_ff(jit_event.tenant_id)):
        logger.info("Feature flag is on, dismissing ItemActivatedJitEvent, exiting")
        return

    if get_asset_in_scale_ff(jit_event.tenant_id):
        logger.info("Feature flag is on")
        if has_asset_ids_filter(jit_event):
            logger.info("The old flow currently supports jit events without asset_ids, exiting")
            return

    jit_event_life_cycle_handler = JitEventLifeCycleHandler()
    jit_event_life_cycle_handler.start(jit_event)
    try:
        # Gets all jobs from the plan-service and all installations from tenant-service
        resources = JitEventResourcesProcessor(jit_event=jit_event).fetch_resources()

        asset_orchestrator = JitEventAssetsOrchestrator(jit_event_resources=resources)
        orchestrator_status = asset_orchestrator.run_jit_event_on_assets()
        if orchestrator_status == JitEventAssetsOrchestratorStatus.FILTERED_ALL_ASSETS:
            jit_event_life_cycle_handler.jit_event_completed(
                tenant_id=jit_event.tenant_id,
                jit_event_id=jit_event.jit_event_id,
                status=JitEventStatus.COMPLETED,
            )
    except Exception as e:
        alert(message=f"Got exception while processing jit event, completing jit event with failed status: {e}",
              alert_type="HANDLE_JIT_EVENT_EXCEPTION",
              log_exception_stacktrace=True)
        jit_event_life_cycle_handler.jit_event_completed(
            tenant_id=jit_event.tenant_id,
            jit_event_id=jit_event.jit_event_id,
            status=JitEventStatus.FAILED,
        )


@feature_flags_init_client()
@exception_handler()
@lambda_warmup_handler
@logger_customer_id(auto=True)
@custom_labels(
    [
        CustomLabel(
            field_name='jit_event_id',
            label_name='jit_event_id',
            auto=True,
        ),
        CustomLabel(
            field_name='jit_event_name',
            label_name='jit_event_name',
            auto=True,
        ),
    ]
)
def fetch_jit_event_resources_handler(event: EventBridgeEvent, _: Context) -> None:
    logger.info(f"event: {event}")
    raw_jit_event = event["detail"]
    jit_event: JitEventTypes = parse_obj_as(JitEventTypes, raw_jit_event)  # type: ignore
    logger.info(f"jit event: {repr(jit_event)}")

    if (jit_event.jit_event_name == JitEventName.ItemActivated and
            get_dismiss_item_activated_event_ff(jit_event.tenant_id)):
        logger.info("Feature flag is on, dismissing ItemActivatedJitEvent, exiting")
        return

    if not get_asset_in_scale_ff(jit_event.tenant_id):
        logger.info("Feature flag is off, exiting")
        return

    if not has_asset_ids_filter(jit_event):
        logger.info("The new flow currently supports only jit events with asset_ids, exiting")
        return

    jit_event_life_cycle_handler = JitEventLifeCycleHandler()
    jit_event_life_cycle_handler.start(jit_event)
    try:
        jit_event_resource_processor = JitEventResourcesProcessor(jit_event=jit_event)
        resources = jit_event_resource_processor.fetch_resources()
        jit_event_resource_processor.send_resources_ready_event(resources)
    except Exception as e:
        alert(message=f"Got exception while processing jit event, completing jit event with failed status: {e}",
              alert_type="HANDLE_JIT_EVENT_EXCEPTION",
              log_exception_stacktrace=True)
        jit_event_life_cycle_handler.jit_event_completed(
            tenant_id=jit_event.tenant_id,
            jit_event_id=jit_event.jit_event_id,
            status=JitEventStatus.FAILED,
        )


def has_asset_ids_filter(jit_event: JitEventTypes) -> bool:
    """
    Temp support for handling only jit events with asset_ids in the new flow
    """
    # In case the jit event missing asset_id, we will try to fetch it from the asset service
    if isinstance(jit_event, CodeRelatedJitEvent) and not jit_event.asset_id and jit_event.owner:
        jit_event.asset_id = AssetService().get_asset_by_attributes(
            tenant_id=jit_event.tenant_id,
            asset_type=REPO,
            vendor=jit_event.vendor,
            owner=jit_event.owner,
            asset_name=jit_event.original_repository,
            api_token=AuthenticationService().get_api_token(jit_event.tenant_id),
        ).asset_id

    return bool(jit_event.trigger_filter_attributes.asset_ids)


@feature_flags_init_client()
@exception_handler()
@lambda_warmup_handler
@logger_customer_id(auto=True)
def run_jit_event_on_assets_by_ids_handler(event: EventBridgeEvent, _: Context) -> None:
    logger.info(f"event: {event}")
    event_detail = event["detail"]
    resources: JitEventProcessingResources = parse_obj_as(JitEventProcessingResources, event_detail)  # type: ignore
    add_label("jit_event_id", resources.jit_event.jit_event_id)
    add_label("jit_event_name", resources.jit_event.jit_event_name)

    jit_event_life_cycle_handler = JitEventLifeCycleHandler()
    try:
        asset_orchestrator = JitEventAssetsOrchestrator(jit_event_resources=resources)
        assets = asset_orchestrator.get_assets_by_ids()
        if assets:
            asset_orchestrator.execute_scan_on_assets(assets)
        else:
            jit_event_life_cycle_handler.jit_event_completed(
                tenant_id=resources.jit_event.tenant_id,
                jit_event_id=resources.jit_event.jit_event_id,
                status=JitEventStatus.COMPLETED,
            )
    except Exception as e:
        alert(message=f"Got exception while processing jit event, completing jit event with failed status: {e}",
              alert_type="HANDLE_JIT_EVENT_EXCEPTION",
              log_exception_stacktrace=True)

        jit_event_life_cycle_handler.jit_event_completed(
            tenant_id=resources.jit_event.tenant_id,
            jit_event_id=resources.jit_event.jit_event_id,
            status=JitEventStatus.FAILED,
        )

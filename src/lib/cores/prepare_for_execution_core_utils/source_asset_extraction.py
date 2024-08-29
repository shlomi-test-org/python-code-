from pydantic import ValidationError
from typing import Optional, Dict

from jit_utils.event_models import JitEventTypes, CodeRelatedJitEvent, DeploymentJitEvent
from jit_utils.event_models.trigger_event import SourceAsset
from jit_utils.logger import logger

ASSET_TYPE_REPO = "repo"


def _get_source_resource_from_code_related_jit_event(jit_event: CodeRelatedJitEvent) -> SourceAsset:
    source_asset = SourceAsset(
        source_asset_id=jit_event.asset_id,
        source_asset_name=jit_event.original_repository,
        source_asset_type=ASSET_TYPE_REPO,
        source_asset_vendor=jit_event.vendor,
        source_asset_owner=jit_event.owner,
    )

    return source_asset


def _get_source_resource_from_deployment_jit_event(jit_event: DeploymentJitEvent) -> SourceAsset:
    source_asset = SourceAsset(
        source_asset_id=jit_event.asset_id,
        source_asset_name=jit_event.original_repository,
        source_asset_type=ASSET_TYPE_REPO,
        source_asset_vendor=jit_event.vendor,
        source_asset_owner=jit_event.owner,
    )

    return source_asset


SOURCE_ASSET_EXTRACTORS: Dict = {
    CodeRelatedJitEvent: _get_source_resource_from_code_related_jit_event,
    DeploymentJitEvent: _get_source_resource_from_deployment_jit_event,
}


def extract_source_asset_from_event(jit_event: JitEventTypes) -> Optional[SourceAsset]:
    try:
        source_asset = SOURCE_ASSET_EXTRACTORS[type(jit_event)](jit_event)
        logger.info(f"Extracted source asset from event: {source_asset}")
        return source_asset
    except KeyError:
        return None
    except ValidationError as e:
        logger.error(f"Failed to extract source asset from event {repr(jit_event)}: {e}")
        raise

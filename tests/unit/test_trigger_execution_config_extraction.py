import pytest

from jit_utils.event_models import ResourceAddedJitEvent, ItemActivatedJitEvent, JitEventName


BASE_JIT_EVENT = {
    "tenant_id": "tenant_id",
    "jit_event_id": "jit_event_id",
}


@pytest.mark.parametrize("jit_event, expected_triggers", [
    (
            ResourceAddedJitEvent(
                **BASE_JIT_EVENT, created_asset_ids={"asset_id"}
            ),
            {JitEventName.ResourceAdded},
    ),
    (
            ItemActivatedJitEvent(
                **BASE_JIT_EVENT, activated_plan_slug="plan_slug", activated_plan_item_slugs={"plan_item_slug"}
            ),
            {JitEventName.ItemActivated},
    ),
])
def test_extractor_for_jit_event(jit_event, expected_triggers):
    assert jit_event.trigger_filter_attributes.triggers == expected_triggers

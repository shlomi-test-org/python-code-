import pytest
from jit_utils.event_models import JitEventTypes
from jit_utils.jit_event_names import JitEventName

from src.lib.models.trigger import JitEventProcessingResources
from tests.common import CodeRelatedJitEventFactory

test_pr_created_jit_event = CodeRelatedJitEventFactory.build(
    jit_event_name=JitEventName.PullRequestCreated
)

test_merge_default_branch_jit_event = CodeRelatedJitEventFactory.build(
    jit_event_name=JitEventName.MergeDefaultBranch
)


@pytest.mark.parametrize("jit_event, expected_jit_event", [
    (test_pr_created_jit_event, test_pr_created_jit_event),
    # We need to make sure that we're cleaning those values on merge default branch event
    (test_merge_default_branch_jit_event, test_merge_default_branch_jit_event.copy(update={
        "pull_request_number": None,
        "pull_request_title": None,
        "commits": {
            "head_sha": None,
            "base_sha": ""
        }})
     ),
])
def test_JitEventProcessingResources__init__(
        jit_event: JitEventTypes,
        expected_jit_event: JitEventTypes):
    jit_event_processing_resources = JitEventProcessingResources(
        jit_event=jit_event,
        installations=[],
        jobs=[],
        plan_depends_on_workflows={},
    )
    assert jit_event_processing_resources.jit_event == expected_jit_event

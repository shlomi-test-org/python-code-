from datetime import datetime

from jit_utils.event_models import JitEventName
from jit_utils.event_models.common import TriggerFilterAttributes
from jit_utils.models.execution_context import RepoEnrichmentResult
from jit_utils.models.oauth.entities import VendorEnum
from jit_utils.models.trigger.jit_event_life_cycle import JitEventStatus

from src.lib.constants import JIT_PLAN_SLUG
from tests.common import (
    DeploymentJitEventFactory,
    CodeRelatedJitEventFactory,
    OpenPRJitEventFactory,
    ItemActivatedJitEventFactory,
    ResourceAddedJitEventFactory,
    TriggerScheduledTaskJitEventFactory
)
from tests.component.utils.mocks.mock_plan import MOCK_PLAN
from tests.component.utils.mocks.mocks import (
    ASSETS,
    MANUAL_EXECUTION_EVENT_TRIGGER_CLOUD_CONTROL,
    TEST_TENANT_ID,
    ASSET_AWS_WITH_DEPLOYMENT_CONF,
    ASSET_DEPLOYMENT,
    ASSET_GITHUB_ORG,
    ASSET_GITHUB_REPO_2,
    ASSET_GITHUB_REPO_1,
    MANUAL_EXECUTION_EVENT_CODE
)

TEST_CASES = {
    # test schedule event - workflow exists + assets exists -> has executions!
    "scheduled_event__has_executions": {
        "jit_event": TriggerScheduledTaskJitEventFactory.build(
            tenant_id=TEST_TENANT_ID,
            plan_item_slug="item-branch-protection-scm",
            plan_item_slugs=["item-branch-protection-scm", "another_plan_item_slug"],
            workflow_slug="workflow-branch-protection-github-checker",
            cron_expression=None,
            single_execution_time=datetime.now(),
        ),
        "plan": MOCK_PLAN,
        "all_assets": ASSETS,
        "expected_triggered_assets": [ASSET_GITHUB_REPO_1, ASSET_GITHUB_REPO_2],
        "expected_trigger_filter_attributes": TriggerFilterAttributes(
            plan_item_slugs={"item-branch-protection-scm", "another_plan_item_slug"},
            workflow_slugs={"workflow-branch-protection-github-checker"},
        ),
        "expected_has_dependency": False,
        "has_valid_plan_item_and_workflow": True,
        "expected_jit_event_status": JitEventStatus.STARTED,
        "expected_enrich_data": None,
    },
    # test schedule event - workflow not exists -> no executions!
    "scheduled_event__no_workflow__no_executions": {
        "jit_event": TriggerScheduledTaskJitEventFactory.build(
            tenant_id=TEST_TENANT_ID,
            plan_item_slug="item-branch-protection-scm",
            workflow_slug="workflow-not-existing",
            cron_expression=None,
            single_execution_time=datetime.now(),
        ),
        "plan": MOCK_PLAN,
        "all_assets": ASSETS,
        "expected_triggered_assets": [],
        "expected_trigger_filter_attributes": None,
        "expected_has_dependency": False,
        "has_valid_plan_item_and_workflow": False,
        "expected_jit_event_status": JitEventStatus.COMPLETED,
        "expected_enrich_data": None,
    },
    # test schedule event - workflow exists + assets not exists -> no executions!
    "scheduled_event__no_assets__no_executions": {
        "jit_event": TriggerScheduledTaskJitEventFactory.build(
            tenant_id=TEST_TENANT_ID,
            plan_item_slug="item-branch-protection-scm",
            workflow_slug="workflow-branch-protection-github-checker",
            cron_expression=None,
            single_execution_time=datetime.now(),
        ),
        "plan": MOCK_PLAN,
        "all_assets": [ASSET_GITHUB_ORG],
        "expected_triggered_assets": [],
        "expected_trigger_filter_attributes": None,
        "expected_has_dependency": False,
        "has_valid_plan_item_and_workflow": True,
        "expected_jit_event_status": JitEventStatus.COMPLETED,
        "expected_enrich_data": None,
    },
    # test resource added event - with 2 assets, has executions!
    "resources_added_event__has_executions": {
        "jit_event": ResourceAddedJitEventFactory.build(
            tenant_id=TEST_TENANT_ID,
            created_asset_ids={ASSET_GITHUB_REPO_1.asset_id, ASSET_GITHUB_REPO_2.asset_id},
            jit_event_name=JitEventName.ResourceAdded,
        ),
        "plan": MOCK_PLAN,
        "all_assets": ASSETS,
        "expected_triggered_assets": [ASSET_GITHUB_REPO_1, ASSET_GITHUB_REPO_2],
        "expected_trigger_filter_attributes": TriggerFilterAttributes(
            triggers={JitEventName.ResourceAdded},
            asset_ids={ASSET_GITHUB_REPO_1.asset_id, ASSET_GITHUB_REPO_2.asset_id},
        ),
        "expected_has_dependency": True,
        "has_valid_plan_item_and_workflow": True,
        "expected_jit_event_status": JitEventStatus.STARTED,
        "expected_enrich_data": None,
    },
    # test resource added event - with 2 assets, but assets are not in DB, no executions!
    "resource_added_event__no_assets__no_executions": {
        "jit_event": ResourceAddedJitEventFactory.build(
            tenant_id=TEST_TENANT_ID,
            created_asset_ids={ASSET_GITHUB_REPO_1.asset_id, ASSET_GITHUB_REPO_2.asset_id},
            jit_event_name=JitEventName.ResourceAdded,
        ),
        "plan": MOCK_PLAN,
        "all_assets": [ASSET_GITHUB_ORG],
        "expected_triggered_assets": [],
        "expected_trigger_filter_attributes": None,
        "expected_has_dependency": True,
        "has_valid_plan_item_and_workflow": True,
        "expected_jit_event_status": JitEventStatus.FAILED,
        "expected_enrich_data": None,
    },
    # test item activated event - with 2 plan items, has executions!
    "item_activated_event__has_executions": {
        "jit_event": ItemActivatedJitEventFactory.build(
            tenant_id=TEST_TENANT_ID,
            activated_plan_slug=JIT_PLAN_SLUG,
            activated_plan_item_slugs={"item-branch-protection-scm", "item-web-app-scanner"},
            jit_event_name=JitEventName.ItemActivated,
        ),
        "plan": MOCK_PLAN,
        "all_assets": ASSETS,
        "expected_triggered_assets": [ASSET_GITHUB_REPO_1, ASSET_GITHUB_REPO_2, ASSET_DEPLOYMENT],
        "expected_trigger_filter_attributes": TriggerFilterAttributes(
            triggers={JitEventName.ItemActivated},
            plan_slugs={JIT_PLAN_SLUG},
            plan_item_slugs={"item-branch-protection-scm", "item-web-app-scanner"},
        ),
        "expected_has_dependency": False,
        "has_valid_plan_item_and_workflow": True,
        "expected_jit_event_status": JitEventStatus.STARTED,
        "expected_enrich_data": None,
    },
    # test item activated event - with 2 plan items, but plan item not in DB, no executions!
    "item_activated_event__no_plan_item__no_executions": {
        "jit_event": ItemActivatedJitEventFactory.build(
            tenant_id=TEST_TENANT_ID,
            activated_plan_slug=JIT_PLAN_SLUG,
            activated_plan_item_slugs={"item-not-exists-1", "item-not-exists-2"},
            jit_event_name=JitEventName.ItemActivated,
        ),
        "plan": MOCK_PLAN,
        "all_assets": ASSETS,
        "expected_triggered_assets": [],
        "expected_trigger_filter_attributes": None,
        "expected_has_dependency": False,
        "has_valid_plan_item_and_workflow": False,
        "expected_jit_event_status": JitEventStatus.COMPLETED,
        "expected_enrich_data": None,
    },
    # test open pr jit event - with existing repo asset, has execution!
    "open_pr_event__has_executions": {
        "jit_event": OpenPRJitEventFactory.build(
            tenant_id=TEST_TENANT_ID,
            asset_id=ASSET_GITHUB_REPO_1.asset_id,
            jit_event_name=JitEventName.OpenFixPullRequest,
        ),
        "plan": MOCK_PLAN,
        "all_assets": ASSETS,
        "expected_triggered_assets": [ASSET_GITHUB_REPO_1],
        "expected_trigger_filter_attributes": TriggerFilterAttributes(
            triggers={JitEventName.OpenFixPullRequest},
            asset_ids={ASSET_GITHUB_REPO_1.asset_id},
            create_trigger_event_from_jit_event=True,
        ),
        "expected_has_dependency": False,
        "has_valid_plan_item_and_workflow": True,
        "expected_jit_event_status": JitEventStatus.STARTED,
        "expected_enrich_data": None,
    },
    # test open pr jit event - with existing non repo asset, no execution!
    "open_pr_event__non_repo_asset__no_executions": {
        "jit_event": OpenPRJitEventFactory.build(
            tenant_id=TEST_TENANT_ID,
            asset_id=ASSET_AWS_WITH_DEPLOYMENT_CONF.asset_id,
            jit_event_name=JitEventName.OpenFixPullRequest,
        ),
        "plan": MOCK_PLAN,
        "all_assets": ASSETS,
        "expected_triggered_assets": [],
        "expected_trigger_filter_attributes": None,
        "expected_has_dependency": False,
        "has_valid_plan_item_and_workflow": True,
        "expected_jit_event_status": JitEventStatus.COMPLETED,
        "expected_enrich_data": None,
    },
    # test open pr jit event - with not existing repo asset, no execution!
    "open_pr_event__no_asset__no_executions": {
        "jit_event": OpenPRJitEventFactory.build(
            tenant_id=TEST_TENANT_ID,
            asset_id=ASSET_GITHUB_REPO_1.asset_id,
            jit_event_name=JitEventName.OpenFixPullRequest,
        ),
        "plan": MOCK_PLAN,
        "all_assets": [ASSET_GITHUB_REPO_2],
        "expected_triggered_assets": [],
        "expected_trigger_filter_attributes": None,
        "expected_has_dependency": False,
        "has_valid_plan_item_and_workflow": True,
        "expected_jit_event_status": JitEventStatus.FAILED,
        "expected_enrich_data": None,
    },
    # test code related jit event - with existing repo asset, has execution!
    "code_related_event__has_executions": {
        "jit_event": CodeRelatedJitEventFactory.build(
            tenant_id=TEST_TENANT_ID,
            asset_id=ASSET_GITHUB_REPO_1.asset_id,
            jit_event_name=JitEventName.PullRequestCreated,
            vendor=VendorEnum('github').value,
            pull_request_number='1',
        ),
        "plan": MOCK_PLAN,
        "all_assets": ASSETS,
        "expected_triggered_assets": [ASSET_GITHUB_REPO_1],
        "expected_trigger_filter_attributes": TriggerFilterAttributes(
            triggers={JitEventName.PullRequestCreated},
            asset_ids={ASSET_GITHUB_REPO_1.asset_id},
            create_trigger_event_from_jit_event=True,
        ),
        "expected_has_dependency": False,
        "has_valid_plan_item_and_workflow": True,
        "expected_jit_event_status": JitEventStatus.STARTED,
        "expected_enrich_data": [
            RepoEnrichmentResult(
                mime_types=['text'],
                languages=['python'],
                package_managers=[],
                frameworks=[],
            )
        ],
    },
    "code_related_event__has_executions_failed_get_pr_change_list": {
        "jit_event": CodeRelatedJitEventFactory.build(
            tenant_id=TEST_TENANT_ID,
            asset_id=ASSET_GITHUB_REPO_1.asset_id,
            jit_event_name=JitEventName.PullRequestCreated,
            vendor=VendorEnum('github').value,
            pull_request_number='1',
        ),
        "plan": MOCK_PLAN,
        "all_assets": ASSETS,
        "expected_triggered_assets": [ASSET_GITHUB_REPO_1],
        "expected_trigger_filter_attributes": TriggerFilterAttributes(
            triggers={JitEventName.PullRequestCreated},
            asset_ids={ASSET_GITHUB_REPO_1.asset_id},
            create_trigger_event_from_jit_event=True,
        ),
        "expected_has_dependency": True,
        "has_valid_plan_item_and_workflow": True,
        "expected_jit_event_status": JitEventStatus.STARTED,
        "expected_enrich_data": None,
    },
    # test code related jit event - with existing non repo asset, no execution!
    "code_related_event__non_repo_asset__no_executions": {
        "jit_event": CodeRelatedJitEventFactory.build(
            tenant_id=TEST_TENANT_ID,
            asset_id=ASSET_AWS_WITH_DEPLOYMENT_CONF.asset_id,
            jit_event_name=JitEventName.PullRequestCreated,
        ),
        "plan": MOCK_PLAN,
        "all_assets": ASSETS,
        "expected_triggered_assets": [],
        "expected_trigger_filter_attributes": None,
        "expected_has_dependency": True,
        "has_valid_plan_item_and_workflow": True,
        "expected_jit_event_status": JitEventStatus.COMPLETED,
        "expected_enrich_data": None,
    },
    # test manual execution jit event - with existing code plan item and asset, has execution!
    "manual_event__code__has_executions": {
        "jit_event": MANUAL_EXECUTION_EVENT_CODE,
        "plan": MOCK_PLAN,
        "all_assets": ASSETS,
        "expected_triggered_assets": [ASSET_GITHUB_REPO_1, ASSET_GITHUB_REPO_2],
        "expected_trigger_filter_attributes": TriggerFilterAttributes(
            plan_item_slugs={MANUAL_EXECUTION_EVENT_CODE.plan_item_slug},
            asset_ids=set(MANUAL_EXECUTION_EVENT_CODE.asset_ids_filter),
            triggers={JitEventName.ManualExecution},
        ),
        "expected_has_dependency": True,
        "has_valid_plan_item_and_workflow": True,
        "expected_jit_event_status": JitEventStatus.STARTED,
        "expected_enrich_data": None,
    },
    # test manual execution jit event - with existing non code plan item and asset, has execution!
    "manual_event__non_code__has_executions": {
        "jit_event": MANUAL_EXECUTION_EVENT_TRIGGER_CLOUD_CONTROL,
        "plan": MOCK_PLAN,
        "all_assets": ASSETS,
        "expected_triggered_assets": [ASSET_AWS_WITH_DEPLOYMENT_CONF],
        "expected_trigger_filter_attributes": TriggerFilterAttributes(
            plan_item_slugs={MANUAL_EXECUTION_EVENT_TRIGGER_CLOUD_CONTROL.plan_item_slug},
            asset_ids=set(MANUAL_EXECUTION_EVENT_TRIGGER_CLOUD_CONTROL.asset_ids_filter),
            triggers={JitEventName.ManualExecution},
        ),
        "expected_has_dependency": False,
        "has_valid_plan_item_and_workflow": True,
        "expected_jit_event_status": JitEventStatus.STARTED,
        "expected_enrich_data": None,
    },
    # test manual execution jit event - with existing code plan item and not existing asset, no execution!
    "manual_event__no_asset__no_executions": {
        "jit_event": MANUAL_EXECUTION_EVENT_TRIGGER_CLOUD_CONTROL,
        "plan": MOCK_PLAN,
        "all_assets": [ASSET_GITHUB_REPO_1, ASSET_GITHUB_REPO_2, ASSET_GITHUB_ORG],
        "expected_triggered_assets": [],
        "expected_trigger_filter_attributes": None,
        "expected_has_dependency": False,
        "has_valid_plan_item_and_workflow": True,
        "expected_jit_event_status": JitEventStatus.COMPLETED,
        "expected_enrich_data": None,
    },
    # test deployment jit event - with existing asset and envs and relevant trigger, has execution!
    "deployment_event__has_executions": {
        "jit_event": DeploymentJitEventFactory.build(
            tenant_id=TEST_TENANT_ID,
            environment="staging",
        ),
        "plan": MOCK_PLAN,
        "all_assets": ASSETS,
        "expected_triggered_assets": [ASSET_DEPLOYMENT, ASSET_AWS_WITH_DEPLOYMENT_CONF],
        "expected_trigger_filter_attributes": TriggerFilterAttributes(
            asset_envs={"staging"},
            triggers={"deployment"},
            plan_item_slugs={"item-web-app-scanner", "item-runtime-misconfiguration-detection"},
        ),
        "expected_has_dependency": False,
        "has_valid_plan_item_and_workflow": True,
        "expected_jit_event_status": JitEventStatus.STARTED,
        "expected_enrich_data": None,
    },
    # test deployment jit event - with existing asset and not existing envs and relevant trigger, no execution!
    "deployment_event__no_relevant_env__no_executions": {
        "jit_event": DeploymentJitEventFactory.build(
            tenant_id=TEST_TENANT_ID,
            environment="qa",
        ),
        "plan": MOCK_PLAN,
        "all_assets": ASSETS,
        "expected_triggered_assets": [],
        "expected_trigger_filter_attributes": TriggerFilterAttributes(
            asset_envs={"staging"},
            triggers={"deployment"},
            plan_item_slugs={"item-web-app-scanner", "item-runtime-misconfiguration-detection"},
        ),
        "expected_has_dependency": False,
        "has_valid_plan_item_and_workflow": True,
        "expected_jit_event_status": JitEventStatus.COMPLETED,
        "expected_enrich_data": None,
    },
    # test no assets in the tenant, no execution!
    "no_assets__no_executions": {
        "jit_event": MANUAL_EXECUTION_EVENT_TRIGGER_CLOUD_CONTROL,
        "plan": MOCK_PLAN,
        "all_assets": [],
        "expected_triggered_assets": [],
        "expected_trigger_filter_attributes": None,
        "expected_has_dependency": False,
        "has_valid_plan_item_and_workflow": True,
        "expected_jit_event_status": JitEventStatus.FAILED,
        "expected_enrich_data": None,
    },
    # test no plan items in the tenant, no execution!
    "no_plan_items__no_executions": {
        "jit_event": MANUAL_EXECUTION_EVENT_TRIGGER_CLOUD_CONTROL,
        "plan": {"items": {}},
        "all_assets": ASSETS,
        "expected_triggered_assets": [],
        "expected_trigger_filter_attributes": None,
        "expected_has_dependency": False,
        "has_valid_plan_item_and_workflow": False,
        "expected_jit_event_status": JitEventStatus.COMPLETED,
        "expected_enrich_data": None,
    },
}

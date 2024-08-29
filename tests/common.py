from datetime import datetime
from typing import Any
from uuid import uuid4

from jit_utils.event_models import (
    JitEvent,
    JitEventName,
    TriggerScheduledTaskJitEvent,
    ManualExecutionJitEvent,
    ResourceAddedJitEvent,
    ItemActivatedJitEvent,
)
from jit_utils.event_models.event_trigger_scheme import EventTriggerScheme
from jit_utils.event_models.third_party.github import (
    WebhookPullRequestEventBody,
    WebhookPullRequestEvent,
    WebhookDeploymentEventBody,
    WebhookDeploymentEvent,
    CodeRelatedJitEvent,
    DeploymentJitEvent,
    OpenPRJitEvent,
    Deployment,
    WebhookRerunEventBody,
    CheckSuite,
    Repository,
    WebhookSingleCheckRerunEventBody,
)
from jit_utils.event_models.trigger_event import (
    BulkTriggerSchemeEvent,
    TriggerScheme)
from jit_utils.models.asset.entities import LimitedAsset
from jit_utils.models.plan.jit_plans import Step
from jit_utils.models.tenant.entities import Installation
from jit_utils.models.trigger.jit_event_life_cycle import JitEventLifeCycleEntity
from pydantic_factories import ModelFactory

from src.lib.constants import PULL_REQUEST_OPENED
from src.lib.models.asset import Asset
from src.lib.models.trigger import (
    WorkflowTemplateWrapper,
    JobTemplateWrapper,
    PrepareForExecutionEvent,
)

test_tenant_id = str(uuid4())
test_time = datetime(2021, 1, 1, 0, 0, 0)


class WebhookPullRequestEventBodyFactory(ModelFactory):
    __model__ = WebhookPullRequestEventBody


class WebhookPullRequestEventFactory(ModelFactory):
    __model__ = WebhookPullRequestEvent


class WebhookDeploymentEventBodyFactory(ModelFactory):
    __model__ = WebhookDeploymentEventBody


class WebhookDeploymentEventFactory(ModelFactory):
    __model__ = WebhookDeploymentEvent


class InstallationFactory(ModelFactory):
    __model__ = Installation
    tenant_id = test_tenant_id
    vendor_response = {}
    vendor_attributes = {}
    centralized_repo_asset = None


class CodeRelatedJitEventFactory(ModelFactory):
    __model__ = CodeRelatedJitEvent
    __allow_none_optionals__ = False
    tenant_id = test_tenant_id


class DeploymentJitEventFactory(ModelFactory):
    __model__ = DeploymentJitEvent
    DEPLOYMENT_WORKFLOW_TRIGGER = "deployment"


class OpenPRJitEventFactory(ModelFactory):
    __model__ = OpenPRJitEvent
    fix_suggestion = {}


class TriggerScheduledTaskJitEventFactory(ModelFactory):
    __model__ = TriggerScheduledTaskJitEvent
    single_execution_time = datetime.now()
    cron_expression = None


class ManualExecutionJitEventFactory(ModelFactory):
    __model__ = ManualExecutionJitEvent


class ResourceAddedJitEventFactory(ModelFactory):
    __model__ = ResourceAddedJitEvent


class ItemActivatedJitEventFactory(ModelFactory):
    __model__ = ItemActivatedJitEvent


class StepFactory(ModelFactory):
    __model__ = Step


class JitEventFactory(ModelFactory):
    __model__ = JitEvent
    tenant_id = test_tenant_id


class DeploymentFactory(ModelFactory):
    __model__ = Deployment
    __allow_none_optionals__ = False


class FilteredWorkflowFactory(ModelFactory):
    __model__ = WorkflowTemplateWrapper
    __allow_none_optionals__ = False


class FilteredJobFactory(ModelFactory):
    __model__ = JobTemplateWrapper
    __allow_none_optionals__ = False


class AssetFactory(ModelFactory):
    __model__ = Asset
    __allow_none_optionals__ = False
    tenant_id = test_tenant_id
    tags = []
    manual_factors = None

    @classmethod
    def build(
            cls,
            factory_use_construct: bool = False,
            **kwargs: Any,
    ) -> LimitedAsset:
        return super().build(factory_use_construct=True, **kwargs)


class LimitedAssetFactory(ModelFactory):
    __model__ = LimitedAsset
    __allow_none_optionals__ = False
    manual_factors = None

    @classmethod
    def build(
            cls,
            factory_use_construct: bool = False,
            **kwargs: Any,
    ) -> LimitedAsset:
        return super().build(factory_use_construct=True, **kwargs)


class GithubInstallationFactory(ModelFactory):
    __model__ = Installation
    __allow_none_optionals__ = False
    tenant_id = str(uuid4())
    centralized_repo_asset = LimitedAssetFactory.build()
    centralized_repo_asset_id = centralized_repo_asset.asset_id


class EventTriggerSchemeFactory(ModelFactory):
    __model__ = EventTriggerScheme
    __allow_none_optionals__ = False


class TriggerSchemeFactory(ModelFactory):
    __model__ = TriggerScheme
    __allow_none_optionals__ = False
    jit_event = OpenPRJitEventFactory


class BulkTriggerSchemeEventFactory(ModelFactory):
    __model__ = BulkTriggerSchemeEvent
    trigger_schemes = [TriggerSchemeFactory.build() for i in range(10)]


class PrepareForExecutionEventFactory(ModelFactory):
    __model__ = PrepareForExecutionEvent
    __allow_none_optionals__ = False
    jit_event = JitEventFactory.build()
    filtered_assets = AssetFactory.build()
    filtered_jobs = FilteredJobFactory.build()


class WebhookRerunEventBodyFactory(ModelFactory):
    __model__ = WebhookRerunEventBody
    __allow_none_optionals__ = False


class WebhookSingleCheckRerunEventBodyFactory(ModelFactory):
    __model__ = WebhookSingleCheckRerunEventBody
    __allow_none_optionals__ = False


class CheckSuiteFactory(ModelFactory):
    __model__ = CheckSuite
    __allow_none_optionals__ = False


class RepositoryFactory(ModelFactory):
    __model__ = Repository
    __allow_none_optionals__ = False


class JitEventLifeCycleEntityFactory(ModelFactory):
    __model__ = JitEventLifeCycleEntity
    __allow_none_optionals__ = True

    created_at = str(test_time.isoformat())
    modified_at = None
    total_assets = None
    plan_item_slugs = []
    remaining_assets = None
    tenant_id = test_tenant_id


class DefaultSetup:
    vendor = 'some_vendor'
    asset_id = 'some_asset_id'
    installation = GithubInstallationFactory.build()
    installation_id = installation.installation_id
    pull_request_webhook_event = WebhookPullRequestEventFactory.build(
        vendor=vendor,
        event_type=PULL_REQUEST_OPENED,
        webhook_body_json=WebhookPullRequestEventBodyFactory.build())
    pull_request_event_body = WebhookPullRequestEventBodyFactory.build()
    tenant_id = installation.tenant_id
    app_id = installation.app_id

    pull_request_event_body.installation.id = installation_id
    jit_event_name = JitEventName.PullRequestCreated


DUMMY_BASE_URL = "https://api.dummy.jit.io"

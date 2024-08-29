import json
import random
from datetime import datetime, timedelta
from random import choice
from typing import List, get_args, Dict, Optional, Union
from uuid import uuid4

from freezegun import freeze_time
from jit_utils.event_models import JitEvent, JitEventTypes
from jit_utils.event_models.third_party.github import Commits
from jit_utils.event_models.trigger_event import TriggerExecutionEvent
from jit_utils.jit_event_names import JitEventName
from jit_utils.models.asset.entities import Asset, AssetType
from jit_utils.models.controls import ControlType
from jit_utils.models.execution import CallbackUrls
from jit_utils.models.execution import Execution
from jit_utils.models.execution_context import Centralized, RepoEnrichmentResult, CI_RUNNERS
from jit_utils.models.execution_context import ExecutionContext
from jit_utils.models.execution_context import Runner
from jit_utils.models.execution_context import RunnerConfig
from jit_utils.models.execution_context import RunnerSetup
from jit_utils.models.execution_context import WorkflowJob
from jit_utils.models.execution_priority import ExecutionPriority
from jit_utils.models.findings.events import UploadFindingsStatus
from jit_utils.models.oauth.entities import VendorEnum
from jit_utils.models.plan.jit_plans import Step
from pydantic import parse_obj_as
from pydantic_factories import ModelFactory

from src.lib.cores.fargate.constants import GITHUB_ORG_MFA_IMAGE_URL, ZAP_IMAGE_URL
from src.lib.data.executions_manager import ExecutionsManager
from src.lib.data.resources_manager import ResourcesManager
from src.lib.endpoints import (EXECUTION_CALLBACK_URL, GET_FINDING_SCHEMA_BY_VERSION_CALLBACK_URL, IGNORES_CALLBACK_URL,
                               PRESIGNED_LOGS_UPLOAD_URL, UPDATE_FINDING_CALLBACK_URL, ACTIONS_CALLBACK_URL)
from src.lib.models.execution_models import ExecutionData, ExecutionStatus, UpdateRequest
from src.lib.models.workflow_models import ControlStatusDetails
from tests.factories import CodeRelatedJitEventFactory, ExecutionContextWorkflowFactory
from tests.mocks.asset_mocks import MOCK_ASSET, MOCK_ASSET_ID
from tests.mocks.installation_mocks import MOCK_INSTALLATION, MOCK_INSTALLATION_ID
from tests.mocks.tenant_mocks import MOCK_TENANT_ID

MOCK_PLAN_ITEM_SLUG = 'item-mock-plan-item'
MOCK_EXECUTION_ID = '8429eb01-2ecb-43fc-933f-4e20480f5306'
MOCK_JIT_EVENT_ID = 'dd7cb9e9-dca6-4012-9401-63a842ee77e9'
MOCK_ASSET_NAME = 'test_repo'


class CentralizedFactory(ModelFactory):
    __model__ = Centralized


MOCK_JIT_EVENT = JitEvent(
    tenant_id=MOCK_TENANT_ID,
    jit_event_name='pull_request_created',
    jit_event_id=MOCK_JIT_EVENT_ID,
    asset_id=MOCK_ASSET_ID,
    workflows={}
)

MOCK_CODE_RELATED_JIT_EVENT = CodeRelatedJitEventFactory.build(
    tenant_id=MOCK_TENANT_ID,
    jit_event_name='pull_request_created',
    jit_event_id=MOCK_JIT_EVENT_ID,
    asset_id=MOCK_ASSET_ID,
    workflows={},
    original_repository="repo"
)

MOCK_EXECUTION_CONTEXT_CODE_EXECUTION = ExecutionContext(
    jit_event=MOCK_CODE_RELATED_JIT_EVENT,
    asset=MOCK_ASSET,
    installation=MOCK_INSTALLATION,
    config={},
    integration={},
    job=WorkflowJob(**{
        'runner': {'type': random.choice(CI_RUNNERS)},
        'job_name': 'job-0',
        'steps': [{'name': 'control-0', 'uses': './.github/actions/least-privileged'}]}),
    centralized=CentralizedFactory.build(),
    workflow=ExecutionContextWorkflowFactory.build(),
    enrichment_result=RepoEnrichmentResult(mime_types={"text"}, languages={"java"}, frameworks=[], package_managers=[]),
)

MOCK_EXECUTION_CONTEXT_JIT_RUNNER = ExecutionContext(
    jit_event=MOCK_JIT_EVENT,
    asset=MOCK_ASSET,
    installation=MOCK_INSTALLATION,
    config={},
    integration={},
    job=WorkflowJob(**{
        'runner': {'type': Runner.JIT},
        'job_name': 'job-0',
        'steps': [{'name': 'control-0', 'uses': './.github/actions/least-privileged'}]}),
    centralized=CentralizedFactory.build(),
    workflow=ExecutionContextWorkflowFactory.build(),
)


def _get_mock_execution_context(
        jit_event_fields: Dict = None,
        asset_fields: Dict = None,
        job_fields: Dict = None,
        runner: Runner = Runner.CI,
) -> ExecutionContext:
    if jit_event_fields is None:
        jit_event_fields = dict()
    if asset_fields is None:
        asset_fields = dict()
    if job_fields is None:
        job_fields = dict()

    if runner in CI_RUNNERS:
        context = MOCK_EXECUTION_CONTEXT_CODE_EXECUTION
    else:
        context = MOCK_EXECUTION_CONTEXT_JIT_RUNNER

    return ExecutionContext(**{
        **context.dict(),
        "jit_event": parse_obj_as(JitEventTypes, {**MOCK_JIT_EVENT.dict(), **jit_event_fields}),
        "asset": Asset(**{**MOCK_ASSET.dict(), **asset_fields}),
        "job": WorkflowJob(**{**context.job.dict(), **job_fields}),
        "workflow": ExecutionContextWorkflowFactory.build(),
    })


def generate_status() -> str:
    """
    Generates a status.

    :return: A status.
    """
    return choice([ExecutionStatus.COMPLETED, ExecutionStatus.FAILED]).value


def generate_runner() -> str:
    """
    Generates a runner.

    :return: A runner.
    """
    return choice(["jit", "github"])


def generate_status_details(i: int) -> ControlStatusDetails:
    return ControlStatusDetails(
        message="dummy-message",
        url="dummy-url",
        url_text="dummy-url-text"
    )


def generate_asset_type_and_related_data():
    return choice(get_args(AssetType))


def generate_has_findings():
    return choice([True, False])


MOCK_EXECUTION_SERVICE_URL = 'https://api.jit.io/execution'
MOCK_FINDINGS_SERVICE_URL = 'https://api.jit.io/findings'
MOCK_ACTIONS_SERVICE_URL = 'https://api.jit.io/actions'


def generate_mock_callback_urls(
        asset_id: str,
        presigned_findings_upload_url: Optional[str] = None,
) -> CallbackUrls:
    """
    Generate a mock callback url for the given jit_event_id, execution_id and asset_id.
    """

    callback_urls = CallbackUrls(
        base_api="https://api.jit-dev.io",
        execution=EXECUTION_CALLBACK_URL.format(base=MOCK_EXECUTION_SERVICE_URL),
        ignores=IGNORES_CALLBACK_URL.format(base=MOCK_FINDINGS_SERVICE_URL,
                                            asset_id=asset_id,
                                            control_name="{control_name}"),
        presigned_logs_upload_url=PRESIGNED_LOGS_UPLOAD_URL,
        finding_schema=GET_FINDING_SCHEMA_BY_VERSION_CALLBACK_URL.format(base=MOCK_FINDINGS_SERVICE_URL,
                                                                         schema_type="{schema_type}",
                                                                         schema_version="{schema_version}"),
        update_finding_url=UPDATE_FINDING_CALLBACK_URL.format(base=MOCK_FINDINGS_SERVICE_URL,
                                                              finding_id='{finding_id}'),
        actions=ACTIONS_CALLBACK_URL.format(base=MOCK_ACTIONS_SERVICE_URL, action_id='{action_id}',
                                            finding_id='{finding_id}'),
    )
    if presigned_findings_upload_url:
        callback_urls.presigned_findings_upload_url = presigned_findings_upload_url
    return callback_urls


@freeze_time("2022-12-05")
def generate_mock_executions(
        executions_amount: int,
        tenant_id: str = MOCK_TENANT_ID,
        status: ExecutionStatus = ExecutionStatus.PENDING,
        plan_item_slug: Optional[str] = None,
        affected_plan_items: Optional[List[str]] = None,
        job_runner: Runner = Runner.CI,
        execution_timeout: Optional[str] = None,
        job_name: Optional[str] = 'job-1',
        single_jit_event_id: Optional[str] = None,
        run_id: Optional[str] = None,
        control_type: ControlType = ControlType.DETECTION,
        priority: ExecutionPriority = None,
        jit_event_fields: Optional[Dict] = None,
        created_at: Optional[datetime] = None,
) -> List[Execution]:
    """
    Generates a list of mock executions.

    :param executions_amount: The number of executions to generate.
    :param tenant_id: The tenant id of the executions.
    :param status: The status of the executions.
    :param plan_item_slug: The slug of the plan item of the executions.
    :param affected_plan_items: The slugs of the plan items of the executions that caused the trigger.
    :param job_runner: The job runner type of the executions.
    :param execution_timeout: The execution_timeout of the executions.
    :param single_jit_event_id: The jit_event_id of the executions.
    :param run_id: The run id in the vendor
    :param job_name: The job name of the executions.
    :param control_type:
    :param priority:
    :param jit_event_fields: The fields of the jit event.
    :param created_at: The created_at timestamp of the executions.
    :return: A list of mock executions.
    """

    def _generate_execution(i: int) -> Execution:
        execution_id = str(uuid4())
        jit_event_id = str(uuid4()) if not single_jit_event_id else single_jit_event_id
        asset_id = str(uuid4())
        asset_name = f"asset-{i}"
        asset_type = generate_asset_type_and_related_data()
        steps = [Step(name=f"control-{i}", uses=f"control-image-{i}")]
        context = _get_mock_execution_context(
            jit_event_fields=jit_event_fields or {
                "tenant_id": tenant_id,
                "jit_event_name": JitEventName.TriggerScheduledTask,  # Low priority event
                "jit_event_id": jit_event_id,
                "asset_id": asset_id,
            },
            asset_fields={
                "asset_id": asset_id,
                "asset_type": asset_type,
                "asset_name": asset_name,
            },
            job_fields={
                "job_name": job_name,
                "runner": RunnerConfig(
                    setup=RunnerSetup(
                        mount=False, assume_role=False, checkout=True, account_id=""
                    ),
                    type=job_runner
                ),
                "steps": steps,
            }
        )
        execution = Execution(
            **context.dict(exclude_none=True),  # TODO: remove this after removing the FF
            **context.jit_event.dict(exclude_none=True),  # TODO: remove this after removing the FF
            context=context,
            execution_id=execution_id,
            plan_item_slug=plan_item_slug or f"item-{i}",
            affected_plan_items=affected_plan_items or [f"item-{i}", f"item-{i + 1}"],
            workflow_slug=f"workflow-{i}",
            job_name=job_name,
            control_name=f"control-{i}",
            control_image=f"control-image-{i}",
            control_type=control_type,
            vendor=VendorEnum.GITHUB,
            created_at=(created_at + timedelta(seconds=i)).isoformat(),
            created_at_ts=int((created_at + timedelta(seconds=i)).timestamp()),
            registered_at=(datetime.now() + timedelta(seconds=3 + i)).isoformat(),
            registered_at_ts=int((datetime.now() + timedelta(seconds=3 + i)).timestamp()),
            completed_at=(datetime.now() + timedelta(seconds=30 + i)).isoformat(),
            completed_at_ts=int((datetime.now() + timedelta(seconds=30 + i)).timestamp()),
            status=status or generate_status(),
            has_findings=generate_has_findings(),
            status_details=generate_status_details(i),
            job_runner=job_runner,
            plan_slug=f"plan-{i}",
            asset_name=asset_name,
            asset_type=asset_type,
            run_id=run_id,
        )
        if priority:
            execution.priority = priority
        if execution_timeout:
            execution.execution_timeout = execution_timeout
        return execution

    if created_at is None:
        created_at = datetime.now()

    return [
        _generate_execution(i)
        for i in range(executions_amount)
    ]


def generate_mock_trigger_execution_events(
        amount: int, tenant_id: str, jit_event_fields: Optional[Dict] = None
) -> List[TriggerExecutionEvent]:
    """Dirty code I copied to generate a mock trigger execution event

    # TODO: Write proper logic
    """
    mock_executions = generate_mock_executions(executions_amount=amount, tenant_id=tenant_id,
                                               jit_event_fields=jit_event_fields)
    return [
        TriggerExecutionEvent(
            **{
                **e.dict(),
                "jit_event": e.context.jit_event,
                "affected_plan_items": e.affected_plan_items,
            }
        )
        for e in mock_executions
    ]


MOCK_STATUS_DETAILS = ControlStatusDetails(
    message="dummy-message",
    url="dummy-url",
    url_text="dummy-url-text"
)

MOCK_EXECUTION: Execution = Execution(
    **Execution(
        context=MOCK_EXECUTION_CONTEXT_CODE_EXECUTION,
        tenant_id=MOCK_TENANT_ID,
        execution_id=MOCK_EXECUTION_ID,
        entity_type='job',
        plan_item_slug='item-0',
        workflow_slug='workflow-0',
        job_name='job-0',
        control_name='control-0',
        vendor="github",
        jit_event_name='pull_request_created',
        jit_event_id=MOCK_JIT_EVENT_ID,
        created_at='2022-04-04T12:01:14.740288',
        created_at_ts=1649062874,
        registered_at='2022-04-04T12:01:17.740344',
        registered_at_ts=1649062877,
        completed_at='2022-04-04T12:01:44.740358',
        completed_at_ts=1649062904,
        control_type=ControlType.DETECTION,
        status=ExecutionStatus.FAILED,
        has_findings=False,
        status_details=MOCK_STATUS_DETAILS,
        job_runner=random.choice(CI_RUNNERS),
        priority=ExecutionPriority.HIGH,
        plan_slug='plan-0',
        asset_type='repo',
        asset_name='asset-service',
        asset_id=MOCK_ASSET_ID,
        control_image='control-image-0',
    ).dict()
)

MOCK_EXECUTION_ENRICHMENT = Execution(**{**MOCK_EXECUTION.dict(), "control_type": ControlType.ENRICHMENT})

MOCK_UPDATE_REQUEST = UpdateRequest(
    tenant_id=MOCK_TENANT_ID,
    jit_event_id=MOCK_JIT_EVENT_ID,
    execution_id=MOCK_EXECUTION_ID,
    registered_at='2022-04-04T12:01:17.740344',
    registered_at_ts=1649062877,
    status=ExecutionStatus.COMPLETED,
    original_request={"key": "value"}
)

MOCK_UPDATE_UPLOAD_FINDINGS_REQUEST = UpdateRequest(
    tenant_id=MOCK_TENANT_ID,
    jit_event_id=MOCK_JIT_EVENT_ID,
    execution_id=MOCK_EXECUTION_ID,
    status=UploadFindingsStatus.COMPLETED,
)

MOCK_REGISTER_REQUEST = UpdateRequest(
    tenant_id=MOCK_TENANT_ID,
    jit_event_id=MOCK_JIT_EVENT_ID,
    execution_id=MOCK_EXECUTION_ID,
    original_request={"key": "value"}
)

MOCK_COMPLETE_REQUEST = UpdateRequest(
    tenant_id=MOCK_TENANT_ID,
    jit_event_id=MOCK_JIT_EVENT_ID,
    execution_id=MOCK_EXECUTION_ID,
    completed_at='2022-04-04T12:01:44.740358',
    completed_at_ts=1649062904,
    status=ExecutionStatus.COMPLETED,
    has_findings=True,
    status_details=MOCK_STATUS_DETAILS,
    original_request={"key": "value"}
)

# Mock execution object that should be received by the "enrich and dispatch
# execution" lambda on execution of AppSec control
MOCK_EXECUTION_CODE_EVENT = Execution(**Execution(
    context=MOCK_EXECUTION_CONTEXT_CODE_EXECUTION,
    tenant_id=MOCK_TENANT_ID,
    execution_id=MOCK_EXECUTION_ID,
    entity_type='job',
    plan_item_slug='item-0',
    affected_plan_items=['item-0', 'item-1'],
    workflow_slug='workflow-0',
    job_name='job-0',
    control_name='control-0',
    control_image='control_image',
    control_type=ControlType.DETECTION,
    vendor=VendorEnum.GITHUB,
    jit_event_name='pull_request_created',
    jit_event_id=MOCK_JIT_EVENT_ID,
    created_at='2022-04-04T12:01:14.740288',
    job_runner=random.choice(CI_RUNNERS),
    plan_slug='plan-0',
    asset_type='repo',
    asset_name='asset-service',
    asset_id=MOCK_ASSET_ID,
    additional_attributes=dict(
        app_id='1e40b765-79bc-42e3-bf24-624b3b1beee5',
        installation_id=MOCK_INSTALLATION_ID,
        original_repository='execution_service',
        owner='jitsecurity',
        vendor='github',
        branch='master',
        pull_request_number='1',
        commits=Commits(base='base', head='head'),
        user_vendor_id='user_vendor_id',
        user_vendor_name='user_vendor_name',
        languages=['python', 'javascript'],
        centralized_repo_asset_name='not-dot-jit'
    )
).dict())

MOCK_EXECUTION_CODE_EVENT_ENRICHMENT = Execution(**{**MOCK_EXECUTION_CODE_EVENT.dict(),
                                                    "control_type": ControlType.ENRICHMENT})

MOCK_EXECUTION_FARGATE_AWS_ACCOUNT_EVENT = Execution(
    context=_get_mock_execution_context(
        jit_event_fields={'jit_event_name': 'pull_request_created'},
        job_fields={'runner': {'type': Runner.JIT}, 'job_name': 'job-0'},
    ),
    tenant_id=MOCK_TENANT_ID,
    execution_id=MOCK_EXECUTION_ID,
    entity_type='job',
    plan_item_slug='item-0',
    workflow_slug='workflow-0',
    job_name='job-0',
    control_name='control-0',
    control_image="",
    control_type=ControlType.DETECTION,
    vendor="aws",
    jit_event_name=JitEventName.PullRequestCreated,  # This is a high-priority event
    jit_event_id=MOCK_JIT_EVENT_ID,
    created_at='2022-04-04T12:01:14.740288',
    job_runner=Runner.JIT,
    plan_slug='plan-0',
    asset_type="aws_account",
    asset_name='aws',
    asset_id=MOCK_ASSET_ID,
    additional_attributes=dict(
        installation_id='123331154',
        assume_role_id='123331154',
        account_name='test',
    )
)

MOCK_EXECUTION_FARGATE_ZAP_ACCOUNT_EVENT = Execution(
    context=_get_mock_execution_context(
        jit_event_fields={'jit_event_name': 'pull_request_created'},
        job_fields={'runner': {'type': Runner.JIT}, 'job_name': 'job-0'},
        runner=Runner.JIT,
    ),
    tenant_id=MOCK_TENANT_ID,
    execution_id=MOCK_EXECUTION_ID,
    entity_type='job',
    plan_item_slug='item-0',
    workflow_slug='workflow-0',
    job_name='job-0',
    control_name='control-0',
    control_image=ZAP_IMAGE_URL,
    control_type=ControlType.DETECTION,
    vendor="aws",
    jit_event_name='pull_request_created',
    jit_event_id=MOCK_JIT_EVENT_ID,
    created_at='2022-04-04T12:01:14.740288',
    job_runner=Runner.JIT,
    plan_slug='plan-0',
    asset_type="api",
    asset_name='aws',
    asset_id=MOCK_ASSET_ID,
    additional_attributes=dict(target_url='https://example.jit.io')
)
MOCK_EXECUTION_FARGATE_ZAP_ACCOUNT_EVENT_CONTAINS_SECRETS = Execution(
    context=_get_mock_execution_context(
        jit_event_fields={'jit_event_name': 'pull_request_created'},
        job_fields={'runner': {'type': Runner.JIT}, 'job_name': 'job-0',
                    'steps': [
                        {
                            "name": "Run Bandit",
                            "uses": "121169888995.dkr.ecr.us-east-1.amazonaws.com/some-job-definition:latest",
                            "params": {
                                "args": "${{jit_secrets.secret1}} -e ${{secret.GITHUB_Secret}}",
                                "env": {
                                    'AWS_ACCESS': "${{ jit_secrets.AWS_ACCESS_DUMMY }}",
                                    'AWS_ACCESS2': "${{ jit_secrets.AWS_ACCESS_DUMMY2 }}",
                                    'conditional_var':
                                        '${{ fromJSON(["jit_secrets.Dummy_sec","-v $(pwd)/code:/code"])'
                                        '[((!(fromJSON(jit_secrets.Dummy_sec))'
                                        ' || (fromJSON(secrets.test1).is_start == jit_secrets.Dummy_sec2)))] }}'

                                }
                            }
                        }

                    ]}
    ),
    tenant_id=MOCK_TENANT_ID,
    execution_id=MOCK_EXECUTION_ID,
    entity_type='job',
    plan_item_slug='item-0',
    workflow_slug='workflow-0',
    job_name='job-0',
    control_name='control-0',
    control_image=ZAP_IMAGE_URL,
    control_type=ControlType.DETECTION,
    vendor="aws",
    jit_event_name=JitEventName.PullRequestCreated,  # This is a high-priority event
    jit_event_id=MOCK_JIT_EVENT_ID,
    created_at='2022-04-04T12:01:14.740288',
    job_runner=Runner.JIT,
    plan_slug='plan-0',
    asset_type="api",
    asset_name='aws',
    asset_id=MOCK_ASSET_ID,
    additional_attributes=dict(target_url='https://example.jit.io')
)

CONTEXT_WITH_AUTH_AND_SECRETS = _get_mock_execution_context(
    jit_event_fields={'jit_event_name': 'pull_request_created'},
    job_fields={
        'runner':
            {
                'type': Runner.JIT,
                'setup': {"auth_type": "aws_iam_role"}
            },
        'job_name': 'job-0',
        'steps':
            [
                {
                    "name": "Run Bandit",
                    "uses": "ghcr.io/jitsecurity-controls/control-bandit-slim:latest",
                    "params": {
                        "args": "${{jit_secrets.secret1}} -e ${{secret.GITHUB_Secret}}",
                        "env": {
                            'AWS_ACCESS': "${{ jit_secrets.AWS_ACCESS_DUMMY }}",
                            'AWS_ACCESS2': "${{ jit_secrets.AWS_ACCESS_DUMMY2 }}",
                            'conditional_var':
                                '${{ fromJSON(["jit_secrets.Dummy_sec","-v $(pwd)/code:/code"])'
                                '[((!(fromJSON(jit_secrets.Dummy_sec))'
                                ' || (fromJSON(secrets.test1).is_start == jit_secrets.Dummy_sec2)))] }}'

                        }
                    }
                }

            ]
    }
)

MOCK_EXECUTION_FARGATE_ZAP_ACCOUNT_EVENT_CONTAINS_SECRETS_AND_ASSUME_ROLE = Execution(
    context=CONTEXT_WITH_AUTH_AND_SECRETS,
    tenant_id=MOCK_TENANT_ID,
    execution_id=MOCK_EXECUTION_ID,
    entity_type='job',
    plan_item_slug='item-0',
    workflow_slug='workflow-0',
    job_name='job-0',
    control_name='control-0',
    control_image=ZAP_IMAGE_URL,
    control_type=ControlType.DETECTION,
    vendor="aws",
    jit_event_name=JitEventName.PullRequestCreated,  # This is a high-priority event
    jit_event_id=MOCK_JIT_EVENT_ID,
    created_at='2022-04-04T12:01:14.740288',
    job_runner=Runner.JIT,
    plan_slug='plan-0',
    asset_type="api",
    asset_name='aws',
    asset_id=MOCK_ASSET_ID,
    additional_attributes=dict(target_url='https://example.jit.io')
)

MOCK_EXECUTION_GITHUB_ORG_EVENT = Execution(
    context=_get_mock_execution_context(jit_event_fields={'jit_event_name': 'item_activated'}, job_fields={
        'runner': {'type': Runner.JIT}, 'job_name': 'mfa-github-checker'
    }),
    tenant_id=MOCK_TENANT_ID,
    execution_id=MOCK_EXECUTION_ID,
    entity_type='job',
    plan_item_slug='item-mfa-scm',
    workflow_slug='workflow-mfa-github-checker',
    job_name='mfa-github-checker',
    control_name='Run MFA checker',
    control_image=GITHUB_ORG_MFA_IMAGE_URL,
    control_type=ControlType.DETECTION,
    vendor="github",
    jit_event_name=JitEventName.ItemActivated,  # This is a low-priority event
    jit_event_id=MOCK_JIT_EVENT_ID,
    created_at='2022-04-04T12:01:14.740288',
    job_runner=Runner.JIT,
    plan_slug='jit-plan',
    asset_type="org",
    asset_name='github-org',
    asset_id=MOCK_ASSET_ID,
    additional_attributes=dict(owner='jitsecurity', installation_id='31408834', app_id='161076')
)

MOCK_EXECUTION_GITHUB_REPO_EVENT = Execution(
    context=_get_mock_execution_context(
        jit_event_fields={'jit_event_name': 'item_activated'},
        job_fields={'runner': {'type': Runner.JIT}, 'job_name': 'mfa-github-checker'}
    ),
    tenant_id=MOCK_TENANT_ID,
    execution_id=MOCK_EXECUTION_ID,
    entity_type='job',
    plan_item_slug='item-mfa-scm',
    workflow_slug='workflow-mfa-github-checker',
    job_name='mfa-github-checker',
    control_name='Run MFA checker',
    control_image=GITHUB_ORG_MFA_IMAGE_URL,
    control_type=ControlType.DETECTION,
    vendor="github",
    jit_event_name=JitEventName.ItemActivated,  # This is a low-priority event
    jit_event_id=MOCK_JIT_EVENT_ID,
    created_at='2022-04-04T12:01:14.740288',
    job_runner=Runner.JIT,
    plan_slug='jit-plan',
    asset_type="repo",
    asset_name='github-org',
    asset_id=MOCK_ASSET_ID,
    additional_attributes=dict(
        app_id='1e40b765-79bc-42e3-bf24-624b3b1beee5',
        installation_id=MOCK_INSTALLATION_ID,
        original_repository='execution_service',
        owner='jitsecurity',
        vendor='github',
        branch='master',
        pull_request_number='1',
        commits=Commits(base='base', head='head'),
        user_vendor_id='user_vendor_id',
        user_vendor_name='user_vendor_name',
        languages=['python', 'javascript']
    )
)

MOCK_CALLBACK_URLS = CallbackUrls(
    workflow='https://api.jit.io/execution',
    execution='https://api.jit.io/execution',
    findings=f'https://api.jit.io/findings/asset/{MOCK_ASSET_ID}/new',
    presigned_findings_upload_url='https://s3.aws.com',
    ignores=f'https://api.jit.io/findings/asset/{MOCK_ASSET_ID}'
            '/control/{control_name}/ignore/new',
    logs=f'https://api.jit.io/execution/jit-event/{MOCK_JIT_EVENT_ID}/execution/{MOCK_EXECUTION_ID}/log',
    presigned_logs_upload_url='https://s3.aws.com',
    finding_schema='https://api.jit.io/findings/schema/{schema_type}/version/{schema_version}',
)

MOCK_DYNAMODB_STREAM_INSERT_EVENT = {
    'Records': [
        {
            'eventID': '0',
            'eventName': 'INSERT',
            'dynamodb': {
                'NewImage': {
                    'tenant_id': {'S': MOCK_TENANT_ID},
                    'plan_item_slug': {'S': 'item-mfa-scm'},
                    'created_at': {'S': '2022-04-18T08:01:04.554421'},
                    'asset_id': {'S': 'c563d1e9-46f0-4ae8-8518-9b902b71842a'},
                    'plan_slug': {'S': 'jit-plan'},
                    'execution_id': {'S': MOCK_EXECUTION_ID},
                    'priority': {'N': '1'},

                    "context": {
                        "M": {
                            "workflow": {
                                "M": {
                                    "default": {"BOOL": "True"},
                                    "depends_on": {"L": [{"S": "workflow-enrichment-code"}]},
                                    "name": {"S": "Secret Detection Workflow"},
                                    "plan_item_template_slug": {"S": "item-secret-detection"},
                                    "type": {"S": "workflow"},
                                    "slug": {"S": "workflow-secret-detection"},
                                    "content": {
                                        "S": ""},
                                    "asset_types": {
                                        "L": [{"S": "repo"}, {"S": "repo"}]}}},
                            "jit_event": {
                                "M": {
                                    "tenant_id": {"S": MOCK_TENANT_ID},
                                    "owner": {"S": "owner"},
                                    "event_signature": {
                                        "S": "github--ac571f22-8362-41cd-b8e8-088bac9b100e-None-"},
                                    "user_vendor_name": {"S": "Eyal"},
                                    "jit_event_name": {"S": "merge_default_branch"},
                                    "original_repository": {"S": "repo"},
                                    "centralized_repo_asset_id": {"S": "799f1b87-93da-4f03-bf1c-b28670c48057"},
                                    "languages": {"L": []},
                                    "installation_id": {"S": "20629849"},
                                    "asset_id": {"S": "ac571f22-8362-41cd-b8e8-088bac9b100e"},
                                    "branch": {"S": "develop"},
                                    "centralized_repo_files_location": {"S": ".jit/"},
                                    "jit_event_id": {"S": "0ab6944a-1cc9-4a40-82a6-9ccfed44a59c"},
                                    "user_vendor_id": {"S": "79972883"},
                                    "vendor": {"S": "github"},
                                    "commits": {"M": {"base_sha": {"S": ""}}},
                                    "ci_workflow_files_path": {"L": [{"S": ".github/workflows/jit-security.yml"}]},
                                    "centralized_repo_asset_name": {"S": ".jit"},
                                    "app_id": {"S": "142441"}
                                }
                            },
                            "installation": {
                                "M": {
                                    "tenant_id": {"S": MOCK_TENANT_ID},
                                    "owner": {"S": "a-b"},
                                    "creator": {"S": "a-b"},
                                    "is_active": {"BOOL": "True"},
                                    "centralized_repo_asset_id": {"S": "799f1b87-93da-4f03-bf1c-b28670c48057"},
                                    "installation_id": {"S": "20629849"},
                                    "created_at": {"S": "2021-11-10T14:11:07.954499"},
                                    "vendor_attributes": {"M": {"repository_selection": {"S": "all"}}},
                                    "vendor": {"S": "github"},
                                    "name": {"S": "a-b"},
                                    "centralized_repo_asset": {
                                        "M": {
                                            "tenant_id": {"S": MOCK_TENANT_ID},
                                            "owner": {"S": MOCK_TENANT_ID},
                                            "is_active": {"BOOL": "True"},
                                            "risk_score": {"N": "0"},
                                            "created_at": {"S": "2021-11-10T14:11:10.349322"},
                                            "asset_id": {"S": "799f1b87-93da-4f03-bf1c-b28670c48057"},
                                            "is_covered": {"BOOL": "True"},
                                            "tags": {"L": []},
                                            "score": {"N": "0"},
                                            "asset_name": {"S": ".jit"},
                                            "vendor": {"S": "github"},
                                            "asset_type": {"S": "repo"},
                                            "modified_at": {"S": "2022-08-25T16:20:15.960000"},
                                            "is_branch_protected_by_jit": {"BOOL": "False"}
                                        }
                                    },
                                    "modified_at": {"S": "2023-01-09T16:03:23.018000"},
                                    "app_id": {"S": "142441"},
                                    "status": {"S": "connected"}
                                }
                            },
                            "asset": {
                                "M": {
                                    "tenant_id": {"S": MOCK_TENANT_ID},
                                    "owner": {"S": "a-b"},
                                    "is_active": {"BOOL": "True"},
                                    "risk_score": {"N": "0"},
                                    "created_at": {"S": "2022-05-19T22:51:16.030612"},
                                    "asset_id": {"S": "ac571f22-8362-41cd-b8e8-088bac9b100e"},
                                    "is_covered": {"BOOL": "True"},
                                    "tags": {"L": []},
                                    "score": {"N": "50"},
                                    "asset_name": {"S": "my_asset"},
                                    "is_archived": {"BOOL": "False"},
                                    "vendor": {"S": "github"},
                                    "asset_type": {"S": "repo"},
                                    "modified_at": {"S": "2023-09-21T16:52:03.193139"},
                                    "is_branch_protected_by_jit": {"BOOL": "False"}
                                }
                            },
                            "job": {
                                "M": {
                                    "condition": {"M": {"mime_types": {"L": [{"S": "text"}]}}},
                                    "job_name": {"S": "secret-detection"},
                                    "runner": {"M": {
                                        "setup": {"M": {"checkout": {"BOOL": "True"}}},
                                        "type": {"S": "github_actions"}}},
                                    "steps": {
                                        "L": [
                                            {"M": {"name": {"S": "Run Gitleaks"},
                                                   "uses": {"S": "registry.jit.io/control-gitleaks-alpine:latest"},
                                                   "params": {"M": {
                                                       "args": {
                                                           "S": "detect --config $GITLEAKS_CONFIG_FILE_PATH --"
                                                                "source ${WORK_DIR:-.} -v --report-format "
                                                                "json --report-path $REPORT_FILE --redact --"
                                                                "no-git --exit-code 0"
                                                       },
                                                       "output_file": {"S": "/tmp/report.json"}}}}}]}}},
                            "integration": {
                                'M': {
                                    'drata': {
                                        'M': {
                                            'workspace': {
                                                'S': 'Drata Partners'
                                            },
                                            'user_email': {
                                                'S': 'jit@dratapartners.com'
                                            }
                                        }
                                    }
                                }
                            },
                            "config": {
                                "M": {
                                    "github_branch_protection": {
                                        "M": {
                                            "organization": {
                                                "M": {
                                                    "required_status_checks": {
                                                        "L": [
                                                            {
                                                                "S": "Jit Security"
                                                            }
                                                        ]
                                                    },
                                                }}}},
                                    "applications": {
                                        "L": [{"M": {"authentication_value": {
                                            "S": "${{ jit_secrets.web_scan_authentication_value }}"},
                                            "authentication_mode": {"S": "local-storage"},
                                            "application_name": {"S": "app_stg"},
                                            "exclude_paths": {"L": []}, "authentication_key": {"S": "jwt"},
                                            "target_url": {"S": "https://my_webapp.in"},
                                            "api_domain": {"S": "mywebapp_domain.io"},
                                            "type": {"S": "web"}}}]}}},
                            "centralized": {"M": {"centralized_repo_files_location": {"S": ".jit/"},
                                                  "ci_workflow_files_path": {
                                                      "L": [{"S": ".github/workflows/jit-security.yml"}]}}}}},
                    'jit_event_id': {'S': MOCK_JIT_EVENT_ID},
                    'jit_event_name': {'S': 'pull_request_created'},
                    'GSI4SK': {'S': '2022-04-18T08:01:04.554421'},
                    'asset_name': {'S': 'test'},
                    'GSI3SK': {'S': '2022-04-18T08:01:04.554421'},
                    'GSI2SK': {'S': '2022-04-18T08:01:04.554421'},
                    'vendor': {'S': 'github'},
                    'GSI1SK': {'S': '2022-04-18T08:01:04.554421'},
                    'job_runner': {'S': random.choice(CI_RUNNERS)},
                    'SK': {
                        'S': f'JIT_EVENT#{MOCK_JIT_EVENT_ID}#RUN#{MOCK_EXECUTION_ID}'
                    },
                    'asset_type': {'S': 'repo'},
                    'GSI4PK': {
                        'S': 'TENANT#610a53ca-a24c-4697-b2e8-428b182f2735#PLAN_ITEM#item-mfa-scm#STATUS#pending'},
                    'GSI3PK': {'S': f'TENANT#{MOCK_TENANT_ID}#PLAN_ITEM#item-mfa-scm'},
                    'GSI2PK': {'S': f'TENANT#{MOCK_TENANT_ID}#STATUS#pending'},
                    'control_name': {'S': 'control-mfa-github'},
                    'steps': {'L': [{'M': {'name': {'S': 'Run Least Privileged IAM Checker'}, 'uses': {
                        'S': 'ghcr.io/jitsecurity-controls/control-iam-least-privileged-alpine:latest'},
                                           'params': {'M': {}}}}]},
                    'entity_type': {'S': 'job'},
                    'GSI1PK': {'S': f'TENANT#{MOCK_TENANT_ID}'},
                    'job_name': {'S': 'mfa-github-checker'},
                    'resource_type': {'S': 'jit_high_priority'},
                    'PK': {'S': f'TENANT#{MOCK_TENANT_ID}'},
                    'workflow_slug': {'S': 'workflow'},
                    'control_image': {'S': 'registry.jit.io/some-image'},
                    'control_type': {'S': 'detection'},
                }
            }
        }
    ]
}

MOCK_EXECUTION_DATA = ExecutionData(
    tenant_id="tenant_id",
    jit_event_id="jit_event_id",
    execution_id="execution_id",
    execution_data_json=json.dumps({"key": "value"}),
    created_at="created_at",
)


def generate_dynamodb_stream_insert_event_from_execution(
        manager: Union[ExecutionsManager, ResourcesManager],
        execution: Execution
):
    return (
        {
            'Records': [
                {
                    'eventName': 'INSERT',
                    'dynamodb': {
                        'NewImage': manager.convert_python_dict_to_dynamodb_object(execution.dict(exclude_none=True))
                    }
                }
            ]
        }
    )

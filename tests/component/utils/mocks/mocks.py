import json
import uuid
from pathlib import Path

from jit_utils.event_models import JitEventName
from jit_utils.event_models.common import TriggerFilterAttributes
from jit_utils.models.asset.entities import AssetStatus
from jit_utils.models.plan.template import WorkflowTemplate

from src.lib.clients.plan_service_models import JitCentralizedRepoFilesMetadataResponse
from src.lib.constants import AWS, DEPENDS_ON, DOT_JIT, GITHUB, ITEMS
from src.lib.models.trigger import (
    JobTemplateWrapper,
    PrepareForExecutionEvent,
    PrepareForExecutionEventWithEnrichedData,
)
from tests.common import AssetFactory, InstallationFactory, ManualExecutionJitEventFactory

PATH_TO_PR_CREATED_EVENT__PREPARE_FOR_EXECUTION__ENRICHED_WITH_PULUMI = \
    Path(__file__).parent / "pr_flow_mocks/pr_created_event__enriched_with_pulumi.json"
PATH_TO_PR_CREATED_EVENT__PREPARE_FOR_EXECUTION__ENRICHED_WITHOUT_PULUMI = \
    Path(__file__).parent / "pr_flow_mocks/pr_created_event__enriched_without_pulumi.json"
PATH_TO_SCHEME_EVENT__PREPARE_FOR_EXECUTION__ENRICHED_WITHOUT_PULUMI = \
    Path(__file__).parent / "pr_flow_mocks/scheme_event__enriched_without_pulumi.json"
PATH_TO_SCHEME_EVENT__PREPARE_FOR_EXECUTION__ENRICHED_WITH_PULUMI = \
    Path(__file__).parent / "pr_flow_mocks/scheme_event__enriched_with_pulumi.json"
PATH_TO_TRIGGER_EXECUTIONS_EVENT__PREPARE_FOR_EXECUTION__ENRICHED_WITHOUT_PULUMI = \
    Path(__file__).parent / "pr_flow_mocks/trigger_execution_event__enriched_without_pulumi.json"
PATH_TO_TRIGGER_EXECUTIONS_EVENT__PREPARE_FOR_EXECUTION__ENRICHED_WITH_PULUMI = \
    Path(__file__).parent / "pr_flow_mocks/trigger_execution_event__enriched_with_pulumi.json"
PATH_TO_PLAN_ITEM_ADDED_EVENT__PREPARE_FOR_EXECUTION = \
    Path(__file__).parent / "plan_item_added_mocks/plan_item_added_event.json"
PATH_TO_PLAN_ITEM_ADDED_EVENT__SCHEME_EVENT = \
    Path(__file__).parent / "plan_item_added_mocks/plan_item_added_scheme_event.json"
PATH_TO_PLAN_ITEM_ADDED_EVENT__TRIGGER_EXECUTIONS_EVENT = \
    Path(__file__).parent / "plan_item_added_mocks/plan_item_added_trigger_executions_event.json"
PREPARE_FOR_EXECUTION_EVENT__DUPLICATION_EXECUTIONS_PATH = \
    Path(__file__).parent / "plan_item_added_mocks/duplication_executions__event_input.json"

PATH_TO_PREPARE_FOR_EXECUTION_PR_CREATED__WITH_DEPENDS_ON = \
    Path(__file__).parent / "depends_on_mocks/prepare_for_execution_pr_created_event.json"

PATH_TO_PREPARE_FOR_EXECUTION_PR_UPDATED_MULTIPLE_JOBS__WITH_DEPENDS_ON = \
    Path(__file__).parent / "depends_on_mocks/prepare_for_execution_pr_updated_multiple_jobs_event.json"

PATH_TO_PREPARE_FOR_EXECUTION_RESOURCE_ADDED__WITH_DEPENDS_ON = \
    Path(__file__).parent / "depends_on_mocks/prepare_for_execution_resource_added_event.json"

PATH_TO_PREPARE_FOR_EXECUTION_EVENT__WITHOUT_DEPENDS_ON = \
    Path(__file__).parent / "not_depends_on_mocks/prepare_for_execution_event_without_depends_on.json"


def get_json(file_path):
    with open(file_path) as f:
        content = json.load(f)
    return content


"""Mocks for flow of prepare_for_execution, PR Created event enriched with Pulumi """
PREPARE_FOR_EXECUTION_EVENT__PR_CREATED__ENRICHED_WITH_PULUMI = PrepareForExecutionEventWithEnrichedData(**get_json(
    PATH_TO_PR_CREATED_EVENT__PREPARE_FOR_EXECUTION__ENRICHED_WITH_PULUMI))
SCHEME_EVENT__PR_CREATED__ENRICHED_WITH_PULUMI = get_json(
    PATH_TO_SCHEME_EVENT__PREPARE_FOR_EXECUTION__ENRICHED_WITH_PULUMI)
TRIGGER_EXECUTION_EVENT__PR_CREATED__ENRICHED_WITH_PULUMI = get_json(
    PATH_TO_TRIGGER_EXECUTIONS_EVENT__PREPARE_FOR_EXECUTION__ENRICHED_WITH_PULUMI)

"""
Mocks for flow of prepare_for_execution, PR Created event enriched without Pulumi"""
PREPARE_FOR_EXECUTION_EVENT__PR_CREATED__ENRICHED_WITHOUT_PULUMI = PrepareForExecutionEventWithEnrichedData(**get_json(
    PATH_TO_PR_CREATED_EVENT__PREPARE_FOR_EXECUTION__ENRICHED_WITHOUT_PULUMI))
SCHEME_EVENT__PR_CREATED__ENRICHED_WITHOUT_PULUMI = get_json(
    PATH_TO_SCHEME_EVENT__PREPARE_FOR_EXECUTION__ENRICHED_WITHOUT_PULUMI)
TRIGGER_EXECUTION_EVENT__PR_CREATED__ENRICHED_WITHOUT_PULUMI = get_json(
    PATH_TO_TRIGGER_EXECUTIONS_EVENT__PREPARE_FOR_EXECUTION__ENRICHED_WITHOUT_PULUMI)

PREPARE_EXECUTION_EVENT_INPUT__ITEM_ACTIVATED = PrepareForExecutionEventWithEnrichedData(**get_json(
    Path(__file__).parent / "prepare_execution_flow/item_activated__event_input.json"))
PREPARE_EXECUTION_EVENT_OUTPUT__ITEM_ACTIVATED = get_json(
    Path(__file__).parent / "prepare_execution_flow/item_activated__prepare_for_execution_output.json")
PREPARE_EXECUTION_SCHEME_MESSAGE__ITEM_ACTIVATED = get_json(
    Path(__file__).parent / "prepare_execution_flow/item_activated__scheme_message.json")

PREPARE_EXECUTION_EVENT_INPUT__NEW_RUNNER_FORMAT_ITEM_ACTIVATED = PrepareForExecutionEventWithEnrichedData(**get_json(
    Path(__file__).parent / "prepare_execution_flow/item_activated__new_runner_format_input_event.json"))
PREPARE_EXECUTION_EVENT_OUTPUT__NEW_RUNNER_FORMAT_ITEM_ACTIVATED = get_json(
    Path(
        __file__).parent / "prepare_execution_flow/item_activated__new_runner_format_prepare_for_execution_output.json")
PREPARE_EXECUTION_SCHEME_MESSAGE__NEW_RUNNER_FORMAT_ITEM_ACTIVATED = get_json(
    Path(__file__).parent / "prepare_execution_flow/item_activated__new_runner_format_scheme_message.json")

""" Mocks for flow of prepare_for_execution, plan item added"""
PREPARE_FOR_EXECUTION_EVENT__PLAN_ITEM_ADDED = PrepareForExecutionEventWithEnrichedData(**get_json(
    PATH_TO_PLAN_ITEM_ADDED_EVENT__PREPARE_FOR_EXECUTION))
SCHEME_EVENT__PLAN_ITEM_ADDED = get_json(
    PATH_TO_PLAN_ITEM_ADDED_EVENT__SCHEME_EVENT)
TRIGGER_EXECUTION_EVENT__PLAN_ITEM_ADDED = get_json(
    PATH_TO_PLAN_ITEM_ADDED_EVENT__TRIGGER_EXECUTIONS_EVENT)
PREPARE_FOR_EXECUTION_EVENT__DUPLICATION_EXECUTIONS = PrepareForExecutionEventWithEnrichedData(**get_json(
    PREPARE_FOR_EXECUTION_EVENT__DUPLICATION_EXECUTIONS_PATH))


""" Mocks for enrich """
PREPARE_FOR_EXECUTION_PR_CREATED__WITH_DEPENDS_ON = get_json(PATH_TO_PREPARE_FOR_EXECUTION_PR_CREATED__WITH_DEPENDS_ON)
PREPARE_FOR_EXECUTION_PR_UPDATED_MULTIPLE_JOBS__WITH_DEPENDS_ON = get_json(
    PATH_TO_PREPARE_FOR_EXECUTION_PR_UPDATED_MULTIPLE_JOBS__WITH_DEPENDS_ON
)
PREPARE_FOR_EXECUTION_RESOURCE_ADDED__WITH_DEPENDS_ON = get_json(
    PATH_TO_PREPARE_FOR_EXECUTION_RESOURCE_ADDED__WITH_DEPENDS_ON
)
PATH_TO_PREPARE_FOR_EXECUTION_EVENT__WITHOUT_DEPENDS_ON = get_json(
    PATH_TO_PREPARE_FOR_EXECUTION_EVENT__WITHOUT_DEPENDS_ON
)

MOCK_JIT_CENTRALIZED_REPO_FILES_METADATA = JitCentralizedRepoFilesMetadataResponse(
    centralized_repo_files_location='centralized_repo_files_location',
    ci_workflow_files_path=['ci_workflow_files_path'],
)
TEST_TENANT_ID = str(uuid.uuid4())
TEST_JIT_EVENT_ID = str(uuid.uuid4())
OWNER = "wow"
ASSET_GITHUB_ORG = AssetFactory.build(
    tenant_id=TEST_TENANT_ID,
    owner=OWNER,
    asset_id="asset-0",
    asset_name="org",
    vendor=GITHUB,
    is_active=True,
    asset_type="org",
    is_covered=True,
)
ASSET_GITHUB_REPO_1 = AssetFactory.build(
    tenant_id=TEST_TENANT_ID,
    owner=OWNER,
    asset_id="asset-1",
    asset_name=DOT_JIT,
    vendor=GITHUB,
    is_active=True,
    asset_type="repo",
    is_covered=True,
)
ASSET_GITHUB_REPO_2 = AssetFactory.build(
    tenant_id=TEST_TENANT_ID,
    owner=OWNER,
    asset_id="asset-2",
    asset_name=DOT_JIT,
    vendor=GITHUB,
    is_active=True,
    asset_type="repo",
    is_covered=True,
)
ASSET_AWS_WITH_DEPLOYMENT_CONF = AssetFactory.build(
    tenant_id=TEST_TENANT_ID,
    owner=OWNER,
    asset_id="aws-account-asset-id",
    asset_name="my-aws-account",
    vendor=AWS,
    is_active=True,
    asset_type="aws_account",
    is_covered=True,
    aws_account_id="123456789012",
    environment="staging",
    status=AssetStatus.CONNECTED,
)
ASSET_DEPLOYMENT = AssetFactory.build(
    tenant_id=TEST_TENANT_ID,
    owner=OWNER,
    asset_id="aws-deployment-asset-id",
    asset_name="my-deployment",
    vendor="domain",
    is_active=True,
    asset_type="web",
    is_covered=True,
    environment="staging",
)
ASSETS = [
    ASSET_GITHUB_ORG,
    ASSET_GITHUB_REPO_1,
    ASSET_GITHUB_REPO_2,
    ASSET_AWS_WITH_DEPLOYMENT_CONF,
    ASSET_DEPLOYMENT,
]
ASSET_IDS = [asset.asset_id for asset in ASSETS]

AWS_ACCOUNT_ASSET_INDEX = 2

GITHUB_INSTALLATION = InstallationFactory.build(
    tenant_id=TEST_TENANT_ID,
    installation_id="installation-1",
    vendor=GITHUB,
    is_active=True,
    centralized_repo_asset=ASSETS[0],
    asset_name=DOT_JIT,
    owner=OWNER,
)

AWS_INSTALLATION = InstallationFactory.build(
    tenant_id=TEST_TENANT_ID,
    installation_id="aws-installation",
    vendor=AWS,
    is_active=True,
    centralized_repo_asset=ASSETS[0],
    asset_name="my-aws-account",
    owner=OWNER,
)

ALL_TENANT_INSTALLATIONS = {
    (GITHUB_INSTALLATION.vendor, GITHUB_INSTALLATION.owner): GITHUB_INSTALLATION,
    (AWS_INSTALLATION.vendor, AWS_INSTALLATION.owner): AWS_INSTALLATION
}
CONTENT_MOCK = (
    "jobs:\n  static-code-analysis-csharp:\n    asset_type: repo\n    default: true\n    if:\n      "
    "languages:\n      - csharp\n    runner:\n      setup:\n        checkout: true\n      "
    "type: github_actions\n    steps:\n    - name: Run semgrep csharp\n      tags:\n        "
    "links:\n          github: https://github.com/jitsecurity-controls/jit-semgrep-code-scanning-control\n"
    "          security_tool: https://github.com/returntocorp/semgrep\n        security_tool: Semgrep\n"
    "      uses: ghcr.io/jitsecurity-controls/control-semgrep-alpine:latest\n      with:\n        "
    "args: --json --config=/semgrep-csharp-config.yml --metrics=off --severity=ERROR\n          "
    "\\${WORK_DIR:-.}\n    tags:\n      languages:\n      - csharp\n  static-code-analysis-go:\n    "
    "asset_type: repo\n    default: true\n    if:\n      languages:\n      - go\n    runner:\n      "
    "setup:\n        checkout: true\n      type: github_actions\n    steps:\n    - name: Run Go\n      "
    "tags:\n        links:\n          "
)
FILTERED_JOBS_MOCK = [
    JobTemplateWrapper(
        plan_item_slug="item-code-vulnerability",
        workflow_slug="workflow-sast",
        workflow_name="SAST Workflow",
        job_name="static-code-analysis-java",
        workflow_template={
            "slug": "workflow-sast",
            "name": "SAST Workflow",
            "type": "workflow",
            "default": True,
            "content": CONTENT_MOCK,
            "depends_on": ["workflow-enrichment-code"],
            "params": None,
            "plan_item_template_slug": None,
            "asset_types": ["repo", "repo", "repo", "repo", "repo", "repo", "repo", "repo", "repo", "repo"],
        },
        raw_job_template={
            "asset_type": "repo",
            "if": {"languages": ["java"]},
            "runner": {"setup": {"checkout": True}, "type": "github_actions"},
            "steps": [
                {
                    "name": "Run semgrep java",
                    "tags": {
                        "links": {
                            "github": "https://github.com/jitsecurity-controls/jit-semgrep-code-scanning-control",
                            "security_tool": "https://github.com/returntocorp/semgrep",
                        },
                        "security_tool": "Semgrep",
                    },
                    "uses": "ghcr.io/jitsecurity-controls/control-semgrep-alpine:latest",
                    "with": {
                        "args": "--json --config=/semgrep-java-config.yml --metrics=off --severity=ERROR "
                                "\\${WORK_DIR:-.}"
                    },
                }
            ],
            "tags": {"languages": ["java"]},
        },
        depends_on_slugs=["workflow-enrichment-code"],
    ),
    JobTemplateWrapper(
        plan_item_slug="item-code-vulnerability",
        workflow_slug="workflow-sast",
        workflow_name="SAST Workflow",
        job_name="static-code-analysis-scala",
        workflow_template={
            "slug": "workflow-sast",
            "name": "SAST Workflow",
            "type": "workflow",
            "default": True,
            "content": CONTENT_MOCK,
            "depends_on": ["workflow-enrichment-code"],
            "params": None,
            "plan_item_template_slug": None,
            "asset_types": ["repo", "repo", "repo", "repo", "repo", "repo", "repo", "repo", "repo", "repo"],
        },
        raw_job_template={
            "asset_type": "repo",
            "if": {"languages": ["scala"]},
            "runner": {"setup": {"checkout": True}, "type": "github_actions"},
            "steps": [
                {
                    "name": "Run semgrep scala",
                    "tags": {
                        "links": {
                            "github": "https://github.com/jitsecurity-controls/jit-semgrep-code-scanning-control",
                            "security_tool": "https://github.com/returntocorp/semgrep",
                        },
                        "security_tool": "Semgrep",
                    },
                    "uses": "ghcr.io/jitsecurity-controls/control-semgrep-alpine:latest",
                    "with": {
                        "args": "--json --config=/semgrep-scala-config.yml "
                                "--metrics=off --severity=ERROR \\${WORK_DIR:-.}"
                    },
                }
            ],
            "tags": {"languages": ["scala"]},
        },
        depends_on_slugs=["workflow-enrichment-code"],
    ),
    JobTemplateWrapper(
        plan_item_slug="item-code-vulnerability",
        workflow_slug="workflow-sast",
        workflow_name="SAST Workflow",
        job_name="static-code-analysis-js",
        workflow_template={
            "slug": "workflow-sast",
            "name": "SAST Workflow",
            "type": "workflow",
            "default": True,
            "content": CONTENT_MOCK,
            "depends_on": ["workflow-enrichment-code"],
            "params": None,
            "plan_item_template_slug": None,
            "asset_types": ["repo", "repo", "repo", "repo", "repo", "repo", "repo", "repo", "repo", "repo"],
        },
        raw_job_template={
            "asset_type": "repo",
            "default": True,
            "if": {"languages": ["javascript", "typescript"]},
            "runner": {"setup": {"checkout": True}, "type": "github_actions"},
            "steps": [
                {
                    "name": "Run semgrep javascript and typescript",
                    "tags": {
                        "links": {
                            "github": "https://github.com/jitsecurity-controls/jit-semgrep-code-scanning-control",
                            "security_tool": "https://github.com/returntocorp/semgrep",
                        },
                        "security_tool": "Semgrep",
                    },
                    "uses": "ghcr.io/jitsecurity-controls/control-semgrep-alpine:latest",
                    "with": {
                        "args": "--json --config=/semgrep-ts-config.yml --metrics=off --severity=ERROR \\${WORK_DIR:-.}"
                    },
                }
            ],
            "tags": {"languages": ["javascript", "typescript", "JS", "TS"]},
        },
        depends_on_slugs=["workflow-enrichment-code"],
    ),
    JobTemplateWrapper(
        plan_item_slug="item-secret-detection",
        workflow_slug="workflow-secret-detection",
        workflow_name="Secret Detection Workflow",
        job_name="secret-detection",
        workflow_template={
            "slug": "workflow-secret-detection",
            "name": "Secret Detection Workflow",
            "type": "workflow",
            "default": True,
            "content": CONTENT_MOCK,
            "depends_on": ["workflow-enrichment-code"],
            "params": None,
            "plan_item_template_slug": None,
            "asset_types": ["repo"],
        },
        raw_job_template={
            "asset_type": "repo",
            "default": True,
            "if": {"mime_types": ["text"]},
            "runner": {"setup": {"checkout": True}, "type": "github_actions"},
            "steps": [
                {
                    "name": "Run Gitleaks",
                    "tags": {
                        "links": {
                            "github": "https://github.com/jitsecurity-controls/jit-secrets-detection-control",
                            "security_tool": "https://github.com/zricethezav/gitleaks",
                        },
                        "security_tool": "Gitleaks",
                    },
                    "uses": "ghcr.io/jitsecurity-controls/control-gitleaks-alpine:latest",
                    "with": {
                        "args": "detect --config \\$GITLEAKS_CONFIG_FILE_PATH --source \\${WORK_DIR:-.} -v "
                                "--report-format json --report-path \\$REPORT_FILE --redact --no-git --exit-code 0",
                        "output_file": "/tmp/report.json",
                    },
                }
            ],
        },
        depends_on_slugs=["workflow-enrichment-code"],
    ),
]

FILTERED_JOBS_MOCK_CLOUD = [
    JobTemplateWrapper(
        plan_item_slug="item-runtime-misconfiguration-detection-aws",
        workflow_slug="workflow-runtime-misconfiguration-detection-aws",
        workflow_name="AWS Workflow",
        job_name="runtime-misconfig-detection-aws",
        workflow_template={
            "slug": "workflow-runtime-misconfiguration-detection-aws",
            "name": "AWS Workflow",
            "type": "workflow",
            "default": True,
            "content": CONTENT_MOCK,
            "params": None,
            "plan_item_template_slug": None,
            "asset_types": ["aws_account"],
        },
        raw_job_template={
            "asset_type": "aws_account",
            "runner": {"setup": {"auth_type": "aws_iam_role"}, "type": "jit"},
            "steps": [
                {
                    "name": "Run Prowler For AWS",
                    "tags": {
                        "links": {
                            "github": "https://github.com/jitsecurity-controls/jit-prowler-control",
                            "security_tool": "https://github.com/prowler-cloud/prowler",
                        },
                        "security_tool": "Prowler",
                    },
                    "uses": "899025839375.dkr.ecr.us-east-1.amazonaws.com/prowler:latest",
                    "with": {
                        "env": {
                            "AWS_ACCESS_KEY_ID": "${{ context.auth.config.aws_access_key_id }}",
                            "AWS_SECRET_ACCESS_KEY": "${{ context.auth.config.aws_secret_access_key }}",
                            "AWS_SESSION_TOKEN": "${{ context.auth.config.aws_session_token }}",
                            "JIT_CONFIG_CONTENT": "${{ context.config }}"
                        }
                    },
                }
            ],
        },
    )
]

FULL_PLAN_CODE = {
    ITEMS: ["item-code-vulnerability"],
    DEPENDS_ON: {
        "workflow-enrichment-code": {
            "slug": "workflow-enrichment-code",
            "name": "Code Enrichment Workflow",
            "type": "workflow",
            "default": None,
            "content": "",
            "depends_on": [],
            "params": None,
            "plan_item_template_slug": None,
            "asset_types": ["repo"],
            "parsed_content": {},
        }
    }
}

FULL_PLAN_CLOUD = {
    ITEMS: ["item-runtime-misconfiguration-detection-aws"],
    DEPENDS_ON: {}
}

MANUAL_EXECUTION_EVENT_CODE = ManualExecutionJitEventFactory.build(
    tenant_id=TEST_TENANT_ID,
    jit_event_id=TEST_JIT_EVENT_ID,
    plan_item_slug="item-code-vulnerability",
    asset_ids_filter=ASSET_IDS,
    workflows=None,
    jit_event_name=JitEventName.ManualExecution,
)

MANUAL_EXECUTION_EVENT_TRIGGER_CLOUD_CONTROL = ManualExecutionJitEventFactory.build(
    tenant_id=TEST_TENANT_ID,
    jit_event_id=TEST_JIT_EVENT_ID,
    asset_id=None,
    plan_item_slug="item-runtime-misconfiguration-detection",
    asset_ids_filter=ASSET_IDS,
    workflows=None,
    jit_event_name=JitEventName.ManualExecution,
)

PREPARE_FOR_EXECUTION_MANUAL_EXECUTION_EVENT_CODE_CONTROL = PrepareForExecutionEvent(
    jit_event=MANUAL_EXECUTION_EVENT_CODE,
    trigger_filter_attributes=TriggerFilterAttributes(
        plan_item_slugs={"item-code-vulnerability"}, asset_ids=set(ASSET_IDS), triggers={JitEventName.ManualExecution}
    ),
    asset=ASSETS[0],
    installations=list(ALL_TENANT_INSTALLATIONS.values()),
    filtered_jobs=FILTERED_JOBS_MOCK,
    should_enrich=True,
    depends_on_workflows_templates=[
        WorkflowTemplate(
            **{
                "slug": "workflow-enrichment-code",
                "name": "Code Enrichment Workflow",
                "type": "workflow",
                "default": None,
                "content": "",
                "depends_on": [],
                "params": None,
                "plan_item_template_slug": None,
                "asset_types": ["repo"],
                "parsed_content": {},
            }
        )
    ],
)

PREPARE_FOR_EXECUTION_MANUAL_EXECUTION_EVENT_CLOUD_CONTROL = PrepareForExecutionEvent(
    jit_event=MANUAL_EXECUTION_EVENT_TRIGGER_CLOUD_CONTROL,
    trigger_filter_attributes=TriggerFilterAttributes(
        plan_item_slugs={"item-runtime-misconfiguration-detection-aws"},
        asset_ids=set(ASSET_IDS),
        triggers={JitEventName.ManualExecution}
    ),
    asset=ASSETS[2],  # AWS asset index
    installations=list(ALL_TENANT_INSTALLATIONS.values()),
    filtered_jobs=FILTERED_JOBS_MOCK_CLOUD,
    should_enrich=False,
    depends_on_workflows_templates=[],
)

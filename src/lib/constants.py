from jit_utils.jit_event_names import PR_RELATED_JIT_EVENTS, JitEventName


# Put your constants here
DEPLOYMENT_STAGE = "DEPLOYMENT_STAGE"

LOCAL = "local"
TEST = "test"
REGION_NAME = "AWS_REGION_NAME"

TENANT_HEADER = 'Tenant'

GITLAB = 'gitlab'
GITHUB = 'github'
AWS = 'aws'
DOT_JIT = ".jit"

# INDEX NAMES
PK = 'PK'
SK = 'SK'

# TABLE NAMES
JIT_EVENT_LIFE_CYCLE_TABLE_NAME = 'JitEventLifeCycle'
ENRICHMENT_RESULTS_TABLE_NAME = 'EnrichmentResults'

WEBHOOK_HEADERS = "webhook_headers"
WEBHOOK_BODY = "webhook_body"
WEBHOOK_BODY_JSON = "webhook_body_json"
SLUG = "slug"
JIT_PLAN_SLUG = "jit-plan"
PLAN_SLUG = "plan_slug"
PLAN_ITEM_SLUG = "plan_item_slug"
WORKFLOW_SLUG = "workflow_slug"
WORKFLOW_TEMPLATES = "workflow_templates"
JOB_NAME = "job_name"
JOBS = "jobs"
STEPS = "steps"
INTEGRATIONS = "integrations"
RUNNER = "runner"
JOB_RUNNER = "job_runner"
JIT_EVENT = "jit_event"
JIT_EVENT_NAME = "jit_event_name"
JIT_EVENT_ID = "jit_event_id"

TRIGGER = "trigger"
YAML_IF_CONDITION = "if"
TRIGGER_SERVICE = "trigger-service"
TRIGGER_EXECUTION_BUS_NAME = 'trigger-execution'
TRIGGER_EXECUTION_DETAIL_TYPE_HANDLE_EVENT = 'handle-jit-event'
TRIGGER_EXECUTION_DETAIL_TYPE_TRIGGER_EVENT = 'trigger-execution'
TRIGGER_EXECUTION_DETAIL_TYPE_TRIGGER_SCHEME = 'trigger-scheme'
TRIGGER_EXECUTION_DETAIL_TYPE_PUBLISHED_PREPARE_FOR_EXECUTION = 'published-prepare-for-execution'
PR_WATCHDOG_DETAIL_TYPE = 'pr-watchdog'

TAGS = "tags"
ASSET_TYPE = "asset_type"
SECURITY_TOOL = "security_tool"

CONTENT = "content"
PARSED_CONTENT = "parsed_content"
TRIGGER_EXECUTIONS_DETAIL_KEY = 'executions'
TRIGGER_MAX_BULK_SIZE = 50

HEAD_SHA = "head_sha"
BASE_SHA = "base_sha"
PULL_REQUEST_OPENED = "pull_request_opened"
PULL_REQUEST_SYNCHRONIZE = "pull_request_synchronize"
PULL_REQUEST_CLOSED = "pull_request_closed"
DEPLOYMENT_STATUS_UPDATED = "deployment_status_created"
RERUN_PIPELINE = "check_suite_rerequested"
CHECK_RERUN_PIPELINE = "check_run_rerequested"
REPO = "repo"
ITEMS = "items"
DEPENDS_ON = "depends_on"

ANY_LANGUAGE = "any"
LANGUAGES = "languages"
JS = "JS"
TS = "TS"
JS_DEPS = "js_deps"  # Used for Node_JS dep
GO_DEPS = "go_deps"
GO = "go"
PYTHON = "python"
DOCKER = "docker"
TERRAFORM = 'terraform'
SERVERLESS = 'serverless'
JAVA = 'java'
BASH = 'bash'
PHP_DEPS = "php_deps"

FILE_EXTENSIONS = "file_extensions"
FILE_NAMES = "file_names"
EXCLUDE_FILE_NAMES = "exclude_file_names"

AWS_ACCOUNT = 'aws_account'
WEB_ASSET = 'web'
API_ASSET = 'api'
ORGANIZATION = 'org'
AWS_CONFIGURATION = 'aws_configuration'

DEPLOYMENT = 'deployment'

URLS = 'urls'

ASSETS_TYPES_WITH_INSTALLATIONS = {REPO, AWS_ACCOUNT, ORGANIZATION}

# enrich workflow has no plan item, we can pass a placeholder that has no impact on the flow
PLACEHOLDER_PLAN_ITEM_SLUG = "DEPENDS_ON_PLAN_ITEM_SLUG"
SLACK_CHANNEL_NAME_ERRORS = "jit-errors-{env_name}"
SLACK_CHANNEL_NAME_PR_WATCHDOG = "jit-pr-watchdog-{env_name}"
SLACK_CHANNEL_WATCHDOG_ERRORS = "jit-resources-mgmt-{env_name}"
SEND_INTERNAL_NOTIFICATION_QUEUE_NAME = "SendInternalNotificationQueue"
STATE_MACHINE_EXECUTION_URL_PREFIX = "https://console.aws.amazon.com/states/home?#/v2/executions/details/"

ENV_NAME = "ENV_NAME"

FEATURE_FLAG_STOP_EXECUTIONS_ON_GH_OUTAGE = "stop-executions-on-github-outage"
FEATURE_FLAG_ASSETS_IN_SCALE = "assets-in-scale"
FEATURE_FLAG_ALLOW_CONTROLLED_PR_CHECKS = "allow-controlled-pr-checks"
FEATURE_FLAG_DISMISS_ITEM_ACTIVATED_EVENT = "dismiss-item-activated-event"

JIT_EVENT_TTL = 60 * 60 * 24 * 7  # 7 days

# EventBridge
TRIGGER_EVENT_SOURCE = "trigger-service"
# Jit Event Life Cycle
JIT_EVENT_LIFE_CYCLE_EVENT_BUS_NAME = "jit-event-life-cycle"
STARTED_JIT_EVENT_LIFE_CYCLE_EVENT_DETAIL_TYPE = "jit-event-life-cycle-started"
COMPLETED_JIT_EVENT_LIFE_CYCLE_EVENT_DETAIL_TYPE = "jit-event-life-cycle-completed"

# Jit Event Life Cycle DB indexes
GSI1PK_TENANT_ID = "GSI1PK_TENANT_ID"
GSI1SK_CREATED_AT = "GSI1SK_CREATED_AT"

GSI2PK_TTL_BUCKET = "GSI2PK_TTL_BUCKET"
GSI2SK_CREATED_AT = "GSI2SK_CREATED_AT"

# Step Function
PAYLOAD_WARNING_THRESHOLD = 150000  # 150KB in bytes
# sfn runs Enrichment in different modes, based on the Jit Event. For example partial (diff based) Enrichment for PRs.
JIT_EVENTS_WITH_DIFF_BASED_ENRICHMENT = PR_RELATED_JIT_EVENTS + [JitEventName.MergeDefaultBranch]

BUCKETS_AMOUNTS_FOR_TTL_INDEX = 10
PR_JIT_EVENTS_START_WATCHDOG_TTL_SECONDS = 15 * 60  # 15 minutes in seconds
PR_JIT_EVENTS_END_WATCHDOG_TTL_SECONDS = 1 * 60 * 60  # 1 hour in seconds

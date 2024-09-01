FARGATE_TASKS_BATCH_QUEUE_NAME = 'fargate-tasks-queue'

# Note that we will use the web app image for both web and api scans, since we unified the control
ZAP_IMAGE_URL = 'ghcr.io/jitsecurity-controls/control-zap-alpine:latest'

GITHUB_ORG_MFA_IMAGE_URL = 'ghcr.io/jitsecurity-controls/control-mfa-github-alpine:latest'

# GENERAL ENV VARS
ENTRYPOINT_EVENT_ENV_NAME = 'EVENT'

SILENT_INVOCATION_SUPPORTED_CONTROL_NAMES = [
    'prowler',
]

GCP_CREDENTIALS_SECRET_NAME = 'gcp_credentials'

AZURE_CREDENTIALS_SECRET_NAMES = ['azure_client_id', 'azure_client_secret', 'azure_subscription_ids']

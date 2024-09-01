from string import Template

TENANT_SERVICE_ENDPOINT = "{base}/vendor/{vendor}/installation/{installation_id}"
GET_TENANT_BY_OWNER_ENDPOINT = "{base}/vendor/{vendor}/owner/{owner}"
TENANT_SERVICE_GET_INSTALLATIONS = "{base}/vendor/{vendor}/installation"
GET_TENANT_INSTALLATIONS = "{base}/vendor/{vendor}/installation"
TENANT_SERVICE_GET_PREFERENCES = "{base}/preferences"

GET_ASSET_BY_ATTRIBUTES_ENDPOINT = "{base}/type/{asset_type}/vendor/{vendor}/owner/{owner}/name/{asset_name}"
GET_ALL_ASSETS_ENDPOINT = "{base}/"

WORKFLOW_CALLBACK_URL = "{base}"

EXECUTION_SERVICE_REGISTER_ENDPOINT = "{base}/register"
EXECUTION_SERVICE_COMPLETE_ENDPOINT = "{base}/complete"

FINDINGS_CALLBACK_URL = "{base}/asset/{asset_id}"
IGNORES_CALLBACK_URL = "{base}/asset/{asset_id}/control/{control_name}/ignore"
LOGS_CALLBACK_URL = "{base}/workflow-suite/{workflow_suite_id}/log"
GET_GITHUB_STATUS_URL = "{base}/github-status"

PLAN_SERVICE_GET_FULL_PLAN_CONTENT = Template('$base/$plan_slug/content-full')
PLAN_SERVICE_GET_CONFIG_FILE = Template('$base/configuration-file')
PLAN_SERVICE_GET_INTEGRATION_FILE = Template('$base/integration-file')
PLAN_SERVICE_GET_APPLICATIONS_CONFIGURATIONS = Template('$base/applications-configurations/trigger/$trigger/tag/$tag')
PLAN_SERVICE_GET_PLAN_ITEMS_CONFIGURATIONS = Template('$base/plan-items-configurations/trigger/$trigger/tag/$tag')
PLAN_SERVICE_GET_CENTRALIZED_REPO_FILES_METADATA = Template(
    '$base/centralized-repo-files-metadata/tenant-id/$tenant_id'
)

AUTH_SERVICE_GENERATE_LAMBDA_API_TOKEN = "{authentication_service}/token/internal"

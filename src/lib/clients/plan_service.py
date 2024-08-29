from http import HTTPStatus
from typing import Dict, Any, List

from jit_utils.logger import logger
from jit_utils.requests.requests_client import get_session, requests
from jit_utils.service_discovery import get_service_url

from src.lib.awsv4_sign_requests import sign
from src.lib.clients.plan_service_models import PlanItemConfiguration, JitCentralizedRepoFilesMetadataResponse
from src.lib.constants import TENANT_HEADER, JIT_PLAN_SLUG, ITEMS, DEPENDS_ON
from src.lib.endpoints import PLAN_SERVICE_GET_FULL_PLAN_CONTENT, PLAN_SERVICE_GET_CONFIG_FILE, \
    PLAN_SERVICE_GET_APPLICATIONS_CONFIGURATIONS, PLAN_SERVICE_GET_PLAN_ITEMS_CONFIGURATIONS, \
    PLAN_SERVICE_GET_CENTRALIZED_REPO_FILES_METADATA, PLAN_SERVICE_GET_INTEGRATION_FILE


class PlanService:
    def __init__(self) -> None:
        self.service = get_service_url('plan-service')['service_url']

    def get_full_plan(self, *, tenant_id: str, api_token: str) -> Dict:
        url = PLAN_SERVICE_GET_FULL_PLAN_CONTENT.substitute(base=self.service, plan_slug=JIT_PLAN_SLUG)
        response = get_session().get(
            url,
            headers={
                'Authorization': f'Bearer {api_token}',
                TENANT_HEADER: tenant_id
            }
        )

        try:
            if response.status_code != HTTPStatus.NOT_FOUND:
                # if the user doesn't have a plan we return a 404. it's still a valid scenario (probably on install)
                # and there's no need to raise an exception for that
                response.raise_for_status()
        except requests.HTTPError as e:
            raise Exception(f'Failed to get full plan contents for plan: jit-plan: {JIT_PLAN_SLUG}') from e
        response_dict = response.json()
        logger.info(f'Successfully retrieved plan contents. {response_dict}.')
        # Support the old response interface of the endpoint get-full-plan-content
        if ITEMS not in response_dict:
            return {
                ITEMS: response_dict,
                DEPENDS_ON: {}
            }
        return response_dict

    def get_configuration_file_for_tenant(self, tenant_id: str, api_token: str) -> Dict[str, Any]:
        logger.info(f'Getting configuration file for tenant {tenant_id}')
        url = PLAN_SERVICE_GET_CONFIG_FILE.substitute(base=self.service)
        response = get_session().get(
            url=url,
            headers={
                'Authorization': f'Bearer {api_token}',
                TENANT_HEADER: tenant_id
            }
        )
        if response.status_code == HTTPStatus.NOT_FOUND:
            logger.warning(f'Configuration file not found for tenant {tenant_id}')
            return {}

        response.raise_for_status()
        response_json = response.json()

        # in the new version of the plan service the content is wrapped in a dict with two keys: content and sha
        # the actual content of the file is in the content key...
        return response_json['content']

    def get_integration_file_for_tenant(self, tenant_id: str, api_token: str) -> Dict[str, Any]:
        logger.info(f'Getting Integration file for tenant {tenant_id}')
        url = PLAN_SERVICE_GET_INTEGRATION_FILE.substitute(base=self.service)
        response = get_session().get(
            url=url,
            headers={
                'Authorization': f'Bearer {api_token}',
                TENANT_HEADER: tenant_id
            }
        )
        if response.status_code == HTTPStatus.NOT_FOUND:
            logger.warning(f'Integration file not found for tenant {tenant_id}')
            return {}

        response.raise_for_status()
        response_json = response.json()

        # in the new version of the plan service the content is wrapped in a dict with two keys: content and sha
        # the actual content of the file is in the content key...
        content = response_json['content']
        if not content:
            return {}
        return content

    def get_plan_item_configurations_applications_according_to_env_trigger(
            self, env: str, trigger: str, api_token: str, tenant_id: str
    ) -> List[Dict]:
        logger.info(f'Getting application_configurations according to the {env=} and {trigger=}')
        url = PLAN_SERVICE_GET_APPLICATIONS_CONFIGURATIONS.substitute(base=self.service, trigger=trigger, tag=env)
        logger.info(f'Sending out request to: {url}')
        response = get_session().get(
            url=url,
            headers={
                'Authorization': f'Bearer {api_token}',
                TENANT_HEADER: tenant_id
            }
        )

        logger.info(f'response status code: {response.status_code}')
        return response.json()

    def get_plan_items_configurations_by_env_trigger(
            self, env: str, trigger: str, api_token: str, tenant_id: str
    ) -> List[PlanItemConfiguration]:
        logger.info(f'Getting plan items configurations according to the {env=} and {trigger=}')
        url = PLAN_SERVICE_GET_PLAN_ITEMS_CONFIGURATIONS.substitute(base=self.service, trigger=trigger, tag=env)
        logger.info(f'Sending out request to: {url}')

        response = get_session().get(
            url=url,
            headers={
                'Authorization': f'Bearer {api_token}',
                TENANT_HEADER: tenant_id
            }
        )

        logger.info(f'response status code: {response.status_code}')
        if response.ok:
            plan_items_configs = response.json()
            return [PlanItemConfiguration(**plan_items_config) for plan_items_config in plan_items_configs]
        else:
            logger.error(f'Failed to get plan items configurations according to the {env=} and {trigger=}')
            return []

    def get_centralized_repo_files_metadata(self, tenant_id: str) -> JitCentralizedRepoFilesMetadataResponse:
        logger.info(f'Getting centralized repo files metadata for {tenant_id=}')
        url = PLAN_SERVICE_GET_CENTRALIZED_REPO_FILES_METADATA.substitute(base=self.service, tenant_id=tenant_id)
        logger.info(f'Sending out request to: {url}')

        response = get_session().get(
            url,
            auth=sign(url)
        )

        logger.info(f'response status code: {response.status_code}')

        response.raise_for_status()

        jit_centralized_repo_metadata = response.json()
        logger.info(f'Got {jit_centralized_repo_metadata=}')
        return JitCentralizedRepoFilesMetadataResponse(**jit_centralized_repo_metadata)

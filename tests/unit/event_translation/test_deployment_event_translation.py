from uuid import uuid4
from jit_utils.event_models import JitEventName
from pytest_mock import MockFixture

import src
from src.lib.cores.event_translation.deployment_event_translation import (get_jit_event_name_from_deployment_event,
                                                                          get_tenant_preferences)
from jit_utils.models.tenant.entities import TenantPreferences, PreferencesScope
from jit_utils.jit_clients.tenant_service.exceptions import TenantServiceApiException


def test_get_jit_event_name_from_deployment_event():
    result = get_jit_event_name_from_deployment_event(random_string=uuid4().hex)
    assert result is JitEventName.NonProductionDeployment


def test_get_tenant_preferences_success_response(mocker: MockFixture):
    expected_result = TenantPreferences(deployment={'environments': ['foo', 'bar'], 'scope': PreferencesScope.TENANT})

    mocker.patch.object(
        src.lib.cores.event_translation.deployment_event_translation.TenantService,
        'get_preferences',
        return_value=expected_result
    )
    assert expected_result == get_tenant_preferences('API_TOKEN', 'TENANT_ID')


def test_get_tenant_preferences_failure_response(mocker: MockFixture):
    expected_result = None

    mocker.patch.object(
        src.lib.cores.event_translation.deployment_event_translation.TenantService,
        'get_preferences',
        side_effect=TenantServiceApiException()

    )
    assert expected_result == get_tenant_preferences('API_TOKEN', 'TENANT_ID')

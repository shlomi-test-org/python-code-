import src.lib.cores.prepare_data_for_execution_core
from src.lib.cores.prepare_data_for_execution_core import generate_callback_urls
from tests.mocks.execution_mocks import generate_mock_callback_urls
from tests.mocks.execution_mocks import MOCK_ACTIONS_SERVICE_URL
from tests.mocks.execution_mocks import MOCK_EXECUTION
from tests.mocks.execution_mocks import MOCK_EXECUTION_SERVICE_URL
from tests.mocks.execution_mocks import MOCK_FINDINGS_SERVICE_URL


def test_generate_callback_urls(mocker):
    # Setup
    url = "https://s3.aws.com"
    mocker.patch.object(src.lib.cores.prepare_data_for_execution_core, "generate_findings_upload_url", return_value=url)
    mocker.patch.object(src.lib.cores.prepare_data_for_execution_core, "generate_logs_upload_url", return_value=url)

    def mocked_get_service_url(service_name: str):
        if service_name == "action-service":
            return {'service_url': MOCK_ACTIONS_SERVICE_URL}
        elif service_name == 'finding-service':
            return {'service_url': MOCK_FINDINGS_SERVICE_URL}
        elif service_name == 'execution-service':
            return {'service_url': MOCK_EXECUTION_SERVICE_URL}

    mocker.patch.object(src.lib.cores.prepare_data_for_execution_core,
                        "get_service_url", mocked_get_service_url)

    # Test
    callback_urls = generate_callback_urls(tenant_id=MOCK_EXECUTION.tenant_id, asset_id=MOCK_EXECUTION.asset_id,
                                           jit_event_id=MOCK_EXECUTION.jit_event_id,
                                           execution_id=MOCK_EXECUTION.execution_id)

    # Assert
    expected_callback_urls = generate_mock_callback_urls(
        asset_id=MOCK_EXECUTION.asset_id,
        presigned_findings_upload_url=url,
    )

    assert callback_urls == expected_callback_urls

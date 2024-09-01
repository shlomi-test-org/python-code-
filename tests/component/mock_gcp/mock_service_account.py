from unittest.mock import MagicMock


def mock_gcp_service_account(mocker):
    mock_service_account = MagicMock()
    mock_service_account.from_service_account_info = MagicMock(return_value=MagicMock())
    mocker.patch('src.lib.gcp_common.service_account')

    return mock_service_account

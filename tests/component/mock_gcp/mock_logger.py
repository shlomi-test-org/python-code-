from typing import List

import google


def mock_gcp_logging_client(mocker):
    class MockLoggingClient:
        class logger:
            class LogEntry:
                def info(self, *args, **kwargs):
                    pass

            def __init__(self, service_name: str):
                pass

            def list_entries(self, filter_: str) -> List[LogEntry]:
                return []

    mock_logging_client = MockLoggingClient()
    mocker.patch.object(google.cloud.logging_v2, 'Client', return_value=mock_logging_client)

    return mock_logging_client

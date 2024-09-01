from src.lib.clients.analytics import send_analytics_event, AnalyticsEventType
from unittest.mock import MagicMock


def test_track(mocker):
    mock_tracker: MagicMock = mocker.patch('src.lib.clients.analytics.track')

    send_analytics_event(
        event_type=AnalyticsEventType.FINDING_WITH_FIX_SUGGESTION,
        distinct_id="12345",
        event_body={"key": "value"}
    )

    assert mock_tracker.call_count == 1

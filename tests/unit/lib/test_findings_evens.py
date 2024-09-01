import json

from jit_utils.aws_clients.events import EventBridgeClient

from src.lib.constants import EVENTS_SOURCE, FINDINGS_BUS_NAME, FINDINGS_FIXED_DETAIL_TYPE
from src.lib.findings_events import send_fixed_findings_events, TimeDecoder, \
    get_first_created_finding
from src.lib.models.finding_change_event import calculate_finding_lifecycle_duration
from src.lib.models.finding_model import Finding, FixedFindingEvent
from tests.fixtures import build_finding_dict


def test_send_fixed_findings_events_success(mocker, env_variables):
    # Assign
    findings_mock = [
        Finding(**build_finding_dict(should_modified_at_add_5_minutes=True)),
        Finding(**build_finding_dict(should_modified_at_add_5_minutes=True)),
        Finding(**build_finding_dict(should_modified_at_add_5_minutes=True))
    ]
    events_mock = []
    for finding in findings_mock:
        event = FixedFindingEvent(
            metadata=FixedFindingEvent.FixedFindingMetadata(
                asset_id=finding.asset_id,
                test_id=finding.test_id,
                event_id=finding.jit_event_id,
                finding_id=finding.id,
                tenant_id=finding.tenant_id,
            ),
            data=FixedFindingEvent.FixedFindingData(
                event_time=finding.modified_at,
                created_at=finding.created_at,
                is_backlog=finding.backlog,
                duration_minutes=5,
                has_fix_suggestion=finding.fix_suggestion is not None,
                priority_factors=finding.priority_factors,
                priority_score=finding.priority_score,
                asset_priority_score=finding.asset_priority_score,
            ),
        )
        events_mock.append(json.dumps(event.dict(), cls=TimeDecoder))

    put_events_mock = mocker.patch.object(EventBridgeClient, 'put_events')

    send_fixed_findings_events(findings_mock)
    assert put_events_mock.call_count == 2
    assert put_events_mock.call_args_list[0].kwargs == {
        'source': EVENTS_SOURCE,
        'bus_name': FINDINGS_BUS_NAME,
        'detail_type': FINDINGS_FIXED_DETAIL_TYPE,
        'details': events_mock,
    }
    assert {
               'source': EVENTS_SOURCE,
               'bus_name': FINDINGS_BUS_NAME,
               'detail_type': 'FindingUpdated',
           }.items() < put_events_mock.call_args_list[1].kwargs.items()


def test_calculate_finding_lifecycle_duration(env_variables):
    # Assign
    fingerprint = 'fingerprint'
    created_at = "2023-01-11T12:36:39.937696"
    finding_mock = Finding(**build_finding_dict(fingerprint=fingerprint,
                                                created_at=created_at,
                                                should_modified_at_add_5_minutes=True))
    # Act
    result = calculate_finding_lifecycle_duration(finding_mock)

    # Assert
    assert result == 5


def test_get_first_created_finding():
    # Assign
    fingerprint = 'fingerprint'
    findings_mock = [
        Finding(**build_finding_dict(fingerprint=fingerprint, created_at="2023-01-11T12:36:39.937696")),
        Finding(**build_finding_dict(fingerprint=fingerprint, created_at="2023-01-08T12:36:39.937696")),
        Finding(**build_finding_dict(fingerprint=fingerprint, created_at="2023-01-09T12:36:39.937696"))]

    # Act
    result = get_first_created_finding(findings_mock)

    # Assert
    assert result == findings_mock[1]

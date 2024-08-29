# Assertion functions
def assert_execution_findings_uploaded_event(event, jit_event_id, execution_id, created_at, new_count,
                                             existing_count, fail_on_findings):
    assert event['detail-type'] == 'execution-findings-uploaded'
    detail = event['detail']
    assert detail['jit_event_id'] == jit_event_id
    assert detail['execution_id'] == execution_id
    assert detail['new_findings_count'] == new_count
    assert detail['existing_findings_count'] == existing_count
    assert detail['created_at'] == created_at
    assert detail['status'] == 'completed'
    assert detail['fail_on_findings'] == fail_on_findings


def assert_findings_fixed_event(event, fixed_finding):
    assert event['detail-type'] == 'findings-fixed'
    assert event['detail']['metadata']['finding_id'] == fixed_finding['id']


def assert_finding_changed_event(event, finding, event_type, prev_resolution=None, new_resolution=None):
    """
    Asserts the details of FindingOpened or FindingUpdated event.

    :param event: The event to be asserted.
    :param finding: The finding dictionary containing the expected details.
    :param event_type: The type of the event ('FindingOpened' or 'FindingUpdated').
    :param prev_resolution: The previous resolution (used only for FindingUpdated).
    :param new_resolution: The new resolution (used for both FindingOpened and FindingUpdated).
    """
    assert event['detail-type'] == event_type
    assert event['detail']['finding_id'] == finding['id']

    if prev_resolution is not None:
        assert event['detail']['prev_resolution'] == prev_resolution

    if new_resolution is not None:
        assert event['detail']['new_resolution'] == new_resolution


def assert_findings_event(event, findings, event_type):
    """
    Asserts the details of findings-related events (either 'findings-created' or 'findings-updated').

    :param event: The event to be asserted.
    :param findings: A list of finding dictionaries containing the expected details.
    :param event_type: The type of the event ('findings-created' or 'findings-updated').
    """

    assert event['detail-type'] == event_type
    assert len(event['detail']['findings']) == len(findings)
    for finding in findings:
        assert any(f['id'] == finding['id'] for f in event['detail']['findings'])

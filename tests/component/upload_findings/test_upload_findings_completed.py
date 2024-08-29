import datetime
import os
import uuid

import pytest
import responses
from freezegun import freeze_time
from jit_utils.models.findings.entities import Resolution, Finding, UiResolution
from jit_utils.models.tenant.entities import TenantPreferences, NotificationsPreferences, \
    NotificationsPreference, PreferencesScope
from test_utils.aws.mock_eventbridge import mock_eventbridge

from src.handlers.findings.upload_findings import upload_findings_completed_handler
from src.lib.constants import SEND_HIGH_SEVERITY_OPEN_FINDINGS_NOTIFICATION_QUEUE, \
    SEND_FINDINGS_SAVED_VIEW_NOTIFICATION_QUEUE, PK, SK
from src.lib.data.db_table import DbTable
from src.lib.models.finding_model import SavedFilter, UploadFindingsStatusItem
from tests.component.upload_findings.events_utils import assert_execution_findings_uploaded_event, \
    assert_findings_fixed_event, assert_finding_changed_event, assert_findings_event
from tests.component.upload_findings.utils import get_expected_high_severity_findings_slack_notification, \
    get_expected_saved_view_findings_slack_notification
from tests.component.utils.assert_queue_content import assert_queue_content
from tests.component.utils.get_dynamo_event import get_dynamo_stream_event
from tests.component.utils.mock_clients.mock_authentication import mock_get_internal_token_api
from tests.component.utils.mock_mongo_driver import mock_mongo_driver
from tests.component.utils.mock_sqs_queue import mock_sqs_queue
from tests.component.utils.put_saved_filter_in_db import put_saved_filter_in_db
from tests.fixtures import build_finding_dict


@freeze_time("2022-01-14")
@responses.activate
def test_upload_findings_completed_verify_slack_notification(mocker, mocked_tables):
    """
    Setup:
        1) Insert one open finding to DB with issue_severity == HIGH and one ignored finding
        2) Insert saved filters to DB
        3) Mock requests
        4) Mock create 'SendHighSeverityFindingsNotificationQueue' SQS
        5) Mock create 'SendFindingsNotificationQueue' SQS
    Test:
        1) Call 'upload_findings_completed_handler' handler

    Assert:
        1) Slack notification sent to SQS queue of open high severity findings with single finding
        2) Slack notification sent to SQS queue of saved filters view for both findings
    """
    findings_table, status_table = mocked_tables
    os.environ['ENV_NAME'] = 'prod'  # This determines the platform url in the slack notification
    tenant_id = '19881e72-6d3b-49df-b79f-298ad89b8056'
    fingerprint = 'fingerprint'
    asset_id = '19881e72-1234-49df-b79f-298ad89b8056'
    finding_id = str(uuid.uuid4())
    execution_id = '5c481b2c-aaf1-4289-b2ac-3ddc79bc0196'
    jit_event_id = '5c481b2c-aaf1-4289-b2ac-3ddc79bc0196'
    control_name = 'control_name'
    created_at = str(datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f"))
    channel = 'some_channel'

    # Initialize status item in upload_findings_status_table
    status_item = UploadFindingsStatusItem(jit_event_id=jit_event_id, jit_event_name='An event',
                                           execution_id=execution_id, created_at=created_at,
                                           tenant_id=tenant_id, snapshots_count=2, error_count=0, failed_snapshots=[],
                                           is_backlog=True)
    item = {
        PK: DbTable.get_key(tenant=tenant_id),
        SK: DbTable.get_key(jit_event_id=jit_event_id, execution_id=execution_id),
        **status_item.dict(),
    }
    status_table.put_item(Item=item)

    # Mock mongo driver
    collection = mock_mongo_driver(mocker).findings

    tenants_preferences = TenantPreferences(notifications=NotificationsPreferences(
        ignore_findings=NotificationsPreference(channel=channel, enabled=True),
        deployment_with_vulnerabilities=NotificationsPreference(channel=channel, enabled=True),
        findings_on_saved_views=NotificationsPreference(channel=channel, enabled=True),
        new_action_created=NotificationsPreference(channel=channel, enabled=True),
        high_severity_findings=NotificationsPreference(channel=channel, enabled=True),
        scope=PreferencesScope.TENANT),
        status=200)
    event = get_dynamo_stream_event(tenant_id=tenant_id, execution_id=execution_id, jit_event_id=jit_event_id,
                                    created_at=created_at)
    # Setup: 1. insert one finding to DB
    finding = build_finding_dict(tenant_id=tenant_id, fingerprint=fingerprint, execution_id=execution_id,
                                 jit_event_id=jit_event_id, control_name=control_name,
                                 asset_id=asset_id, finding_id=finding_id, created_at=created_at, backlog=True,
                                 with_specs=True, issue_severity="CRITICAL", fix_suggestion=None)
    ignored_finding = build_finding_dict(tenant_id=tenant_id, fingerprint="ignored_fingerprint",
                                         execution_id=execution_id,
                                         jit_event_id=jit_event_id, control_name=control_name, ignored=True,
                                         asset_id=asset_id, finding_id="ignored_finding_id", created_at=created_at,
                                         backlog=True, fix_suggestion=None,
                                         with_specs=True)
    collection.insert_one(finding)
    collection.insert_one(ignored_finding)

    # Setup: 2. insert saved filters to DB
    saved_filter = put_saved_filter_in_db(tenant_id)

    # Setup: 3. Mock requests
    mock_get_internal_token_api()
    responses.add(responses.GET, 'https://api.dummy.jit.io/tenant/preferences',
                  json=tenants_preferences.dict())

    # Mock create 'findings' event bus
    with mock_eventbridge(bus_name='findings'):
        # Setup: 4. Mock create 'SendHighSeverityFindingsNotificationQueue' SQS
        mock_sqs_queue(queue_name=SEND_HIGH_SEVERITY_OPEN_FINDINGS_NOTIFICATION_QUEUE)
        # Setup: 5. Mock create 'SendFindingsNotificationQueue' SQS
        mock_sqs_queue(queue_name=SEND_FINDINGS_SAVED_VIEW_NOTIFICATION_QUEUE)
        # Test: Call 'upload_findings_completed_handler' handler
        upload_findings_completed_handler(event, None)  # type: ignore

    expected_high_severity_slack_sqs_message = get_expected_high_severity_findings_slack_notification(
        Finding(**finding),
        channel=channel)
    expected_saved_filters_slack_sqs_message = get_expected_saved_view_findings_slack_notification(
        [Finding(**ignored_finding), Finding(**finding)],
        channel=channel,
        view_name=SavedFilter(**saved_filter).name)

    # Assert: Slack notification were sent to SQS queue - High severity findings.
    assert_queue_content(
        queue_name=SEND_HIGH_SEVERITY_OPEN_FINDINGS_NOTIFICATION_QUEUE,
        expected_messages=[expected_high_severity_slack_sqs_message]
    )
    # Assert: Slack notification were sent to SQS queue - Saved filters view
    assert_queue_content(
        queue_name=SEND_FINDINGS_SAVED_VIEW_NOTIFICATION_QUEUE,
        expected_messages=[expected_saved_filters_slack_sqs_message]
    )

    # Assert completed status item has completed time
    status_item_from_db = status_table.scan()['Items'][0]
    assert status_item_from_db['completed_at'] == '2022-01-14T00:00:00'


@freeze_time("2022-01-14")
def test_upload_findings_completed__open_recurring__recurring_ignored__fixed_findings(mocker, mocked_tables):
    """
    Setup:
        1) Insert 6 recurring open findings, 6 recurring ignored findings and 1 fixed finding
    Act:
        1) Call 'upload_findings_completed_handler' handler
    Assert:
        1) Assert the types of the sent events and their specific contents:
            1.1 'execution-findings-uploaded' event - 0 new findings, 6 existing findings
            1.2 'findings-fixed' event - 1 fixed finding
            1.3 'FindingUpdated' event - open->fixed finding
            1.4 'findings-updated'/ 'upload-findings' event - 13 findings
    """
    tenant_id = str(uuid.uuid4())
    asset_id = str(uuid.uuid4())
    control_name = "control_name"
    created_at = "2021-01-01T00:00:00Z"
    jit_event_id = str(uuid.uuid4())
    execution_id = str(uuid.uuid4())
    _, status_table = mocked_tables

    # Initialize status item in upload_findings_status_table
    status_item = UploadFindingsStatusItem(jit_event_id=jit_event_id, jit_event_name='An event',
                                           execution_id=execution_id, created_at=created_at,
                                           tenant_id=tenant_id, snapshots_count=2, error_count=0, failed_snapshots=[],
                                           is_backlog=True)
    item = {
        PK: DbTable.get_key(tenant=tenant_id),
        SK: DbTable.get_key(jit_event_id=jit_event_id, execution_id=execution_id),
        **status_item.dict(),
    }
    status_table.put_item(Item=item)

    # Mock mongo driver
    collection = mock_mongo_driver(mocker).findings
    # Insert 6 open findings
    [collection.insert_one(
        build_finding_dict(finding_id=str(uuid.uuid4()), tenant_id=tenant_id, asset_id=asset_id,
                           control_name=control_name,
                           jit_event_id=jit_event_id, execution_id=execution_id,
                           with_specs=True, issue_severity='HIGH', fix_suggestion=None,
                           created_at="2023-03-26T06:09:03.063186", plan_items=['dummy-plan-item'])
    ) for i in range(0, 6)]
    # Insert 6 ignored findings
    [collection.insert_one(
        build_finding_dict(finding_id=str(uuid.uuid4()), tenant_id=tenant_id, asset_id=asset_id,
                           control_name=control_name,
                           jit_event_id=jit_event_id, execution_id=execution_id,
                           with_specs=True, issue_severity='HIGH', fix_suggestion=None,
                           created_at="2023-03-26T06:09:03.063186", plan_items=['plan-item-with-ignored'], ignored=True)
    ) for i in range(0, 6)]
    # insert a fixed finding
    fixed_finding_jit_event_id = str(uuid.uuid4())
    fixed_finding_execution_id = str(uuid.uuid4())
    fixed_finding = build_finding_dict(finding_id=str(uuid.uuid4()), tenant_id=tenant_id, asset_id=asset_id,
                                       control_name=control_name,
                                       jit_event_id=fixed_finding_jit_event_id, execution_id=fixed_finding_execution_id,
                                       with_specs=True, issue_severity='HIGH',
                                       plan_items=['fixed-plan-item-1', 'fixed-plan-item-2', 'dummy-plan-item'],
                                       fixed_at_execution_id=execution_id,
                                       resolution=UiResolution.FIXED, fix_suggestion=None,
                                       created_at="2023-03-26T06:09:03.063186")
    collection.insert_one(fixed_finding)

    event = get_dynamo_stream_event(tenant_id=tenant_id, execution_id=execution_id, jit_event_id=jit_event_id,
                                    created_at=created_at)
    with mock_eventbridge(bus_name='findings') as get_sent_events:
        upload_findings_completed_handler(event, None)  # type: ignore

    sent_events = get_sent_events()

    assert len(sent_events) == 4
    sent_events[0]['detail']['plan_items_with_findings'] = sorted(sent_events[0]['detail']['plan_items_with_findings'])
    assert sent_events[0]['detail-type'] == 'execution-findings-uploaded'
    assert sent_events[0]['detail'] == {
        'tenant_id': tenant_id, 'jit_event_id': jit_event_id, 'status': 'completed',
        'execution_id': execution_id, 'new_findings_count': 0,
        'existing_findings_count': 12, 'created_at': '2021-01-01T00:00:00Z',
        'plan_items_with_findings': ['dummy-plan-item'],
        'fail_on_findings': True
    }
    assert sent_events[1]['detail-type'] == 'findings-fixed'
    assert sent_events[1]['detail']['metadata']['finding_id'] == fixed_finding['id']

    assert sent_events[2]['detail-type'] == 'FindingUpdated'
    assert sent_events[2]['detail'] == {
        'prev_resolution': 'OPEN', 'new_resolution': 'FIXED', 'has_fix_suggestion': False,
        'fix_suggestion_source': 'na', 'duration_minutes': 0.0,
        'tenant_id': tenant_id, 'finding_id': fixed_finding['id'], 'is_backlog': False,
        'asset_id': asset_id, 'asset_name': 'repo-name', 'jit_event_id': fixed_finding_jit_event_id,
        'jit_event_name': 'item_activated', 'control_name': 'control_name', 'plan_layer': 'code',
        'vulnerability_type': 'code_vulnerability', 'timestamp': '2022-01-14 00:00:00',
        'created_at': '2023-03-26T06:09:03.063186', 'test_id': 'B105',
        'plan_items': ['fixed-plan-item-1', 'fixed-plan-item-2', 'dummy-plan-item'],
        'priority_factors': [], 'priority_score': 0, 'asset_priority_score': 0,
    }
    assert sent_events[3]['detail-type'] == 'findings-updated'
    assert len(sent_events[3]['detail']['findings']) == 13

    # Assert completed status item has completed time
    status_item_from_db = status_table.scan()['Items'][0]
    assert status_item_from_db['completed_at'] == '2022-01-14T00:00:00'


@freeze_time("2022-01-14")
def test_upload_findings_completed_with_large_amount_of_findings(mocker, mocked_tables):
    tenant_id = str(uuid.uuid4())
    asset_id = str(uuid.uuid4())
    control_name = "control_name"
    created_at = "2021-01-01T00:00:00Z"
    jit_event_id = str(uuid.uuid4())
    execution_id = str(uuid.uuid4())
    _, status_table = mocked_tables

    # Initialize status item in upload_findings_status_table
    status_item = UploadFindingsStatusItem(jit_event_id=jit_event_id, jit_event_name='An event',
                                           execution_id=execution_id, created_at=created_at,
                                           tenant_id=tenant_id, snapshots_count=2, error_count=0, failed_snapshots=[],
                                           is_backlog=True)
    item = {
        PK: DbTable.get_key(tenant=tenant_id),
        SK: DbTable.get_key(jit_event_id=jit_event_id, execution_id=execution_id),
        **status_item.dict(),
    }
    status_table.put_item(Item=item)

    # Mock mongo driver
    collection = mock_mongo_driver(mocker).findings
    # Insert some mock data
    findings_to_upload = [
        build_finding_dict(finding_id=str(uuid.uuid4()), tenant_id=tenant_id, asset_id=asset_id,
                           control_name=control_name,
                           jit_event_id=jit_event_id, execution_id=execution_id,
                           with_specs=True, issue_severity='HIGH', fix_suggestion=None,
                           created_at="2023-03-26T06:09:03.063186")
        for _ in range(0, 100)
    ]
    collection.insert_many(findings_to_upload)

    event = get_dynamo_stream_event(tenant_id=tenant_id, execution_id=execution_id, jit_event_id=jit_event_id,
                                    created_at=created_at)
    with mock_eventbridge(bus_name='findings'):
        upload_findings_completed_handler(event, None)  # type: ignore

    # Assert completed status item has completed time
    status_item_from_db = status_table.scan()['Items'][0]
    assert status_item_from_db['completed_at'] == '2022-01-14T00:00:00'


@freeze_time("2022-01-14")
@responses.activate
def test_upload_findings_completed__no_slack_notification_when_not_backlog_findings(mocker, mocked_tables):
    """
    Setup:
        1) Insert one open finding to DB with severity HIGH and backlog=False
        2) Mock requests
        3) Mock create 'SendHighSeverityFindingsNotificationQueue' SQS
        4) Mock create 'SendFindingsNotificationQueue' SQS
    Test:
        1) Call 'upload_findings_completed_handler' handler

    Assert:
        1) No slack notification sent
    """
    findings_table, status_table = mocked_tables
    os.environ['ENV_NAME'] = 'prod'  # This determines the platform url in the slack notification
    tenant_id = '19881e72-6d3b-49df-b79f-298ad89b8056'
    fingerprint = 'fingerprint'
    asset_id = '19881e72-1234-49df-b79f-298ad89b8056'
    finding_id = str(uuid.uuid4())
    execution_id = '5c481b2c-aaf1-4289-b2ac-3ddc79bc0196'
    jit_event_id = '5c481b2c-aaf1-4289-b2ac-3ddc79bc0196'
    control_name = 'control_name'
    created_at = str(datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f"))
    channel = 'some_channel'

    # Initialize status item in upload_findings_status_table
    status_item = UploadFindingsStatusItem(jit_event_id=jit_event_id, jit_event_name='An event',
                                           execution_id=execution_id, created_at=created_at,
                                           tenant_id=tenant_id, snapshots_count=2, error_count=0, failed_snapshots=[],
                                           is_backlog=True)
    item = {
        PK: DbTable.get_key(tenant=tenant_id),
        SK: DbTable.get_key(jit_event_id=jit_event_id, execution_id=execution_id),
        **status_item.dict(),
    }
    status_table.put_item(Item=item)

    # Mock mongo driver
    collection = mock_mongo_driver(mocker).findings

    tenants_preferences = TenantPreferences(notifications=NotificationsPreferences(
        ignore_findings=NotificationsPreference(channel=channel, enabled=True),
        deployment_with_vulnerabilities=NotificationsPreference(channel=channel, enabled=True),
        findings_on_saved_views=NotificationsPreference(channel=channel, enabled=True),
        _action_created=NotificationsPreference(channel=channel, enabled=True),
        high_severity_findings=NotificationsPreference(channel=channel, enabled=True),
        scope=PreferencesScope.TENANT),
        status=200)
    event = get_dynamo_stream_event(tenant_id=tenant_id, execution_id=execution_id, jit_event_id=jit_event_id,
                                    created_at=created_at)
    # Setup: 1. insert one finding to DB
    finding = build_finding_dict(tenant_id=tenant_id, fingerprint=fingerprint, execution_id=execution_id,
                                 jit_event_id=jit_event_id, control_name=control_name, fix_suggestion=None,
                                 asset_id=asset_id, finding_id=finding_id, created_at=created_at, backlog=False,
                                 with_specs=True)
    collection.insert_one(finding)

    # Setup: 2. Mock requests
    mock_get_internal_token_api()
    responses.add(responses.GET, 'https://api.dummy.jit.io/tenant/preferences',
                  json=tenants_preferences.dict())

    # Mock create 'findings' event bus
    with mock_eventbridge(bus_name='findings'):
        # Setup: 3. Mock create 'SendHighSeverityFindingsNotificationQueue' SQS
        mock_sqs_queue(queue_name=SEND_HIGH_SEVERITY_OPEN_FINDINGS_NOTIFICATION_QUEUE)
        # Setup: 4. Mock create 'SendFindingsNotificationQueue' SQS
        mock_sqs_queue(queue_name=SEND_FINDINGS_SAVED_VIEW_NOTIFICATION_QUEUE)
        # Test: Call 'upload_findings_completed_handler' handler
        upload_findings_completed_handler(event, None)  # type: ignore

    # Assert: No slack notification were sent to SQS queue - High severity findings
    assert_queue_content(
        queue_name=SEND_HIGH_SEVERITY_OPEN_FINDINGS_NOTIFICATION_QUEUE,
        expected_messages=[]
    )
    # Assert: No slack notification were sent to SQS queue - Findings on saved views
    assert_queue_content(
        queue_name=SEND_FINDINGS_SAVED_VIEW_NOTIFICATION_QUEUE,
        expected_messages=[]
    )

    # Assert completed status item has completed time
    status_item_from_db = status_table.scan()['Items'][0]
    assert status_item_from_db['completed_at'] == '2022-01-14T00:00:00'


@pytest.fixture
def common_setup(mocker, mocked_tables):
    tenant_id, asset_id, jit_event_id, execution_id = str(uuid.uuid4()), str(uuid.uuid4()), \
                                                      str(uuid.uuid4()), str(uuid.uuid4())
    control_name = "control_name"
    created_at = str(datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f"))
    _, status_table = mocked_tables

    # Initialize status item
    status_item = UploadFindingsStatusItem(
        jit_event_id=jit_event_id, jit_event_name='An event',
        execution_id=execution_id, created_at=created_at,
        tenant_id=tenant_id, snapshots_count=2, error_count=0,
        failed_snapshots=[], is_backlog=True
    )
    item = {
        PK: DbTable.get_key(tenant=tenant_id),
        SK: DbTable.get_key(jit_event_id=jit_event_id, execution_id=execution_id),
        **status_item.dict(),
    }
    status_table.put_item(Item=item)

    collection = mock_mongo_driver(mocker).findings
    return tenant_id, asset_id, control_name, created_at, jit_event_id, execution_id, collection, status_table


@freeze_time("2022-01-14")
@responses.activate
def test_upload_findings_completed__new_open_finding(common_setup):
    """
    Setup:
        1) Insert new finding with resolution 'OPEN'
    Test:
        1) Call 'upload_findings_completed_handler' handler

    Assert:
        1) Assert the types of the sent events and their specific contents:
            1.1 'execution-findings-uploaded' event
            1.2 'findings-created' event
            1.3 'FindingOpened' event
        2) Assert that the status item in the database is updated correctly with a 'completed_at' timestamp
    """
    # Setup
    tenant_id, asset_id, control_name, created_at, jit_event_id, execution_id, collection, status_table = \
        common_setup

    # Insert new finding with resolution 'OPEN'
    new_open_finding = build_finding_dict(resolution=Resolution.OPEN,
                                          backlog=True,
                                          finding_id="new_open_finding",
                                          tenant_id=tenant_id,
                                          asset_id=asset_id,
                                          control_name=control_name,
                                          jit_event_id=jit_event_id,
                                          execution_id=execution_id,
                                          created_at=created_at,
                                          fix_suggestion=None,
                                          )
    collection.insert_one(new_open_finding)
    event = get_dynamo_stream_event(tenant_id=tenant_id, execution_id=execution_id, jit_event_id=jit_event_id,
                                    created_at=created_at)

    # Act
    with mock_eventbridge(bus_name='findings') as get_sent_events:
        upload_findings_completed_handler(event, None)  # type: ignore

    # Assert
    sent_events = get_sent_events()

    # Assert total number of events sent
    assert len(sent_events) == 3

    # Assert the types of the sent events and their specific contents
    assert_execution_findings_uploaded_event(
        event=sent_events[0],
        jit_event_id=jit_event_id,
        execution_id=execution_id,
        created_at=created_at,
        new_count=1,
        existing_count=0,
        fail_on_findings=True)
    assert_findings_event(event=sent_events[1],
                          findings=[new_open_finding],
                          event_type='findings-created')
    assert_finding_changed_event(event=sent_events[2],
                                 finding=new_open_finding,
                                 event_type='FindingOpened',
                                 new_resolution=Resolution.OPEN)
    # Assert completed status item has completed time
    status_item_from_db = status_table.scan()['Items'][0]
    assert status_item_from_db['completed_at'] == '2022-01-14T00:00:00'


@freeze_time("2022-01-14")
@responses.activate
def test_upload_findings_completed__recurring_open_finding(common_setup):
    """
    Setup:
        1) Insert recurring finding with resolution 'OPEN', was created in previous executions
    Test:
        1) Call 'upload_findings_completed_handler' handler

    Assert:
        1) Assert the types of the sent events and their specific contents:
            1.1. 'execution-findings-uploaded' event
            1.2. 'findings-updated' event
        2) Assert that the status item in the database is updated correctly with a 'completed_at' timestamp
    """
    # Setup
    tenant_id, asset_id, control_name, created_at, jit_event_id, execution_id, collection, status_table = \
        common_setup

    # Insert existing finding with resolution 'OPEN'
    existing_open_finding = build_finding_dict(
        resolution=Resolution.OPEN,
        backlog=True,
        finding_id="existing_open_finding",
        tenant_id=tenant_id,
        asset_id=asset_id,
        control_name=control_name,
        jit_event_id=jit_event_id,
        execution_id=execution_id,
        created_at="2023-03-26T06:09:03.063186",
        fix_suggestion=None,
    )
    collection.insert_one(existing_open_finding)

    event = get_dynamo_stream_event(tenant_id=tenant_id, execution_id=execution_id, jit_event_id=jit_event_id,
                                    created_at=created_at)

    # Act
    with mock_eventbridge(bus_name='findings') as get_sent_events:
        upload_findings_completed_handler(event, None)  # type: ignore

    # Assert
    sent_events = get_sent_events()

    # Assert total number of events sent
    assert len(sent_events) == 2

    # Assert the types of the sent events and their specific contents
    assert_execution_findings_uploaded_event(event=sent_events[0],
                                             jit_event_id=jit_event_id,
                                             execution_id=execution_id,
                                             created_at=created_at,
                                             existing_count=1,
                                             new_count=0,
                                             fail_on_findings=True)
    assert_findings_event(event=sent_events[1],
                          findings=[existing_open_finding],
                          event_type='findings-updated')

    # Assert completed status item has completed time
    status_item_from_db = status_table.scan()['Items'][0]
    assert status_item_from_db['completed_at'] == '2022-01-14T00:00:00'


@freeze_time("2022-01-14")
@responses.activate
def test_upload_findings_completed__fixed_finding(common_setup):
    """
    Setup:
        1) Insert finding with resolution 'FIXED'
    Test:
        1) Call 'upload_findings_completed_handler' handler

    Assert:
        1) Assert the types of the sent events and their specific contents:
            1.1. 'execution-findings-uploaded' event
            1.2. 'findings-fixed' event
            1.3. 'FindingUpdated' event should reflect:
               - The transition of a finding from 'OPEN' to 'FIXED'
            1.4. 'findings-updated' event
        2) Assert that the status item in the database is updated correctly with a 'completed_at' timestamp
    """
    # Setup
    tenant_id, asset_id, control_name, created_at, jit_event_id, execution_id, collection, status_table = \
        common_setup

    # Insert finding that was fixed in this execution
    fixed_finding = build_finding_dict(resolution=Resolution.FIXED,
                                       fixed_at_execution_id=execution_id,
                                       finding_id="fixed_finding",
                                       execution_id=str(uuid.uuid4()),
                                       created_at="2023-03-26T06:09:03.063186",
                                       tenant_id=tenant_id,
                                       backlog=True,
                                       fix_suggestion=None,
                                       asset_id=asset_id,
                                       control_name=control_name,
                                       jit_event_id=jit_event_id)

    collection.insert_one(fixed_finding)

    event = get_dynamo_stream_event(tenant_id=tenant_id, execution_id=execution_id, jit_event_id=jit_event_id,
                                    created_at=created_at)

    # Act
    with mock_eventbridge(bus_name='findings') as get_sent_events:
        upload_findings_completed_handler(event, None)  # type: ignore

    # Assert
    sent_events = get_sent_events()

    # Assert total number of events sent
    assert len(sent_events) == 4

    # Assert the types of the sent events and their specific contents
    assert_execution_findings_uploaded_event(event=sent_events[0],
                                             jit_event_id=jit_event_id,
                                             execution_id=execution_id,
                                             created_at=created_at,
                                             existing_count=0,
                                             new_count=0,
                                             fail_on_findings=False)

    assert_findings_fixed_event(event=sent_events[1], fixed_finding=fixed_finding)
    assert_finding_changed_event(event=sent_events[2],
                                 finding=fixed_finding,
                                 event_type='FindingUpdated',
                                 prev_resolution=Resolution.OPEN,
                                 new_resolution=Resolution.FIXED)
    assert_findings_event(event=sent_events[3],
                          findings=[fixed_finding],
                          event_type='findings-updated')

    # Assert completed status item has completed time
    status_item_from_db = status_table.scan()['Items'][0]
    assert status_item_from_db['completed_at'] == '2022-01-14T00:00:00'


@freeze_time("2022-01-14")
@responses.activate
def test_upload_findings_completed___recurring_inactive_finding(common_setup):
    """
    Setup:
        1) Insert finding with resolution 'INACTIVE'
    Test:
        1) Call 'upload_findings_completed_handler' handler
    Assert:
        1) Assert the types of the sent events and their specific contents:
            1.1) 'execution-findings-uploaded' event
            1.2) 'findings-updated' event
        2) Assert that the status item in the database is updated correctly with a 'completed_at' timestamp
    """
    # Setup
    tenant_id, asset_id, control_name, created_at, jit_event_id, execution_id, collection, status_table = \
        common_setup

    # Insert finding that turned inactive in this execution
    inactive_finding = build_finding_dict(
        resolution=Resolution.INACTIVE,
        ignored=True,
        backlog=True,
        finding_id="inactive_finding",
        tenant_id=tenant_id,
        asset_id=asset_id,
        control_name=control_name,
        jit_event_id=jit_event_id,
        execution_id=execution_id,
        fix_suggestion=None,
        created_at="2023-03-26T06:09:03.063186",
    )
    collection.insert_one(inactive_finding)

    event = get_dynamo_stream_event(tenant_id=tenant_id, execution_id=execution_id, jit_event_id=jit_event_id,
                                    created_at=created_at)

    # Act
    with mock_eventbridge(bus_name='findings') as get_sent_events:
        upload_findings_completed_handler(event, None)  # type: ignore

    # Assert
    sent_events = get_sent_events()

    # Assert total number of events sent
    assert len(sent_events) == 2

    # Assert the types of the sent events and their specific contents.
    assert_execution_findings_uploaded_event(event=sent_events[0],
                                             jit_event_id=jit_event_id,
                                             execution_id=execution_id,
                                             created_at=created_at,
                                             existing_count=1,
                                             new_count=0,
                                             fail_on_findings=False)
    assert_findings_event(event=sent_events[1],
                          findings=[inactive_finding],
                          event_type='findings-updated')

    # Assert completed status item has completed time
    status_item_from_db = status_table.scan()['Items'][0]
    assert status_item_from_db['completed_at'] == '2022-01-14T00:00:00'


@freeze_time("2022-01-14")
@responses.activate
def test_upload_findings_completed__new_open_ignored_finding(common_setup):
    """
    Test a scenario where a finding that was uploaded in the current execution is ignored and open.
    Setup:
        1) Insert new open ignored finding
    Test:
        1) Call 'upload_findings_completed_handler' handler

    Assert:
        1) Assert the types of the sent events and their specific contents:
            1.1 'execution-findings-uploaded' event
            1.2 'findings-created' event
            1.3 'FindingOpened' event
        2) Assert that the status item in the database is updated correctly with a 'completed_at' timestamp
    """
    # Setup
    tenant_id, asset_id, control_name, created_at, jit_event_id, execution_id, collection, status_table = \
        common_setup

    # Insert finding with resolution 'OPEN' ignored=true
    new_open_ignored_finding = build_finding_dict(
        resolution=Resolution.OPEN,
        ignored=True,
        backlog=True,
        finding_id="ignored_finding",
        tenant_id=tenant_id,
        asset_id=asset_id,
        control_name=control_name,
        jit_event_id=jit_event_id,
        execution_id=execution_id,
        created_at=created_at,
        fix_suggestion=None,
    )
    # Insert findings into mongo
    collection.insert_one(new_open_ignored_finding)

    event = get_dynamo_stream_event(tenant_id=tenant_id, execution_id=execution_id, jit_event_id=jit_event_id,
                                    created_at=created_at)

    # Act
    with mock_eventbridge(bus_name='findings') as get_sent_events:
        upload_findings_completed_handler(event, None)  # type: ignore

    # Assert
    sent_events = get_sent_events()

    # Assert total number of events sent
    assert len(sent_events) == 3

    # Assert the types of the sent events and their specific contents
    assert_execution_findings_uploaded_event(event=sent_events[0],
                                             jit_event_id=jit_event_id,
                                             execution_id=execution_id,
                                             created_at=created_at,
                                             existing_count=0,
                                             new_count=1,
                                             fail_on_findings=False)

    assert_findings_event(event=sent_events[1],
                          findings=[new_open_ignored_finding],
                          event_type='findings-created')
    assert_finding_changed_event(event=sent_events[2],
                                 finding=new_open_ignored_finding,
                                 event_type='FindingOpened',
                                 new_resolution=UiResolution.IGNORED)

    # Assert completed status item has completed time
    status_item_from_db = status_table.scan()['Items'][0]
    assert status_item_from_db['completed_at'] == '2022-01-14T00:00:00'

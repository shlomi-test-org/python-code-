import json
from uuid import uuid4
from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Dict, Any

import responses
import boto3 as boto3
from freezegun import freeze_time
from moto import mock_s3, mock_ssm

from jit_utils.jit_clients.github_service.endpoints import GET_VENDOR_EXECUTION_FAILURE
from jit_utils.models.execution import FetchLogsEvent, VendorExecutionFailureMetricsEvent, VendorFailureReason
from jit_utils.models.execution_context import Runner
from jit_utils.models.execution_priority import ExecutionPriority
from jit_utils.models.github.github_api_objects import GetVendorExecutionFailureResponse
from jit_utils.service_discovery import get_service_url
from jit_utils.models.execution import ResourceType, Execution

from test_utils.aws.mock_eventbridge import mock_eventbridge
from test_utils.aws.mock_sqs import create_mock_queue_and_get_sent_events

from src.handlers.resources_watchdog import free_resources_handler
from src.lib.constants import BATCH_ITEMS_FAILURE, JIT_GCP_JOB_LOGS_BUCKET_NAME
from src.lib.constants import EXECUTION_EVENT_BUS_NAME
from src.lib.constants import EXECUTION_FAILURE_METRIC_DETAIL_TYPE
from src.lib.constants import ITEM_IDENTIFIER
from src.lib.constants import MAX_RESOURCES_IN_USE
from src.lib.constants import MESSAGE_ID
from src.lib.constants import SLACK_CHANNEL_NAME_RESOURCE_EXPIRED_ERRORS
from src.lib.constants import SLACK_CHANNEL_NAME_USER_MISCONFIG
from src.lib.cores.resources_watchdog_core import format_channel_name
from src.lib.data.executions_manager import ExecutionsManager
from src.lib.data.resources_manager import ResourcesManager
from src.lib.models.client_models import InternalSlackMessageBody
from src.lib.models.execution_models import ExecutionStatus, UpdateRequest
from src.lib.models.github_models import CancelWorkflowRunRequest
from src.lib.models.resource_models import Resource, ResourceInUse

from tests.component.mock_gcp.mock_batch_service_client import mock_gcp_batch_service_client
from tests.component.mock_gcp.mock_logger import mock_gcp_logging_client
from tests.component.mock_gcp.mock_service_account import mock_gcp_service_account
from tests.component.mock_responses.mock_authentication_service import mock_get_internal_token_api
from tests.component.mock_responses.mock_github_service import mock_get_vendor_failure
from tests.mocks.execution_mocks import generate_mock_executions
from tests.mocks.resources_mocks import generate_mock_resource_in_use, generate_mock_resources
from tests.mocks.tenant_mocks import MOCK_TENANT_ID


def scan_executions_table():
    execution_manager = ExecutionsManager()
    items = execution_manager.table.scan()["Items"]
    return items


def scan_resources_table():
    resources_manager = ResourcesManager()
    items = resources_manager.table.scan()["Items"]
    return items


def generate_create_resources_query(resources_manager: ResourcesManager, resources_to_create: List[Resource]) -> \
        List[Dict[str, Any]]:
    return ([
        resources_manager.generate_create_resource_query(resource)
        for resource in resources_to_create])


def generate_create_resources_in_use_query(resources_manager: ResourcesManager,
                                           resources_to_create: List[ResourceInUse]) -> \
        List[Dict[str, Any]]:
    return ([
        resources_manager.generate_create_resource_in_use_query(resource_in_use)
        for resource_in_use in resources_to_create])


def put_items(resources_manager: ResourcesManager, items: List[Dict[str, Any]]):
    max_items_in_batch = 25
    for i in range(0, len(items), max_items_in_batch):
        resources_manager.execute_transaction(items[i:i + max_items_in_batch])


def put_execution_items(execution_manager: ExecutionsManager, items: List[Execution]):
    for execution in items:
        update_request = UpdateRequest(
            tenant_id=execution.tenant_id,
            jit_event_id=execution.jit_event_id,
            execution_id=execution.execution_id,
            execution_timeout=execution.execution_timeout,
            status=ExecutionStatus.RUNNING,
        )
        if execution.status == ExecutionStatus.RUNNING:
            update_request.status = None
        execution_manager.create_execution(execution)
        execution_manager.update_execution(update_request, execution.plan_item_slug, execution.job_runner)


@responses.activate
@mock_s3
@mock_ssm
def test_free_resources_handler__gcp__happy_flow(
        executions_manager,
        resources_manager,
        mock_events_fixt,
        mock_sqs_fixt,
        mocker,
):
    """
    Test that the free resources handler successfully frees resources
    Setup:
        1. Create resources for tenant
        2. Mock the GCP Feature Flag
        3. Create resources in use for tenant
        4. Create executions records for tenant
        5. Modify the execution_id and jit_event_id to match the resources in use
        6. Put the executions in the table

    Test:
        1. Send the event to the free resources handler

    Assert:
        1. Assert that the resources in use were freed
        2. Assert that the executions were updated to WATCHDOG_TIMEOUT
        3. Assert that the correct events were sent
        4. Assert that the correct messages were sent
        5. Assert that the correct failed messages were returned
        6. Assert logs has been uploaded to GCP
        7. Assert job has been deleted from GCP
    """

    # Mock GCP clients
    mock_gcp_service_account(mocker)
    mock_batch_service_client = mock_gcp_batch_service_client(mocker)
    mock_gcp_logging_client(mocker)

    mock_tenant_id = str(uuid4())
    s3_client = boto3.client('s3', **{'region_name': 'us-east-1'})
    s3_client.create_bucket(Bucket=JIT_GCP_JOB_LOGS_BUCKET_NAME)

    ssm = boto3.client("ssm", region_name="us-east-1")
    ssm.put_parameter(
        Name="/local/infra/gcp-batch/free-resources-gcp-credentials",
        Value="{}",
        Type="SecureString",
    )

    # Create resources for tenant
    resources_to_create = generate_mock_resources(mock_tenant_id)
    JIT_RUNNER_RESOURCE_TYPE_INDEX = 2
    resources_to_create[JIT_RUNNER_RESOURCE_TYPE_INDEX].resources_in_use = \
        resources_to_create[JIT_RUNNER_RESOURCE_TYPE_INDEX].max_resources_in_use = MAX_RESOURCES_IN_USE
    resources_to_create_queries = generate_create_resources_query(resources_manager, resources_to_create)
    put_items(resources_manager, resources_to_create_queries)
    resources_items = scan_resources_table()
    assert len(resources_items) == len(resources_to_create)

    # Mock GCP feature flag
    mocker.patch("src.lib.cores.execution_runner.cloud_execution_runners.evaluate_feature_flag", return_value=True)

    # Create resources in use for tenant
    resource_to_test = resources_to_create[JIT_RUNNER_RESOURCE_TYPE_INDEX]
    resources_in_use = generate_mock_resource_in_use(mock_tenant_id, ResourceType.JIT,
                                                     resource_to_test.resources_in_use)
    resources_in_use_queries = generate_create_resources_in_use_query(resources_manager, resources_in_use)
    put_items(resources_manager, resources_in_use_queries)
    resources_in_use_items = scan_resources_table()
    assert len(resources_in_use_items) == len(resources_in_use) + len(resources_to_create)

    # Create executions records for tenant
    stale_time = (datetime.utcnow() + timedelta(hours=2)).isoformat()
    executions_to_create = generate_mock_executions(
        executions_amount=MAX_RESOURCES_IN_USE,
        tenant_id=mock_tenant_id,
        status=ExecutionStatus.DISPATCHING,
        execution_timeout=stale_time,
        run_id="123",
        job_runner=Runner.JIT,
    )
    failed_executions = generate_mock_executions(
        executions_amount=2,
        tenant_id=mock_tenant_id,
        status=ExecutionStatus.DISPATCHING,
        execution_timeout=stale_time,
        run_id="123",
        job_runner=Runner.JIT,
    )

    # Modify the execution_id and jit_event_id to match the resources in use
    for i in range(len(executions_to_create)):
        executions_to_create[i].execution_id = resources_in_use[i].execution_id
        executions_to_create[i].jit_event_id = resources_in_use[i].jit_event_id

    # Put the executions in the table
    put_execution_items(executions_manager, executions_to_create)
    executions_items = scan_executions_table()
    assert len(executions_items) == len(executions_to_create)

    event = {
        'Records': [
            {'body': execution.json(), MESSAGE_ID: str(uuid4())}
            for execution
            in executions_to_create + failed_executions
        ],
    }

    messages = create_mock_queue_and_get_sent_events("SendInternalNotificationQueue")
    response = free_resources_handler(event, None)
    # The last two event records contains the failed executions
    expected_failed_event_records = event['Records'][-2:]
    expected_response = {
        'batchItemFailures': [{'itemIdentifier': r['messageId']} for r in expected_failed_event_records]
    }
    assert response == expected_response
    sent_messages = messages()
    assert len(sent_messages) == 1
    assert InternalSlackMessageBody(**sent_messages[0])

    resources_in_use_items = scan_resources_table()
    assert len(resources_in_use_items) == len(resources_to_create)
    executions_items = scan_executions_table()
    for execution in executions_items:
        assert Execution(**execution).status == ExecutionStatus.WATCHDOG_TIMEOUT

    uploaded_logs = s3_client.list_objects(Bucket=JIT_GCP_JOB_LOGS_BUCKET_NAME)
    assert len(uploaded_logs['Contents']) == len(executions_to_create)
    expected_logs_keys = [f"{mock_tenant_id}/{execution.jit_event_id}-{execution.execution_id}.log" for execution in
                          executions_to_create]
    assert sorted([log['Key'] for log in uploaded_logs['Contents']]) == sorted(expected_logs_keys)

    assert mock_batch_service_client.delete_job_calls == [execution.run_id for execution in executions_to_create]


def _mock_events_that_should_fetch_vendor_error(executions: List[Execution]) -> Tuple[Execution, Execution]:
    mock_get_internal_token_api()
    # these execution has no run id/status is not running, so we will fetch failure from vendor
    # execution 1 - doesn't have run_id -> should fetch
    executions[0].run_id = None
    executions[0].status = ExecutionStatus.DISPATCHING
    # execution 1 - doesn't have run_id -> should fetch
    executions[1].run_id = None
    executions[1].status = ExecutionStatus.DISPATCHED
    # execution 2 - has run_id but status is not running -> should fetch
    executions[2].run_id = None
    executions[2].status = ExecutionStatus.DISPATCHED
    _mock_get_vendor_execution_failure(executions[0], VendorFailureReason.NO_GITHUB_CI_MINUTES, "123")
    _mock_get_vendor_execution_failure(executions[1], VendorFailureReason.BAD_USER_CONFIGURATIONS, None)
    _mock_get_vendor_execution_failure(executions[2], None, None)
    return executions[1], executions[2]


def _mock_get_vendor_execution_failure(
        execution: Execution, reason: Optional[VendorFailureReason], run_id: Optional[str]
):
    url = GET_VENDOR_EXECUTION_FAILURE.format(
        base_url=get_service_url("github-service")["service_url"],
        execution_id=execution.execution_id,
    )
    body = json.dumps({})
    status = 404
    if reason:
        body = GetVendorExecutionFailureResponse(
            tenant_id=execution.tenant_id,
            run_id=run_id,
            reason=reason,
            error_body="error_body",
        ).json()
        status = 200
    responses.add(method=responses.GET, url=url, body=body, status=status)


def _assert_sent_messages(sent_messages, expected_messages_num: int):
    # each of the non-failed execution should produce 1 sqs message will notify our channel
    assert len(sent_messages) == expected_messages_num
    user_misconfig_channel = format_channel_name(SLACK_CHANNEL_NAME_USER_MISCONFIG)
    resource_management_channel = format_channel_name(SLACK_CHANNEL_NAME_RESOURCE_EXPIRED_ERRORS)
    for sent_message in sent_messages:
        assert InternalSlackMessageBody(**sent_message)
        slack_message = json.dumps(InternalSlackMessageBody(**sent_message).blocks)
        if "job failed for user" in slack_message:
            assert sent_message['channel_id'] == user_misconfig_channel
        else:
            assert sent_message['channel_id'] == resource_management_channel


def _assert_sent_events(
        executions: List[Execution],
        no_run_id_execution: Optional[Execution],
        no_run_id_and_vendor_failure: Optional[Execution],
        sent_events: List[dict],
):
    # extract all metrics events
    metrics_events = [event for event in sent_events if event["detail-type"] == EXECUTION_FAILURE_METRIC_DETAIL_TYPE]
    assert len(metrics_events) == 2
    for metrics_event in metrics_events:
        assert VendorExecutionFailureMetricsEvent(**metrics_event["detail"])
        sent_events.remove(metrics_event)
    # extract the event for the execution with no run_id (since it only has update-execution + metric events)
    events_no_run_id = [
        event for event in sent_events
        if "execution_id" in event["detail"] and event["detail"]["execution_id"] == no_run_id_execution.execution_id
    ]
    for event_no_run_id in events_no_run_id:
        sent_events.remove(event_no_run_id)
    # extract the event for the execution with no run_id and vendor failure (only has update-execution + metric events)
    events_no_run_id_and_vendor_failure = [
        event for event in sent_events
        if "execution_id" in event["detail"]
           and event["detail"]["execution_id"] == no_run_id_and_vendor_failure.execution_id
    ]
    for event_no_run_id_and_vendor_failure in events_no_run_id_and_vendor_failure:
        sent_events.remove(event_no_run_id_and_vendor_failure)

    # each of the non-failed events should produce 3 events - update-execution + terminate + fetch-logs
    events_per_executions_number = 3
    assert len(sent_events) == (len(executions) - 2) * events_per_executions_number
    for i in range(0, len(sent_events), events_per_executions_number):
        assert Execution(**sent_events[i]["detail"])
        assert CancelWorkflowRunRequest(**sent_events[i + 1]["detail"])
        assert FetchLogsEvent(**sent_events[i + 2]["detail"])

    # each of the non-failed events should be in sent events
    original_execution_ids = [
        e.execution_id for e in executions
        if e.execution_id not in [no_run_id_execution.execution_id, no_run_id_and_vendor_failure.execution_id]
    ]
    execution_ids_in_events = [
        Execution(**s["detail"]).execution_id for s in sent_events[::events_per_executions_number]
    ]
    assert original_execution_ids == execution_ids_in_events


def setup_data(resources_manager, executions_manager, is_should_add_events_with_no_run_id=False):
    """
    This function sets up mock data for resources and executions within a system:
    Step 1: Generate a mock tenant ID and create resources for the tenant.
    Step 2: Validate that the number of resources created matches the desired amount.
    Step 3: Create records for resources currently in use by the tenant.
    Step 4: Validate the total number of resources in the table including those in use.
    Step 5: Create mock execution records for the tenant and validate their addition to the executions table.
    Step 6: Create an event object with execution records to simulate a dispatching event for the system.

    The function returns created execution records, failed execution records,
    created resources, and the generated event.
    """

    mock_tenant_id = str(uuid4())
    # Step 1: Generate a mock tenant ID and create resources for the tenant.
    resources_to_create = generate_mock_resources(mock_tenant_id)
    resources_to_create[0].resources_in_use = resources_to_create[0].max_resources_in_use = MAX_RESOURCES_IN_USE
    resources_to_create_queries = generate_create_resources_query(resources_manager, resources_to_create)
    put_items(resources_manager, resources_to_create_queries)
    resources_items = scan_resources_table()
    # Step 2: Validate that the number of resources created matches the desired amount.
    assert len(resources_items) == len(resources_to_create)

    # Step 3: Create records for resources currently in use by the tenant.
    resource_to_test = resources_to_create[0]
    resources_in_use = generate_mock_resource_in_use(mock_tenant_id, ResourceType.CI,
                                                     resource_to_test.resources_in_use)
    resources_in_use_queries = generate_create_resources_in_use_query(resources_manager, resources_in_use)
    put_items(resources_manager, resources_in_use_queries)
    resources_in_use_items = scan_resources_table()
    # Step 4: Validate the total number of resources in the table including those in use.
    assert len(resources_in_use_items) == len(resources_in_use) + len(resources_to_create)

    # Step 5: Create mock execution records for the tenant and validate their addition to the executions table.
    stale_time = (datetime.utcnow() + timedelta(hours=2)).isoformat()
    executions_to_create = generate_mock_executions(
        executions_amount=MAX_RESOURCES_IN_USE,
        tenant_id=mock_tenant_id,
        status=ExecutionStatus.RUNNING,
        execution_timeout=stale_time,
        run_id="123",
    )
    failed_executions = generate_mock_executions(
        executions_amount=2,
        tenant_id=mock_tenant_id,
        status=ExecutionStatus.DISPATCHING,
        execution_timeout=stale_time,
        run_id="123",
    )
    # Modify the execution_id and jit_event_id to match the resources in use
    for i in range(len(executions_to_create)):
        executions_to_create[i].execution_id = resources_in_use[i].execution_id
        executions_to_create[i].jit_event_id = resources_in_use[i].jit_event_id
    no_run_id_execution, no_run_id_and_vendor_failure = None, None
    if is_should_add_events_with_no_run_id:
        no_run_id_execution, no_run_id_and_vendor_failure = _mock_events_that_should_fetch_vendor_error(
            executions_to_create
        )
    # Put the executions in the table
    put_execution_items(executions_manager, executions_to_create)
    executions_items = scan_executions_table()
    assert len(executions_items) == len(executions_to_create)

    # Step 6: Create an event object with execution records to simulate a dispatching event for the system.
    event = {
        'Records': [
            {'body': execution.json(), MESSAGE_ID: str(uuid4())}
            for execution
            in executions_to_create + failed_executions
        ],
    }

    return executions_to_create, failed_executions, resources_to_create, \
        event, no_run_id_execution, no_run_id_and_vendor_failure


def validate_execution_records(event, failed_executions, resources_to_create, response):
    """
    This function conducts a series of validation checks on execution records to ensure their consistency:
    Step 1: Validate the failed message IDs extracted from a batch response.
    Step 2: Ensure the number of these failed message IDs aligns with the count of failed executions.
    Step 3: Confirm that these failed message IDs correspond with the event records.
    Step 4: Compare the number of resources currently in use to the count of those designated for creation.
    Step 5: Ensure all execution items within a table hold a status of 'WATCHDOG_TIMEOUT'.
    Any discrepancies in these steps will trigger an `AssertionError` exception.
    """

    # Extract failed message IDs from the response's batch item failures.
    failed_message_ids = [failed_message[ITEM_IDENTIFIER] for failed_message in response[BATCH_ITEMS_FAILURE]]

    # Assert that the number of failed message IDs matches the number of failed executions.
    assert len(failed_message_ids) == len(failed_executions)

    # Assert that the failed message IDs match the message IDs from the last two records in the event.
    assert failed_message_ids == [record[MESSAGE_ID] for record in event['Records'][-2:]]

    # Scan the resources table and get all the items.
    resources_in_use_items = scan_resources_table()

    # Assert that the number of items in the resources table matches the number of resources to be created.
    assert len(resources_in_use_items) == len(resources_to_create)

    # Scan the executions table and get all the execution items.
    executions_items = scan_executions_table()

    # For each execution item in the executions table:
    for execution in executions_items:
        # Assert that the status of the execution is 'WATCHDOG_TIMEOUT'.
        assert Execution(**execution).status == ExecutionStatus.WATCHDOG_TIMEOUT


@responses.activate
def test_free_resources_handler__new_flow(
        executions_manager,
        resources_manager,
        mock_events_fixt,
        mock_sqs_fixt,
):
    """Test that the free resources handler successfully frees resources

    # TODO: Copied it from being a flaky integration tests, need to rewrite in a more cleaner way
    """

    executions_to_create, failed_executions, resources_to_create, \
        event, no_run_id_execution, no_run_id_and_vendor_failure = setup_data(resources_manager,
                                                                              executions_manager, True)

    with mock_eventbridge([EXECUTION_EVENT_BUS_NAME]) as events:
        messages = create_mock_queue_and_get_sent_events("SendInternalNotificationQueue")
        response = free_resources_handler(event, None)
        sent_events = events[EXECUTION_EVENT_BUS_NAME]()
        sent_messages = messages()
        _assert_sent_events(executions_to_create, no_run_id_execution, no_run_id_and_vendor_failure, sent_events)
        _assert_sent_messages(sent_messages, 2)

        validate_execution_records(event, failed_executions, resources_to_create, response)


@responses.activate
def test_free_resources_separation_slack_messages_only_resource_errors(
        executions_manager,
        resources_manager,
        mock_events_fixt,
        mock_sqs_fixt,
):
    """Test that the free resources handler successfully frees resources
    """

    executions_to_create, failed_executions, resources_to_create, event, _, _ = setup_data(resources_manager,
                                                                                           executions_manager)
    messages = create_mock_queue_and_get_sent_events("SendInternalNotificationQueue")
    response = free_resources_handler(event, None)
    sent_messages = messages()
    _assert_sent_messages(sent_messages, 1)
    validate_execution_records(event, failed_executions, resources_to_create, response)


@freeze_time("2022-12-12T00:00:00.000000")
def test_free_resources__dont_manage_high_priority(
        executions_manager,
        resources_manager,
        mock_events_fixt,
        mock_sqs_fixt,
):
    """
    Test that the handler does not free resources for high priority executions when the feature flag is set.
    Setup:
        - Create a tenant with resources
        - Create a high priority dispatching execution that should be watchdog timed-out
        - Mock the feature flag to return True for skipping high priority executions
        - Mock the eventbridge + sqs
    Test:
        - Call the handler
    Assert:
        - The handler doesn't throw an exception
        - The execution completion event is sent
        - The execution vendor cancellation event is sent
        - The execution fetch log event is sent
        - The execution has a watchdog_timeout status
    """
    # Setup - Create resources for tenant
    resources_to_create = generate_mock_resources(MOCK_TENANT_ID)
    resources_to_create_queries = generate_create_resources_query(resources_manager, resources_to_create)
    put_items(resources_manager, resources_to_create_queries)

    # Setup - Create a high priority execution to watchdog timeout
    stale_time = (datetime.utcnow() + timedelta(hours=2)).isoformat()
    execution_to_create = generate_mock_executions(
        executions_amount=1,
        tenant_id=MOCK_TENANT_ID,
        status=ExecutionStatus.RUNNING,
        execution_timeout=stale_time,
        run_id="123",
        job_runner=Runner.CI,
        priority=ExecutionPriority.HIGH,
    )
    executions_manager.create_execution(execution_to_create[0])

    # Setup - Mock the eventbridge
    with mock_eventbridge(bus_name=EXECUTION_EVENT_BUS_NAME) as get_sent_events:
        create_mock_queue_and_get_sent_events("SendInternalNotificationQueue")
        # Test
        event = {
            "Records": [{"body": execution_to_create[0].json(), MESSAGE_ID: str(uuid4())}],
        }
        assert free_resources_handler(event, None)  # This means no exception was thrown

        # Assert
        sent_events = get_sent_events()
        assert len(sent_events) == 3
        updated_execution_in_event = Execution(**sent_events[0]["detail"])
        assert updated_execution_in_event.execution_id == execution_to_create[0].execution_id
        assert CancelWorkflowRunRequest(**sent_events[1]["detail"])
        assert FetchLogsEvent(**sent_events[2]["detail"])

        items = executions_manager.table.scan()['Items']
        assert len(items) == 1
        execution_in_db = Execution(**items[0])
        assert execution_in_db.execution_id == updated_execution_in_event.execution_id
        assert execution_in_db.status == updated_execution_in_event.status == ExecutionStatus.WATCHDOG_TIMEOUT


@freeze_time("2022-12-12T00:00:00.000000")
def test_free_resources__completed_execution_not_updated(
        executions_manager,
        resources_manager,
        mock_events_fixt,
        mock_sqs_fixt,
):
    """
    Test that the handler does not process or update already completed executions.
    Setup:
        - Create a tenant with resources
        - Create a high priority execution with status set to COMPLETED
    Test:
        - Call the handler
    Assert:
        - The handler doesn't throw an exception
        - No events are sent (since the execution is already completed)
        - The execution remains in the COMPLETED status in the database
    """
    # Setup - Create resources for tenant
    resources_to_create = generate_mock_resources(MOCK_TENANT_ID)
    resources_to_create_queries = generate_create_resources_query(resources_manager, resources_to_create)
    put_items(resources_manager, resources_to_create_queries)

    # Setup - Create a high priority execution to watchdog timeout
    stale_time = (datetime.utcnow() + timedelta(hours=2)).isoformat()
    execution_to_create = generate_mock_executions(
        executions_amount=1,
        tenant_id=MOCK_TENANT_ID,
        status=ExecutionStatus.COMPLETED,
        execution_timeout=stale_time,
        run_id="123",
        job_runner=Runner.CI,
        priority=ExecutionPriority.HIGH,
    )
    executions_manager.create_execution(execution_to_create[0])

    # Setup - Mock the eventbridge
    with mock_eventbridge(bus_name=EXECUTION_EVENT_BUS_NAME) as get_sent_events:
        create_mock_queue_and_get_sent_events("SendInternalNotificationQueue")
        # Test
        event = {
            "Records": [{"body": execution_to_create[0].json(), MESSAGE_ID: str(uuid4())}],
        }
        assert free_resources_handler(event, None)  # This means no exception was thrown

        # Assert
        sent_events = get_sent_events()
        assert len(sent_events) == 0

        items = executions_manager.table.scan()['Items']
        assert len(items) == 1
        execution_in_db = Execution(**items[0])
        assert execution_in_db.execution_id == execution_to_create[0].execution_id
        assert execution_in_db.status == execution_to_create[0].status == ExecutionStatus.COMPLETED


@freeze_time("2022-12-12T00:00:00.000000")
@responses.activate
def test_free_resources__non_complete_execution_changes_to_watchdog_timeout(
        executions_manager,
        resources_manager,
        mock_events_fixt,
        mock_sqs_fixt,
):
    """
    Test that the handler does not process or update already completed executions.
    Setup:
        - Create a tenant with resources
        - Create a high priority execution with status set to DISPATCHING
    Test:
        - Call the handler
    Assert:
        - The handler doesn't throw an exception
        - 4 events are sent:
            - 'execution-completed' (complete execution)
            - 'execution-failure-metric' (fetch vendor logs)
            - 'cancel-execution' (terminate in vendor)
            - 'fetch-logs' (_send_fetch_logs_request_event)
        - The execution updates to WATCHDOG_TIMEOUT status in the database
    """
    # Setup - Create resources for tenant
    mock_get_internal_token_api()
    resources_to_create = generate_mock_resources(MOCK_TENANT_ID)
    resources_to_create_queries = generate_create_resources_query(resources_manager, resources_to_create)
    put_items(resources_manager, resources_to_create_queries)

    # Setup - Create a high priority execution to watchdog timeout
    stale_time = (datetime.utcnow() + timedelta(hours=2)).isoformat()
    execution_to_create = generate_mock_executions(
        executions_amount=1,
        tenant_id=MOCK_TENANT_ID,
        status=ExecutionStatus.DISPATCHED,
        execution_timeout=stale_time,
        run_id="123",
        priority=ExecutionPriority.HIGH,
        job_runner=Runner.CI,
    )
    executions_manager.create_execution(execution_to_create[0])
    mock_get_vendor_failure(
        execution_to_create[0].execution_id,
        GetVendorExecutionFailureResponse(
            tenant_id=MOCK_TENANT_ID,
            error_body="error_body",
            reason=VendorFailureReason.BAD_USER_CONFIGURATIONS)
    )
    # Setup - Mock the eventbridge
    with mock_eventbridge(bus_name=EXECUTION_EVENT_BUS_NAME) as get_sent_events:
        create_mock_queue_and_get_sent_events("SendInternalNotificationQueue")
        # Test
        event = {
            "Records": [{"body": execution_to_create[0].json(), MESSAGE_ID: str(uuid4())}],
        }
        assert free_resources_handler(event, None)  # This means no exception was thrown

        # Assert
        sent_events = get_sent_events()
        assert len(sent_events) == 4

        items = executions_manager.table.scan()['Items']
        assert len(items) == 1
        execution_in_db = Execution(**items[0])
        assert execution_in_db.execution_id == execution_to_create[0].execution_id
        assert execution_in_db.status == ExecutionStatus.WATCHDOG_TIMEOUT

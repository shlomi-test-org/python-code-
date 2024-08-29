import json
import os

import freezegun
import pytest
import responses
from moto import mock_sqs
from test_utils.aws.mock_sqs import create_mock_queue_and_get_sent_events

from src.handlers.pr_jit_event_watchdog import handler
from src.lib.constants import SEND_INTERNAL_NOTIFICATION_QUEUE_NAME
from src.lib.exceptions import FailedPRJitEventWatchdogException
from tests.component.utils.build_execution import build_execution
from tests.component.utils.build_jit_event_lifecycle_db_record import build_jit_event_lifecycle_db_record
from tests.component.utils.mock_responses.mock_authentication_service import mock_get_internal_token_api
from tests.component.utils.mock_responses.mock_execution_service import mock_get_executions
from tests.component.utils.mock_responses.mock_github_api import mock_get_pull_request_api, \
    mock_get_commit_check_suites_api, mock_get_checks_in_check_suite_api
from tests.component.utils.mock_responses.mock_github_service import mock_get_github_token


def _mock_apis(inserted_items):
    mock_get_internal_token_api()
    os.environ['ENV_NAME'] = 'dev'
    for jit_event_lifecycle_record in inserted_items:
        jit_event = jit_event_lifecycle_record['jit_event']
        repo = jit_event['original_repository']
        org = jit_event['owner']
        commit_sha = jit_event['commits']['head_sha']

        mock_get_executions(jit_event_id=jit_event_lifecycle_record['jit_event_id'])
        mock_get_github_token(app_id=jit_event['app_id'], installation_id=jit_event['installation_id'])
        mock_get_pull_request_api(org=org, repo=repo, head_sha=commit_sha, pr_number=jit_event['pull_request_number'])

        check_suite_id = 123456
        mock_get_commit_check_suites_api(org=org, repo=repo, commit_sha=commit_sha, jit_check_suite_id=check_suite_id)
        mock_get_checks_in_check_suite_api(org=org, repo=repo, check_suite_id=check_suite_id)


def assert_items_updated(jit_event_life_cycle_table, expected_items):
    items_in_db = jit_event_life_cycle_table.scan()['Items']
    assert len(items_in_db) == len(expected_items)
    for expected_item in expected_items:
        expected_item = {
            **expected_item,
            'modified_at': '2021-01-01T00:17:00',

        }
        expected_item.pop('GSI2PK_TTL_BUCKET')
        expected_item.pop('GSI2SK_CREATED_AT')

    item_in_db = next(item for item in items_in_db if item['jit_event_id'] == expected_item['jit_event_id'])
    assert item_in_db == expected_item


@responses.activate
@freezegun.freeze_time('2021-01-01 00:17:00')
@mock_sqs
def test_pr_jit_event_watchdog__happy_flow__nothing_stuck(dynamodb_table_mocks):
    """
    Testing a happy flow when there is one jit event to review, which has completed as expected
    Setup:
        - Create a jit event lifecycle record
        - Mock the required APIs
        - Mock Sqs
    Test:
        - Run the handler
    Assert:
        - No slack notification was sent
        - The jit event lifecycle record was updated - GSI2 is removed and modified_at is updated
    """
    ttl_bucket_index = 1
    jit_event_lifecycle_record = build_jit_event_lifecycle_db_record(created_at='2021-01-01T00:00:00',
                                                                     ttl_bucket_index=ttl_bucket_index)
    jit_event_life_cycle_table, _ = dynamodb_table_mocks
    jit_event_life_cycle_table.put_item(Item=jit_event_lifecycle_record)
    created_items = [jit_event_lifecycle_record]
    _mock_apis(created_items)
    get_sent_events = create_mock_queue_and_get_sent_events(SEND_INTERNAL_NOTIFICATION_QUEUE_NAME)
    handler({"gsi_bucket_index": str(ttl_bucket_index)}, None)

    assert_items_updated(jit_event_life_cycle_table, created_items)
    assert not get_sent_events()


@responses.activate
@freezegun.freeze_time('2021-01-01 00:17:00')
@mock_sqs
def test_pr_jit_event_watchdog__not_code_related_jit_event(dynamodb_table_mocks):
    """
    Testing a that we handle the case when the jit event is not code related.
    Setup:
        - Create a jit event lifecycle record that is not code related
        - Mock Sqs
    Test:
        - Run the handler
    Assert:
        - An exception is raised
        - No slack notification was sent
        - The jit event lifecycle record was updated - GSI2 is removed and modified_at is updated
    """
    ttl_bucket_index = 1
    jit_event_lifecycle_record = build_jit_event_lifecycle_db_record(
        created_at='2021-01-01T00:00:00',
        jit_evnet_name='manual_execution',
        jit_event_kwargs={
            'asset_ids_filter': [],
            'plan_item_slug': 'item-branch-protection-scm',
            'priority': 3,
        },
        ttl_bucket_index=ttl_bucket_index
    )
    jit_event_life_cycle_table, _ = dynamodb_table_mocks
    jit_event_life_cycle_table.put_item(Item=jit_event_lifecycle_record)
    created_items = [jit_event_lifecycle_record]
    _mock_apis(created_items)

    with pytest.raises(FailedPRJitEventWatchdogException):
        get_sent_events = create_mock_queue_and_get_sent_events(SEND_INTERNAL_NOTIFICATION_QUEUE_NAME)
        handler({"gsi_bucket_index": str(ttl_bucket_index)}, None)

    assert_items_updated(jit_event_life_cycle_table, created_items)
    assert not get_sent_events()


@responses.activate
@freezegun.freeze_time('2021-01-01 00:17:00')
@mock_sqs
def test_pr_jit_event_watchdog__has_running_executions(dynamodb_table_mocks):
    """
    Testing a that we skip checking the jit event when there are running executions.
    Setup:
        - Create a jit event lifecycle record
        - Mock the required APIs
        - Mock get_executions to return a running execution
        - Mock Sqs
    Test:
        - Run the handler
    Assert:
        - No slack notification was sent
        - The jit event lifecycle was NOT updated
    """
    ttl_bucket_index = 1
    jit_event_lifecycle_record = build_jit_event_lifecycle_db_record(created_at='2021-01-01T00:00:00',
                                                                     ttl_bucket_index=ttl_bucket_index
                                                                     )
    jit_event_life_cycle_table, _ = dynamodb_table_mocks
    jit_event_life_cycle_table.put_item(Item=jit_event_lifecycle_record)
    created_items = [jit_event_lifecycle_record]
    _mock_apis(created_items)
    # Remove the mock for get_executions
    mocked_execution_response = next(res for res in responses.registered() if 'execution' in res.url)
    responses.remove(mocked_execution_response)

    mock_get_executions(jit_event_id=jit_event_lifecycle_record['jit_event_id'],
                        executions=[json.loads(build_execution(status='running').json())])

    get_sent_events = create_mock_queue_and_get_sent_events(SEND_INTERNAL_NOTIFICATION_QUEUE_NAME)
    handler({"gsi_bucket_index": str(ttl_bucket_index)}, None)

    # Assert that the record was not updated
    items_in_db = jit_event_life_cycle_table.scan()['Items']
    assert len(items_in_db) == 1
    assert items_in_db[0] == jit_event_lifecycle_record

    assert not get_sent_events()


@responses.activate
@freezegun.freeze_time('2021-01-01 00:17:00')
@mock_sqs
def test_pr_jit_event_watchdog__skipping_when_not_last_commit_sha(dynamodb_table_mocks):
    """
    Testing a that we skip checking the jit event when the jit event is not the last commit sha.
    Setup:
        - Create a jit event lifecycle record
        - Mock the required APIs
        - Mock get_pr_details API to return a different head sha
        - Mock Sqs
    Test:
        - Run the handler
    Assert:
        - No slack notification was sent
        - The jit event lifecycle was updated
    """
    ttl_bucket_index = 1
    jit_event_lifecycle_record = build_jit_event_lifecycle_db_record(created_at='2021-01-01T00:00:00',
                                                                     ttl_bucket_index=ttl_bucket_index)
    jit_event_life_cycle_table, _ = dynamodb_table_mocks
    jit_event_life_cycle_table.put_item(Item=jit_event_lifecycle_record)
    created_items = [jit_event_lifecycle_record]
    _mock_apis(created_items)
    # Remove the mock for get_executions
    mocked_get_pr_details_response = next(res for res in responses.registered() if 'pulls' in res.url)
    responses.remove(mocked_get_pr_details_response)

    jit_event = jit_event_lifecycle_record['jit_event']
    repo = jit_event['original_repository']
    org = jit_event['owner']
    mock_get_pull_request_api(org=org, repo=repo, pr_number=jit_event['pull_request_number'],
                              head_sha='different_commit_sha')

    get_sent_events = create_mock_queue_and_get_sent_events(SEND_INTERNAL_NOTIFICATION_QUEUE_NAME)
    handler({"gsi_bucket_index": str(ttl_bucket_index)}, None)

    assert_items_updated(jit_event_life_cycle_table, created_items)
    assert not get_sent_events()


@responses.activate
@freezegun.freeze_time('2021-01-01 00:17:00')
@pytest.mark.parametrize('has_findings', [True, False])
@mock_sqs
def test_pr_jit_event_watchdog__has_failing_executions(dynamodb_table_mocks, has_findings):
    """
    Testing a that send an alert when the jit event has a failing executions.
    Setup:
        - Create a jit event lifecycle record
        - Mock the required APIs
        - Mock get_executions to return a running execution
        - Mock Sqs
    Test:
        - Run the handler
    Assert:
        - No slack notification was sent
        - The jit event lifecycle was NOT updated
    """
    ttl_bucket_index = 1
    jit_event_lifecycle_record = build_jit_event_lifecycle_db_record(created_at='2021-01-01T00:00:00',
                                                                     ttl_bucket_index=ttl_bucket_index)
    jit_event_life_cycle_table, _ = dynamodb_table_mocks
    jit_event_life_cycle_table.put_item(Item=jit_event_lifecycle_record)
    created_items = [jit_event_lifecycle_record]
    _mock_apis(created_items)
    # Remove the mock for get_executions
    mocked_execution_response = next(res for res in responses.registered() if 'execution' in res.url)
    responses.remove(mocked_execution_response)

    mock_get_executions(jit_event_id=jit_event_lifecycle_record['jit_event_id'],
                        executions=[json.loads(build_execution(status='failed', has_findings=has_findings).json())])

    get_sent_events = create_mock_queue_and_get_sent_events(SEND_INTERNAL_NOTIFICATION_QUEUE_NAME)
    handler({"gsi_bucket_index": str(ttl_bucket_index)}, None)

    assert_items_updated(jit_event_life_cycle_table, created_items)

    if has_findings:
        assert not get_sent_events()
    else:
        assert len(get_sent_events()) == 1


@responses.activate
@freezegun.freeze_time('2021-01-01 00:17:00')
@mock_sqs
def test_pr_jit_event_watchdog__repo_not_found(dynamodb_table_mocks):
    """
    Testing that we handle the case when the repo is not found.
    Setup:
        - Create a jit event lifecycle record
        - Mock the required APIs, but with a 404 response for the get_pull_request API
        - Mock get_executions to return a running execution
        - Mock Sqs
    Test:
        - Run the handler
    Assert:
        - No slack notification was sent
        - The jit event lifecycle was NOT updated
    """
    ttl_bucket_index = 1
    jit_event_lifecycle_record = build_jit_event_lifecycle_db_record(created_at='2021-01-01T00:00:00',
                                                                     ttl_bucket_index=ttl_bucket_index)
    jit_event_life_cycle_table, _ = dynamodb_table_mocks
    jit_event_life_cycle_table.put_item(Item=jit_event_lifecycle_record)
    created_items = [jit_event_lifecycle_record]
    _mock_apis(created_items)
    # Remove the mock for get_pr_details
    mocked_get_pr_details_response = next(res for res in responses.registered() if 'pulls' in res.url)
    responses.remove(mocked_get_pr_details_response)
    jit_event = jit_event_lifecycle_record['jit_event']
    repo = jit_event['original_repository']
    org = jit_event['owner']
    commit_sha = jit_event['commits']['head_sha']
    pr_number = jit_event['pull_request_number']
    mock_get_pull_request_api(org=org, repo=repo, head_sha=commit_sha, pr_number=pr_number)

    get_sent_events = create_mock_queue_and_get_sent_events(SEND_INTERNAL_NOTIFICATION_QUEUE_NAME)
    handler({"gsi_bucket_index": str(ttl_bucket_index)}, None)

    assert not get_sent_events()


@responses.activate
@freezegun.freeze_time('2021-01-01 00:17:00')
@mock_sqs
def test_pr_jit_event_watchdog__github_installation_not_found(dynamodb_table_mocks):
    """
    Testing that we handle the case when the GitHub installation is not found (404 error).
    Setup:
        - Create a jit event lifecycle record
        - Mock the required APIs, with a 404 response for the get_github_token API
        - Mock Sqs
    Test:
        - Run the handler
    Assert:
        - No slack notification was sent
        - The jit event lifecycle was updated - GSI2 is removed and modified_at is updated
    """
    ttl_bucket_index = 1
    jit_event_lifecycle_record = build_jit_event_lifecycle_db_record(created_at='2021-01-01T00:00:00',
                                                                     ttl_bucket_index=ttl_bucket_index)
    jit_event_life_cycle_table, _ = dynamodb_table_mocks
    jit_event_life_cycle_table.put_item(Item=jit_event_lifecycle_record)
    created_items = [jit_event_lifecycle_record]
    _mock_apis(inserted_items=created_items)
    mock_get_internal_token_api()
    os.environ['ENV_NAME'] = 'dev'

    # remove mocks for executions and installations
    for res in list(responses.registered()):
        if 'execution' in res.url or 'installation' in res.url:
            responses.remove(res)

    # Include an execution with a watchdog_timeout status
    mock_get_executions(jit_event_id=jit_event_lifecycle_record['jit_event_id'],
                        executions=[json.loads(build_execution(status='watchdog_timeout').json())])

    # GitHub Installations API should return 404 in this case
    mock_get_github_token(
        app_id=jit_event_lifecycle_record['jit_event']['app_id'],
        installation_id=jit_event_lifecycle_record['jit_event']['installation_id'],
        return_code=404
    )

    get_sent_events = create_mock_queue_and_get_sent_events(SEND_INTERNAL_NOTIFICATION_QUEUE_NAME)
    handler({"gsi_bucket_index": str(ttl_bucket_index)}, None)

    # Assert that the record was updated (GSI2 is removed)
    assert_items_updated(jit_event_life_cycle_table, created_items)
    assert not get_sent_events()


@responses.activate
@freezegun.freeze_time('2021-01-01 00:17:00')
@mock_sqs
def test_pr_jit_event_watchdog__non_github_event(dynamodb_table_mocks):
    """
    Testing a happy flow when there is one jit event to review, which has completed as expected
    Setup:
        - Create a jit event lifecycle record for non github vendor
        - Mock Sqs
    Test:
        - Run the handler
    Assert:
        - No slack notification was sent
        - The jit event lifecycle record was updated
    """
    ttl_bucket_index = 1
    jit_event_lifecycle_record = build_jit_event_lifecycle_db_record(created_at='2021-01-01T00:00:00',
                                                                     ttl_bucket_index=ttl_bucket_index,
                                                                     vendor="gitlab")
    jit_event_life_cycle_table, _ = dynamodb_table_mocks
    jit_event_life_cycle_table.put_item(Item=jit_event_lifecycle_record)
    created_items = [jit_event_lifecycle_record]
    get_sent_events = create_mock_queue_and_get_sent_events(SEND_INTERNAL_NOTIFICATION_QUEUE_NAME)
    handler({"gsi_bucket_index": str(ttl_bucket_index)}, None)

    assert_items_updated(jit_event_life_cycle_table, created_items)
    assert not get_sent_events()

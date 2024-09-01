import datetime
import json

import boto3
import freezegun
from jit_utils.event_models.trigger_event import INTERNAL_FAILURE_EVENT_BUS_NAME
from moto import mock_sqs
from test_utils.aws import idempotency
from test_utils.aws.mock_eventbridge import mock_eventbridge
from jit_utils.aws_clients.config.aws_config import get_aws_config

from src.lib.constants import SEND_INTERNAL_NOTIFICATION_QUEUE_NAME, ENV_NAME
from src.lib.models.jit_event_life_cycle import JitEventDBEntity
from tests.component.conftest import setup_jit_event_life_cycle_in_db


@mock_sqs
@freezegun.freeze_time("2024-03-24T16:37:54Z")
def test_handler_sends_message_to_sqs(
        mocker,
        monkeypatch,
        jit_event_life_cycle_manager,
        jit_event_mock,
):
    from src.handlers import step_function_failure
    idempotency.mock_idempotent_decorator(
        mocker=mocker,
        module_to_reload=step_function_failure,
    )
    monkeypatch.setenv(ENV_NAME, "test")

    mock_event = {
        "version": "0",
        "id": "315c1398-40ff-a850-213b-158f73e60175",
        "detail-type": "Step Functions Execution Status Change",
        "source": "aws.states",
        "account": "123456789012",
        "time": "2019-02-26T19:42:21Z",
        "region": "us-east-1",
        "resources": ["arn:aws:states:us-east-1:123456789012:execution:state-machine-name:execution-name"],
        "detail": {
            "executionArn": "arn:aws:states:us-east-1:123456789012:execution:state-machine-name:execution-name",
            "stateMachineArn": "arn:aws:states:us-east-1:123456789012:stateMachine:state-machine",
            "name": "execution-name",
            "status": "FAILED",
            "startDate": 1551225146847,
            "stopDate": 1551225151881,
            "input": json.dumps({
                "jit_event": jit_event_mock.dict(),
            }),
            "output": None,
            "error": "States.Runtime",
            "cause": "An error occurred while executing the state 'Has Enricher?' (entered at the event id #2)."
                     " Invalid path '$.should_enrich': The choice state's condition path references an invalid value."
        }
    }

    expected_jit_event_mock, expected_jit_event_db_mock = setup_jit_event_life_cycle_in_db(
        jit_event_life_cycle_manager=jit_event_life_cycle_manager,
        jit_event_mock=jit_event_mock,
        total_assets=2,
    )

    with mock_eventbridge(bus_name=[INTERNAL_FAILURE_EVENT_BUS_NAME]) as get_events:
        sqs = boto3.client('sqs', **get_aws_config())
        sqs.create_queue(QueueName=SEND_INTERNAL_NOTIFICATION_QUEUE_NAME)
        queue_url = sqs.get_queue_url(QueueName=SEND_INTERNAL_NOTIFICATION_QUEUE_NAME)['QueueUrl']

        step_function_failure.handler(mock_event, None)

    internal_failure_events = get_events[INTERNAL_FAILURE_EVENT_BUS_NAME]()
    assert len(internal_failure_events) == 1
    assert internal_failure_events[0] == {
        'account': '123456789012',
        'detail': {
            'event_type': 'code-related-internal-failure',
            'failure_message': 'Internal failure Enrichment Step Function',
            'jit_event': expected_jit_event_mock.dict(),
            'tenant_id': expected_jit_event_mock.tenant_id,
        },
        'detail-type': 'internal-failure',
        'id': internal_failure_events[0]['id'],
        'region': 'us-east-1',
        'resources': [],
        'source': 'trigger-service',
        'time': '2024-03-24T16:37:54Z',
        'version': '0',
    }

    # Check DB for expected state
    response = jit_event_life_cycle_manager.table.scan()
    assert len(response["Items"]) == 1

    # assert Jit Event remaining_assets is -1
    jit_event_db_entity = JitEventDBEntity(**response["Items"][0])
    expected_jit_event_db_mock.remaining_assets = 1
    assert jit_event_db_entity == expected_jit_event_db_mock

    # Checking if the Slack message was sent to the SQS queue
    messages = sqs.receive_message(QueueUrl=queue_url)
    assert 'Messages' in messages, "No message was sent to the SQS queue"

    sent_message = json.loads(messages['Messages'][0]['Body'])
    assert sent_message == json.loads(
        '{"text": "(= ФェФ=) `Step Function Failure Alert` (= ФェФ=)\\n'
        'Status: `FAILED`\\n'
        'Error: `States.Runtime`\\n'
        f"Start Time: {datetime.datetime.fromtimestamp(mock_event['detail']['startDate'] / 1000).isoformat()}\\n"
        f"End Time: {datetime.datetime.fromtimestamp(mock_event['detail']['stopDate'] / 1000).isoformat()}\\n"
        'Execution URL: https://console.aws.amazon.com/states/home?#/v2/executions/details/'
        'arn:aws:states:us-east-1:123456789012:execution:state-machine-name:execution-name", '
        '"channel_id": "jit-errors-test", "blocks": null}'
    )


@freezegun.freeze_time("2024-03-24T16:37:54Z")
def test_handler_returns_without_slack_msg_on_watchdog_timeout(
        mocker,
        monkeypatch,
        jit_event_life_cycle_manager,
        jit_event_mock,
):
    """
    Tests the step_function_failure.handler's
     behavior when dealing with a Step Function execution failure due to a watchdog timeout.

    Setup:
      - Freeze time for consistent test conditions.
      - Mock idempotency and environment setup.
      - Prepare a mock event simulating a Step Function failure.
      - Configure mocks and expected conditions for JIT Event lifecycle and database entries.

    Execution:
      - Invoke the handler with the mock event.

    Assertions:
      - Verify the handler returns None.
      - Verify no internal failure events are published.
      - Ensure the JIT Event's remaining_assets is correctly updated in the database.
      - Check that no Slack messages are dispatched to the SQS queue for internal notifications.
    """
    from src.handlers import step_function_failure
    idempotency.mock_idempotent_decorator(
        mocker=mocker,
        module_to_reload=step_function_failure,
    )
    monkeypatch.setenv(ENV_NAME, "test")

    mock_event = {
        "version": "0",
        "id": "315c1398-40ff-a850-213b-158f73e60175",
        "detail-type": "Step Functions Execution Status Change",
        "source": "aws.states",
        "account": "123456789012",
        "time": "2019-02-26T19:42:21Z",
        "region": "us-east-1",
        "resources": ["arn:aws:states:us-east-1:123456789012:execution:state-machine-name:execution-name"],
        "detail": {
            "executionArn": "arn:aws:states:us-east-1:123456789012:execution:state-machine-name:execution-name",
            "stateMachineArn": "arn:aws:states:us-east-1:123456789012:stateMachine:state-machine",
            "name": "execution-name",
            "status": "FAILED",
            "startDate": 1551225146847,
            "stopDate": 1551225151881,
            "input": json.dumps({
                "jit_event": jit_event_mock.dict(),
            }),
            "output": None,
            "error": "States.Runtime",
            "cause": "{\"tenant_id\": \"12d91528-3e9d-4143-b165-2e0857a3701c\","
                     " \"jit_event_id\": \"7cde59f5-29fb-43a6-9b87-fdb487f94c57\","
                     " \"execution_id\": \"ad9be1eb-1fbf-4a8e-a869-e6e2126a3ef0\","
                     " \"entity_type\": \"job\", \"plan_item_slug\": \"DEPENDS_ON_PLAN_ITEM_SLUG\","
                     " \"workflow_slug\": \"workflow-enrichment-code\", \"job_name\": \"enrich\","
                     " \"control_name\": \"Run code enrichment\","
                     " \"control_image\": \"registry.jit.io/control-enrichment-slim:latest\","
                     " \"jit_event_name\": \"pull_request_created\","
                     " \"task_token\": \"AQCIAAAAKgAAAAMAAAAAAAAAAXAL//k/QQGWs/GFO/lXmCzCyXDuwHxf/ggR5\","
                     " \"created_at\": \"2024-03-26T08:53:10.107594\", \"created_at_ts\": 1711443190,"
                     " \"dispatched_at\": \"2024-03-26T08:53:13.774016\","
                     " \"dispatched_at_ts\": 1711443193, \"completed_at\": \"2024-03-26T09:00:33.002164\","
                     " \"completed_at_ts\": 1711443633, \"status\": \"watchdog_timeout\","
                     " \"status_details\": {\"message\": \"Exceeded time limitation\"},"
                     " \"job_runner\": \"github_actions\", \"resource_type\": \"github_actions_high_priority\","
                     " \"plan_slug\": \"jit-plan\", \"asset_type\": \"repo\", \"asset_name\": \"flipAlot\","
                     " \"asset_id\": \"85862e41-b010-49dd-86ab-f5e88dace689\", \"vendor\": \"github\", \"priority\": 1,"
                     " \"control_type\": \"enrichment\", \"execution_timeout\": \"2024-03-26T08:58:13.775079\","
                     " \"affected_plan_items\": []}"
        }
    }

    expected_jit_event_mock, expected_jit_event_db_mock = setup_jit_event_life_cycle_in_db(
        jit_event_life_cycle_manager=jit_event_life_cycle_manager,
        jit_event_mock=jit_event_mock,
        total_assets=2,
    )

    with mock_eventbridge(bus_name=INTERNAL_FAILURE_EVENT_BUS_NAME) as get_events:
        sqs = boto3.client('sqs', **get_aws_config())
        sqs.create_queue(QueueName=SEND_INTERNAL_NOTIFICATION_QUEUE_NAME)
        queue_url = sqs.get_queue_url(QueueName=SEND_INTERNAL_NOTIFICATION_QUEUE_NAME)['QueueUrl']

        response = step_function_failure.handler(mock_event, None)
        assert response is None

    # asset internal failure event was sent, so we close the jit security check
    events = get_events()
    assert len(events) == 1

    # Check DB for expected state
    response = jit_event_life_cycle_manager.table.scan()
    assert len(response["Items"]) == 1

    # assert Jit Event remaining_assets is -1
    jit_event_db_entity = JitEventDBEntity(**response["Items"][0])
    expected_jit_event_db_mock.remaining_assets = 1
    assert jit_event_db_entity == expected_jit_event_db_mock

    # Checking if the Slack message was sent to the SQS queue
    messages = sqs.receive_message(QueueUrl=queue_url)
    assert 'Messages' not in messages

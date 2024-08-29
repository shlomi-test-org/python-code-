import json

import boto3
from jit_utils.event_models import CodeRelatedJitEvent
from jit_utils.event_models.trigger_event import BulkTriggerExecutionEvent
from test_utils.aws_config import get_aws_config
from test_utils.step_functions.execution_visualizer import ExecutionVisualizer

from src.lib.constants import TRIGGER_EXECUTION_BUS_NAME, TRIGGER_EXECUTION_DETAIL_TYPE_TRIGGER_EVENT
from src.lib.cores.jit_event_life_cycle.jit_event_life_cycle_handler import JitEventLifeCycleHandler


def create_queue_and_subscribe_to_eventbridge(queue_name, event_bus_name, detail_type):
    event_bridge = boto3.client('events', **get_aws_config())

    sqs = boto3.client('sqs', **get_aws_config())
    queue = sqs.create_queue(QueueName=queue_name)
    queue_url = queue['QueueUrl']

    # make sure the queue is empty -
    # when running the test multiple times (usually locally), the queue may already have messages
    sqs.purge_queue(QueueUrl=queue_url)
    queue_arn = sqs.get_queue_attributes(QueueUrl=queue['QueueUrl'],
                                         AttributeNames=['QueueArn'])['Attributes']['QueueArn']

    try:
        event_bridge.create_event_bus(Name=event_bus_name)
    except Exception as e:
        print(e)

        # Resource already exists
        pass
    event_bridge.put_rule(
        Name=f"trigger-service-events-rule-{queue_name}",
        EventBusName=event_bus_name,
        EventPattern="{" + f"\"source\": [\"trigger-service\"], \"detail-type\": [\"{detail_type}\"]" + "}"
    )
    event_bridge.put_targets(Rule=f"trigger-service-events-rule-{queue_name}", EventBusName=event_bus_name,
                             Targets=[
                                 {
                                     'Id': '1',
                                     'Arn': queue_arn,
                                 }
                             ])

    return sqs, queue_url


def setup_listener_for_enrichment_execution_event():
    return create_queue_and_subscribe_to_eventbridge(
        queue_name="enrichment_queue",
        event_bus_name=TRIGGER_EXECUTION_BUS_NAME,
        detail_type=TRIGGER_EXECUTION_DETAIL_TYPE_TRIGGER_EVENT,
    )


def execute_state_machine(local_stack_step_function, event):
    # Starting the lifecycle of the JIT event
    JitEventLifeCycleHandler().start(jit_event=CodeRelatedJitEvent(**event['jit_event']))
    return local_stack_step_function.start_execution(
        state_machine_arn=local_stack_step_function.get_state_machine_arn("local-handle-enrichment-process"),
        payload=event,
    )


def listen_to_enrichment_execution_event(queue, queue_url):
    enrich_message = queue.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=1, WaitTimeSeconds=20)["Messages"][0]
    return json.loads(enrich_message["Body"])["detail"]["TaskToken"]


def listen_to_the_actual_executions_we_need_to_run(queue, queue_url):
    final_message = queue.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=1, WaitTimeSeconds=20)["Messages"][0]
    return BulkTriggerExecutionEvent(**json.loads(final_message["Body"])["detail"])


def assert_state_machine_steps(history, expected_steps, has_execution_succeeded=True):
    if has_execution_succeeded:
        assert any(step["type"] == "ExecutionSucceeded" for step in history)
    else:
        assert any(step["type"] == "ExecutionFailed" for step in history)
    steps = [step["stateExitedEventDetails"]["name"] for step in history if step["type"] == "TaskStateExited"]
    assert steps == expected_steps, f"Expected steps: {expected_steps}, Actual steps: {steps}"


def visualize(local_stack_step_function, history):
    redacted_history = local_stack_step_function.get_redacted_execution(history)
    vis = ExecutionVisualizer(redacted_history)
    vis.visualize()

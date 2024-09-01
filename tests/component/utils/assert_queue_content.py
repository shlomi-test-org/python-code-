import json
import boto3


def assert_queue_content(queue_name, expected_messages):
    sqs_client = boto3.client("sqs", region_name="us-east-1")
    queue_url = sqs_client.get_queue_url(QueueName=queue_name)["QueueUrl"]
    messages = sqs_client.receive_message(QueueUrl=queue_url).get('Messages', [])
    assert len(messages) == len(expected_messages)

    for msg_index, expected_msg in enumerate(expected_messages):
        parsed_message = json.loads(messages[msg_index]['Body'])
        assert expected_msg == parsed_message

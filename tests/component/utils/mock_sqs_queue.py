import boto3


def mock_sqs_queue(queue_name):
    sqs_client = boto3.client("sqs", region_name="us-east-1")
    sqs_client.create_queue(QueueName=queue_name)

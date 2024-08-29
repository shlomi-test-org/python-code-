import boto3
from jit_utils.aws_clients.config.aws_config import get_aws_config
from jit_utils.logger import logger
from jit_utils.service_discovery import get_queue_url


class SQSClient:
    """
    A client for connecting to AWS SQS
    """

    def __init__(self):
        self.client = boto3.client('sqs', **get_aws_config())

    def send_fifo_messages_batch(self, queue_name, messages):
        """
        Send a batch of FIFO messages to an SQS queue
        """
        queue_url = get_queue_url(queue_name)

        response = self.client.send_message_batch(
            QueueUrl=queue_url,
            Entries=messages)

        logger.info(f"SQS response: {response}")

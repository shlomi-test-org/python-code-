import os
from typing import Optional
from typing import Sequence
from typing import Union

from jit_utils.logger import logger
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.models.blocks import Block

from src.lib.constants import SLACK_NOTIFICATIONS_BOT_TOKEN


class SlackClient:
    """
    A client for connecting to Slack
    """

    def __init__(self):
        self.token = os.environ.get(SLACK_NOTIFICATIONS_BOT_TOKEN, '')
        self.client = WebClient(token=self.token)

    def send_message(self, channel_id, message, blocks: Optional[Sequence[Union[dict, Block]]] = None) -> None:
        """
        Send a message to Slack
        """
        try:
            if not self.token:
                logger.error('No slack token found')
                return
            # Call the chat.postMessage method using the WebClient
            result = self.client.chat_postMessage(
                channel=channel_id,
                text=message,
                blocks=blocks,
            )
            logger.info(result)
        except SlackApiError as e:
            logger.exception(f"Error posting message: {e}")

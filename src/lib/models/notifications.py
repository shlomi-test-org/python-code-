from typing import Optional, Sequence, Union

from pydantic import BaseModel
from slack_sdk.models.blocks import Block


class InternalSlackMessageBody(BaseModel):
    text: str
    channel_id: str
    blocks: Optional[Sequence[Union[dict, Block]]] = None

    # To support blocks validation in pydantic
    class Config:
        arbitrary_types_allowed = True

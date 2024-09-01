from __future__ import annotations

import re

import botocore
from pydantic import BaseModel

UUID4_PATTERN = r"[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}"


class GetLogRequest(BaseModel):
    jit_event_id: str
    execution_id: str


class GetTruncatedLogWithPresignedResult(BaseModel):
    content: str
    truncated: bool
    presigned_url_read: str


class ControlLogs(BaseModel):
    tenant_id: str
    jit_event_id: str
    execution_id: str
    stream: botocore.response.StreamingBody
    s3_url: str

    class Config:
        arbitrary_types_allowed = True

    @staticmethod
    def initialize(key: str, stream: botocore.response.StreamingBody, s3_url: str) -> ControlLogs:
        """
        This static method initializes a new ControlLogs object with a given file key and content.
        :param key: The S3 file key. The file format is '{tenant_id}/{jit_event_id}-{execution_id}.log'.
        :param stream: The S3 file stream body. We will use it to read the file in chunks.
        :param s3_url: The S3 file URL. We will use it to generate a share URL for the S3 object in aws console.

        :return: A ControlLogs object initialized from the given data.
        """
        key_split = key.split("/")
        try:
            uuids_from_key = re.findall(UUID4_PATTERN, key_split[1])
        except IndexError:
            raise ValueError(f"Key isn't valid UUID. {key=}")

        return ControlLogs(
            tenant_id=key_split[0],
            jit_event_id=uuids_from_key[0],
            execution_id=uuids_from_key[1],
            stream=stream,
            s3_url=s3_url
        )

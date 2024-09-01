import botocore
from jit_utils.aws_clients.s3 import S3Client
from jit_utils.lambda_decorators import get_s3_session_keys
from jit_utils.logger import logger
from pydantic import BaseModel

from src.lib.constants import EXECUTION_LOG_S3_OBJECT_KEY


class GetLogStreamResponse(BaseModel):
    stream: botocore.response.StreamingBody
    content_length: int

    class Config:
        arbitrary_types_allowed = True


class ExecutionLogNotFoundException(Exception):
    def __init__(self, s3_object_key: str):
        self.s3_object_key = s3_object_key
        super().__init__(f"Log not found in S3 ({s3_object_key})")


class ExecutionLogManager:
    def __init__(self, tenant_id: str, jit_event_id: str, execution_id: str, bucket: str):
        self.s3_object_key = EXECUTION_LOG_S3_OBJECT_KEY.format(
            tenant_id=tenant_id,
            jit_event_id=jit_event_id,
            execution_id=execution_id,
        )
        self.bucket = bucket

        # Pass s3 session keys created in tenant isolation (aws config),
        # if tenant isolation exists will use its credentials, if not S3Client will use default conf
        self.s3 = S3Client(get_s3_session_keys())

    def does_object_exist(self) -> bool:
        try:
            self.s3.client.head_object(Bucket=self.bucket, Key=self.s3_object_key)
            return True
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == "404":
                return False
            raise

    def get_log_stream(self) -> GetLogStreamResponse:
        """Returns a StreamingBody object of the execution log content from S3 and the size of the object in bytes.

        If the object does not exist, an ExecutionLogNotFoundException will be raised.
        StreamingBody docs: https://botocore.amazonaws.com/v1/documentation/api/latest/reference/response.html#botocore.response.StreamingBody # noqa
        """
        try:
            response = self.s3.client.get_object(
                Bucket=self.bucket,
                Key=self.s3_object_key,
            )
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == "NoSuchKey":
                logger.error(f"Execution log file not found ({self.s3_object_key})")
                raise ExecutionLogNotFoundException(self.s3_object_key)
            raise

        return GetLogStreamResponse(
            stream=response['Body'],
            content_length=response['ContentLength'],
        )

    def get_log_presigned_url_read(self) -> str:
        """Gets a presigned URL for reading the execution log file from S3.

        If the object does not exist, an ExecutionLogNotFoundException will be raised.
        """
        # Check if the object exists first because generate_presigned_url doesn't validate that the object exists
        if not self.does_object_exist():
            raise ExecutionLogNotFoundException(self.s3_object_key)

        return self.s3.client.generate_presigned_url(
            ClientMethod='get_object',
            Params={
                "Bucket": self.bucket,
                "Key": self.s3_object_key,
            },
        )

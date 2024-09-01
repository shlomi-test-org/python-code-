from http import HTTPStatus
from typing import List
from typing import Literal
from typing import Optional

import botocore
from jit_utils.aws_clients.s3 import S3Client
from jit_utils.lambda_decorators.core.tenant_isolation.tenant_isolation_context import get_general_session_keys
from jit_utils.logger import logger

from src.lib.constants import DOWNLOAD_URL_EXPIRATION_SECONDS
from src.lib.constants import MAX_OUTPUTS_UPLOAD_FILES
from src.lib.constants import PUBLIC_ARTIFACTS_ARCHIVE_BASE_NAME
from src.lib.constants import S3_EXECUTION_OUTPUTS_BUCKET_NAME
from src.lib.constants import S3_OUTPUTS_UPLOAD_URL_EXPIRATION_SECONDS
from src.lib.exceptions import UploadOutputFilesTooManyFiles
from src.lib.models.output_files import ControlOutputFileUploadedResponse
from src.lib.models.output_files import UploadControlOutputFileRequest


def get_output_file_key_name(tenant_id: str, jit_event_id: str, execution_id: str, file_name: str) -> str:
    return f'{tenant_id}/{jit_event_id}-{execution_id}/{file_name}'


def generate_output_upload_url(tenant_id: str, jit_event_id: str, execution_id: str, file_name: str) -> str:
    key_name = get_output_file_key_name(tenant_id, jit_event_id, execution_id, file_name)

    logger.info(
        f"Generating output upload url for tenant {tenant_id}, "
        f"jit_event_id {jit_event_id}, "
        f"execution_id {execution_id}, "
        f"file_name {file_name}, "
        f"key_name {key_name}"
    )

    s3_client = S3Client(aws_config=get_general_session_keys())
    return s3_client.generate_put_presigned_url(
        bucket_name=S3_EXECUTION_OUTPUTS_BUCKET_NAME,
        key=key_name,
        expiration_seconds=S3_OUTPUTS_UPLOAD_URL_EXPIRATION_SECONDS,
    )


def generate_output_files_pre_sign_urls(
        tenant_id: str, request: UploadControlOutputFileRequest) -> List[ControlOutputFileUploadedResponse]:
    if len(request.files) > MAX_OUTPUTS_UPLOAD_FILES:
        raise UploadOutputFilesTooManyFiles()

    response = []
    for file in request.files:
        logger.info(f"Generating output upload url for file {file.file_name}")

        url = generate_output_upload_url(
            tenant_id=tenant_id,
            jit_event_id=request.jit_event_id,
            execution_id=request.execution_id,
            file_name=file.file_name,
        )
        response.append(ControlOutputFileUploadedResponse(file_name=file.file_name, upload_url=url))

    return response


def get_execution_artifacts_archive_download_url(tenant_id: str, event_id: str, execution_id: str,
                                                 archive_type: Literal['zip']) -> Optional[str]:
    s3_client = S3Client(aws_config=get_general_session_keys())
    public_archive_base_name = get_output_file_key_name(tenant_id, event_id, execution_id,
                                                        PUBLIC_ARTIFACTS_ARCHIVE_BASE_NAME)
    public_archive_key = f'{public_archive_base_name}.{archive_type}'
    logger.info(f"Searching for public archive file {public_archive_key} in S3")
    try:
        object_metadata = s3_client.head_object(bucket_name=S3_EXECUTION_OUTPUTS_BUCKET_NAME, key=public_archive_key)
        if object_metadata:
            logger.info("Found public archive file")
            return s3_client.generate_get_presigned_url(
                bucket_name=S3_EXECUTION_OUTPUTS_BUCKET_NAME,
                key=public_archive_key,
                expiration_seconds=DOWNLOAD_URL_EXPIRATION_SECONDS,
            )
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == str(HTTPStatus.NOT_FOUND.value):
            logger.info("No public archive file found")
            return None
        raise e
    return None

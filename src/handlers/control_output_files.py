import json
from http import HTTPStatus
from typing import cast
from typing import List
from typing import Tuple

from aws_lambda_typing.context import Context
from aws_lambda_typing.events import APIGatewayProxyEventV2 as APIEvent
from jit_utils.lambda_decorators import general_tenant_isolation
from jit_utils.lambda_decorators import lambda_warmup_handler
from jit_utils.lambda_decorators import request_headers_keys
from jit_utils.lambda_decorators import response_wrapper
from jit_utils.lambda_decorators import S3IsolationRule
from jit_utils.lambda_decorators.status_code_wrapper import status_code_wrapper
from jit_utils.logger import logger
from jit_utils.logger import logger_customer_id
from jit_utils.models.common.responses import DownloadFileResponse
from jit_utils.models.common.responses import ErrorResponse
from py_api import api_documentation
from py_api import Method
from py_api import PathParameter
from py_api import Response
from pydantic import BaseModel

from src.lib.constants import S3_EXECUTION_OUTPUTS_BUCKET_NAME
from src.lib.cores.control_output_files import generate_output_files_pre_sign_urls
from src.lib.cores.control_output_files import get_execution_artifacts_archive_download_url
from src.lib.exceptions import StatusErrors
from src.lib.exceptions import UploadOutputFilesTooManyFiles
from src.lib.models.output_files import ControlOutputFileUploadedResponse
from src.lib.models.output_files import UploadControlOutputFileRequest


@lambda_warmup_handler
@request_headers_keys
@response_wrapper
@status_code_wrapper({
    UploadOutputFilesTooManyFiles: (HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                                    ErrorResponse(message=StatusErrors.TOO_MANY_FILES_TO_UPLOAD.value,
                                                  error=StatusErrors.TOO_MANY_FILES_TO_UPLOAD.name)),
})
@logger_customer_id(auto=True)
@general_tenant_isolation(
    rules=[
        S3IsolationRule(
            bucket_name=S3_EXECUTION_OUTPUTS_BUCKET_NAME,
            actions=["s3:PutObject"]
        )
    ]
)
@api_documentation(
    post=Method(
        description='Upload output files',
        method_responses={
            HTTPStatus.CREATED: Response(
                schema=List[ControlOutputFileUploadedResponse],
                description='Upload output files with pre signed urls',
                title='OutputFileResponseList',
            ),
            HTTPStatus.OK: Response(
                schema=List[ControlOutputFileUploadedResponse],
                description='Upload output files with no files to upload',
                title='OutputFileResponseList',
            ),
        },
    )
)
def upload(event: APIEvent, context: Context) -> Tuple[int, List[ControlOutputFileUploadedResponse]]:
    """
    Upload control output files

    if generate_pre_signed_urls is True:
        will generate pre signed urls for each file in the request

    else:
        will not upload any files
    """
    tenant_id = cast(str, event['requestContext']['authorizer']['tenant_id'])
    logger.info(f"Received request to upload output files for tenant {tenant_id}")

    payload = json.loads(event["body"])

    request = UploadControlOutputFileRequest(**payload)
    if request.generate_pre_signed_urls:
        logger.info("Starting generate_pre_signed_upload_urls")
        response = generate_output_files_pre_sign_urls(tenant_id, request)
        return HTTPStatus.CREATED if response else HTTPStatus.OK, response
    else:
        logger.info("Since generate_pre_signed_urls is False, not uploading any files")
        return HTTPStatus.OK, []


@lambda_warmup_handler
@request_headers_keys
@response_wrapper
@status_code_wrapper()
@logger_customer_id(auto=True)
@general_tenant_isolation(
    rules=[
        S3IsolationRule(
            bucket_name=S3_EXECUTION_OUTPUTS_BUCKET_NAME,
            actions=["s3:GetObject"]
        )
    ]
)
@api_documentation(
    get=Method(
        description='Get a zip archive of an execution output artifacts',
        method_responses={
            HTTPStatus.OK: Response(
                schema=DownloadFileResponse,
                description='A download url for the zip archive of the execution output artifacts',
            ),
            HTTPStatus.NOT_FOUND: Response(
                schema=ErrorResponse,
                description='No artifacts found for the given execution id',
            ),
        },
        path_parameters=[
            PathParameter(
                name='jit_event_id',
                schema=str,
                description='The jit event id',
            ),
            PathParameter(
                name='execution_id',
                schema=str,
                description='The execution id',
            ),
        ]
    )
)
def zipball(event: APIEvent, context: Context) -> Tuple[int, BaseModel]:
    """
    Fetch the control outputs artifacts zip archive for a given execution
    """
    tenant_id = cast(str, event['requestContext']['authorizer']['tenant_id'])
    logger.info(f"Received request to fetch artifacts zip archive for tenant {tenant_id}")
    path_parameters = event['pathParameters'] or {}
    event_id = path_parameters['jit_event_id']
    execution_id = path_parameters['execution_id']

    zip_url = get_execution_artifacts_archive_download_url(tenant_id, event_id, execution_id, archive_type="zip")
    if not zip_url:
        return HTTPStatus.NOT_FOUND, ErrorResponse.from_enum(StatusErrors.NO_ARTIFACTS)

    return HTTPStatus.OK, DownloadFileResponse(download_url=zip_url)

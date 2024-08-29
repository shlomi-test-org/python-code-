from typing import List

from jit_utils.lambda_decorators.status_code_wrapper import api_request
from pydantic import BaseModel


class ControlOutputFile(BaseModel):
    file_name: str


@api_request
class UploadControlOutputFileRequest(BaseModel):
    files: List[ControlOutputFile]
    jit_event_id: str
    execution_id: str
    generate_pre_signed_urls: bool


class ControlOutputFileUploadedResponse(ControlOutputFile):
    upload_url: str

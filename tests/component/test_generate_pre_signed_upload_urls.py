import json
from http import HTTPStatus
from typing import List
from uuid import uuid4

import pytest
import responses
from moto import mock_s3

from src.handlers.control_output_files import upload
from src.lib.constants import MAX_OUTPUTS_UPLOAD_FILES
from tests.component.fixtures import get_handler_event


def _get_mock_event(tenant_id: str, jit_event_id: str, execution_id: str, file_names: List[str],
                    generate_pre_signed_urls: bool):
    return get_handler_event(tenant_id=tenant_id, body={
        "jit_event_id": jit_event_id,
        "execution_id": execution_id,
        "files": [{"file_name": file_name} for file_name in file_names],
        "generate_pre_signed_urls": generate_pre_signed_urls
    })


@responses.activate
@mock_s3
@pytest.mark.parametrize("files_amount", [0, MAX_OUTPUTS_UPLOAD_FILES, MAX_OUTPUTS_UPLOAD_FILES + 1])
@pytest.mark.parametrize("generate_pre_signed_urls", [True, False])
def test_generate_pre_signed_upload_urls(generate_pre_signed_urls: bool, files_amount: int):
    """
    Test:
        - Generate pre-signed upload urls for output files if generate_pre_signed_urls is True
        - Don't generate pre-signed upload urls for output files if generate_pre_signed_urls is False

    Assert:
        - If generate_pre_signed_urls is True, the response should contain a list of pre-signed upload urls
        - If generate_pre_signed_urls is False, the response should not contain a list of pre-signed upload urls
        - If the amount of files is greater than MAX_OUTPUTS_UPLOAD_FILES, the response should contain an error
    """
    tenant_id = str(uuid4())
    jit_event_id = str(uuid4())
    execution_id = str(uuid4())
    file_names = [str(uuid4()) for _ in range(files_amount)]

    event = _get_mock_event(tenant_id, jit_event_id, execution_id, file_names, generate_pre_signed_urls)

    response = upload(event, None)

    status_code = response["statusCode"]
    response = response["body"]
    response_body = json.loads(response)

    should_have_created_urls = generate_pre_signed_urls and len(file_names) > 0
    should_raise_error = generate_pre_signed_urls and len(file_names) > MAX_OUTPUTS_UPLOAD_FILES

    if should_raise_error:
        assert status_code == HTTPStatus.REQUEST_ENTITY_TOO_LARGE
        assert response_body["error"] == "TOO_MANY_FILES_TO_UPLOAD"
        assert response_body["message"] == "Too many files to upload"
    else:
        assert status_code == HTTPStatus.CREATED if should_have_created_urls else HTTPStatus.OK
        assert len(response_body) == (len(file_names) if should_have_created_urls else 0)

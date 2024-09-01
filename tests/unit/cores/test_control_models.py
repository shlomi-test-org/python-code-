import uuid
from io import BytesIO

import pytest
from botocore.response import StreamingBody

from src.lib.models.log_models import ControlLogs


TEST_TENANT_ID = str(uuid.uuid4())
TEST_JIT_EVENT_ID = str(uuid.uuid4())
TEST_EXECUTION_ID = str(uuid.uuid4())
TEST_S3_URL = "IMA URL"
TEST_STREAM = StreamingBody(BytesIO(b""), len(b""))


def test_initialize_control_logs():
    control_logs = ControlLogs.initialize(
        f"{TEST_TENANT_ID}/{TEST_JIT_EVENT_ID}-{TEST_EXECUTION_ID}", TEST_STREAM, TEST_S3_URL
    )
    assert control_logs.tenant_id == TEST_TENANT_ID
    assert control_logs.jit_event_id == TEST_JIT_EVENT_ID
    assert control_logs.execution_id == TEST_EXECUTION_ID
    assert control_logs.s3_url == TEST_S3_URL


def test_initialize_control_logs__execution_id_is_not_uuid():
    with pytest.raises(Exception):
        ControlLogs.initialize(f"{TEST_TENANT_ID}/{TEST_JIT_EVENT_ID}-aaa", TEST_STREAM, TEST_S3_URL)


def test_initialize_control_logs__bad_object_key():
    with pytest.raises(Exception):
        ControlLogs.initialize("aaaaaaaaa", TEST_STREAM, TEST_S3_URL)

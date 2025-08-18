"""A template for an integration tests file for a control.

The main purpose is to test a specific image of a control, and mock all backend points, to which the container sends
requests.
"""

import base64
import json
import logging
import os
from pathlib import Path

import pytest as pytest
from test_utils.controls import assertions
from test_utils.controls.aws import (
    generate_presigned_put_object,
    get_uploaded_object,
)
from test_utils.controls.docker_ import get_docker_network_by_prefix, run_container
from test_utils.controls.jit import get_test_github_event

logger = logging.getLogger(__name__)

IMAGE_NAME = os.environ["TEST_IMAGE_NAME"]
IMAGE_TAG = os.environ["TEST_IMAGE_TAG"]
# IMAGE_NAME = "kics"
# IMAGE_TAG = "latest"

TEST_DATA_DIRECTORY = Path.cwd() / "tests" / "data"


logger.info(f"Using image {IMAGE_NAME}:{IMAGE_TAG}")


def get_container_command(framework):
    return ' '.join([
        "scan",
        "-t",
        "CloudFormation,Pulumi,Terraform,ServerlessFW",
        "-p",
        "${WORK_DIR:-.}",
        "-o",
        "$REPORT_FILE",
        "--config",
        f"/{framework}-config.yaml",
        "--report-formats",
        "json",
        "--disable-secrets",
    ])


@pytest.mark.parametrize(
    "count, framework",
    [
        (15, "terraform"),
        # (1, "pulumi"),
        # (1, "serverless"),
        # (10, "cloud-formation"),
        # (9, "cdk"),
    ],
)
def test_control__without_backend(count, framework):
    result, container = run_container(
        image=f"{IMAGE_NAME}:{IMAGE_TAG}",
        command=f"'{get_container_command(framework)}'",
        environment={
            "SECURITY_CONTROL_OUTPUT_FILE": "/code/jit-report/results.json",
        },
        volumes={
            str(Path.cwd() / "tests" / "data" / framework): {
                "bind": "/code",
                "mode": "rw",
            }
        },
        platform="linux/amd64",
        privileged=True,  # important for the instrumented image
        stderr=True,
    )
    assert result['StatusCode'] == 0, f"Container exited with code {result['StatusCode']}."

    logs: bytes = container.logs()
    try:
        # Decode in attempt to get the colorized output
        logger.info(f"Output: \n\n{logs.decode('utf-8')}\n")
    except UnicodeDecodeError as e:
        logger.warning(f"Failed to decode output, printing encoded. Error: {e}")
        logger.info(f"Output: \n\n{logs}\n")
        pass

    assertions.assert_string_appearance(
        buffer=logs,
        min_lines=30,
        expected=[
            f"Found {count} findings".encode(),
            b"Control 'KICS' ended with status 'PASS'",
        ],
        unexpected=[
            b"[404]",
            b"[500]",
        ],
    )


@pytest.mark.parametrize(
    "count, framework",
    [
        (15, "terraform"),
        (1, "pulumi"),
        (1, "serverless"),
        (10, "cloud-formation"),
        (9, "cdk"),
    ],
)
def test_control__with_backend(count, framework, execution_id, s3_mock_client):
    event = get_test_github_event(
        execution_id=execution_id,
        callback_urls={
            'presigned_findings_upload_url': generate_presigned_put_object(
                s3=s3_mock_client,
                bucket_name='upload-findings-bucket',
                key=f'some-tenant-id/{execution_id}-findings.json',
            ).replace('localhost:9090', 's3-mock:9090'),
            'presigned_logs_upload_url': generate_presigned_put_object(
                s3=s3_mock_client,
                bucket_name='upload-logs-bucket',
                key=f'some-tenant-id/{execution_id}-logs.json',
            ).replace('localhost:9090', 's3-mock:9090'),
            'execution': 'http://execution-service',
            'ignores': 'http://finding-service/asset/some-id/control/some-control-name/ignore',
            'finding_schema': 'http://finding-service/schema/{schema_type}/version/{schema_version}',
        },
    )

    result, container = run_container(
        image=f"{IMAGE_NAME}:{IMAGE_TAG}",
        command=f"'{get_container_command(framework)}'",
        environment={
            "GITHUB_EVENT": base64.b64encode(json.dumps(event).encode()).decode(),
            "SECURITY_CONTROL_OUTPUT_FILE": "/code/jit-report/results.json",
        },
        volumes={
            str(Path.cwd() / "tests" / "data" / framework): {
                "bind": "/code",
                "mode": "rw",
            }
        },
        platform="linux/amd64",
        privileged=True,  # important for the instrumented image
        network=get_docker_network_by_prefix('github_network_'),
    )
    assert result['StatusCode'] == 0, f"Container exited with code {result['StatusCode']}."

    logs: bytes = container.logs()
    try:
        # Decode before print so we can get the colorized output
        logger.info(logs.decode('utf-8'))
    except UnicodeDecodeError as e:
        logger.warning(f"Failed to decode output, printing encoded. Error: {e}")
        logger.info(f"Output: \n\n{logs}\n")
        pass

    assertions.assert_string_appearance(
        buffer=logs,
        min_lines=30,
        expected=[
            f"Found {count} findings".encode(),
            b"Control 'KICS' ended with status 'PASS'",
        ],
        unexpected=[
            b"[404]",
            b"[500]",
        ],
    )

    uploaded_logs = get_uploaded_object(
        s3=s3_mock_client,
        bucket_name='upload-logs-bucket',
        key=f'some-tenant-id/{execution_id}-logs.json',
    )
    logger.info(f"Uploaded logs:\n\n{uploaded_logs}\n")

    assertions.assert_string_appearance(
        buffer=uploaded_logs,
        min_lines=30,
        expected=[
            f"Found {count} findings",
            "Control 'KICS' ended with status 'PASS'"
        ],
        unexpected=[
            "[404]",
            "[500]",
        ],
    )


# @pytest.mark.parametrize(
#     "count, framework",
#     [15, "terraform"],
#     indirect=["local_output_file_test_setup"],
#
# )
# def test_control__output_file(count, framework, local_output_file_test_setup):
#     """
#     Test that the findings are written to the output file when the output file is specified.\n
#     Currently, the output file is not used by the backend, but it is used by the IDE Extension.
#     """
#     container_findings_output_file_path = local_output_file_test_setup["container_findings_output_file_path"]
#     local_findings_output_file_path = local_output_file_test_setup["local_findings_output_file_path"]
#     output_directory = local_output_file_test_setup["output_directory"]
#
#     run_container(
#         image=f"{IMAGE_NAME}:{IMAGE_TAG}",
#         command=f"'{get_container_command(framework)}'",
#         environment={
#             "SECURITY_CONTROL_OUTPUT_FILE": "/code/jit-report/results.json",
#             "FINDINGS_OUTPUT_FILE_PATH": container_findings_output_file_path,
#         },
#         volumes={
#             output_directory: {
#                 "bind": "/tmp/output",
#                 "mode": "rw",
#             },
#             str(TEST_DATA_DIRECTORY / framework): {
#                 "bind": f"/code/{framework}",
#                 "mode": "rw",
#             }
#         },
#         platform="linux/amd64",
#         privileged=True,  # important for the instrumented image
#         network=get_docker_network_by_prefix('github_network_'),
#     )
#
#     with open(local_findings_output_file_path, 'r') as f:
#         findings = json.load(f)
#         assert len(findings) == count

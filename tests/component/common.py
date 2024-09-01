from typing import Dict

import boto3
from mypy_boto3_batch import BatchClient
from aws_lambda_typing.events import EventBridgeEvent
from mypy_boto3_batch.type_defs import ContainerPropertiesTypeDef

from jit_utils.aws_clients.config.aws_config import get_aws_config

from src.lib.constants import AWS_COMMON_BATCH_CLIENT_NAME


def wrap_eventbridge_event(
        payload: Dict,
        detail_type: str = "detail_type",
        source: str = "source",
) -> EventBridgeEvent:
    return {
        "version": "",
        "id": "",
        "detail-type": detail_type,
        "source": source,
        "account": "",
        "time": "",
        "region": "",
        "resources": [],
        "detail": payload,
    }


class NoEventBridgeWasSentError(Exception):
    def __init__(self):
        super().__init__()


_batch_client = None


def _get_batch_client() -> BatchClient:
    global _batch_client
    if not _batch_client:
        _batch_client = boto3.client(AWS_COMMON_BATCH_CLIENT_NAME, **get_aws_config())

    return _batch_client


def create_job_definition(job_definition_name: str):
    _get_batch_client().register_job_definition(
        jobDefinitionName=job_definition_name,
        type='container',
        platformCapabilities=['FARGATE'],
        containerProperties=ContainerPropertiesTypeDef(
            command=['echo', job_definition_name],
            image='alpine:3.15',
            vcpus=1,
            memory=10
        )
    )

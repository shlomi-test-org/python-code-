from typing import List

from aws_lambda_typing.events import SQSEvent

from src.lib.models.client_models import InternalSlackMessageBody
from src.lib.models.resource_models import ResourceInUse

MOCK_SQS_EVENT: SQSEvent = {
    "Records": [
        {
            "body": "{\"tenant_id\": \"f991908d-8a9f-469a-bd30-99df582ae3cb\", \"resource_type\": \"github_actions\", "
                    "\"jit_event_id\": \"01cfd764-8537-4b9e-84b2-e884cf86c223\", \"execution_id\": "
                    "\"6d5bf8fa-53a6-4694-8497-5e730d377935\", \"created_at\": \"2022-11-02T10:48:04.310491\", "
                    "\"channel_id\": \"jit-errors-bandit\", \"text\": \"hopa stopa\"}"
        },
        {
            "body": "{\"tenant_id\": \"f991908d-8a9f-469a-bd30-99df582ae3cb\", \"resource_type\": \"github_actions\", "
                    "\"jit_event_id\": \"01cfd764-8537-4b9e-84b2-e884cf86c223\", \"execution_id\": "
                    "\"6d5bf8fa-53a6-4694-8497-5e730d377935\", \"created_at\": \"2022-11-02T10:48:04.310491\", "
                    "\"channel_id\": \"jit-sade\", \"text\": \"grape grape\"}"
        }
    ]
}

MOCK_SQS_EVENT_INTERNAL_SLACK_MESSAGE: List[InternalSlackMessageBody] = [
    InternalSlackMessageBody(text="hopa stopa", channel_id="jit-errors-bandit"),
    InternalSlackMessageBody(text="grape grape", channel_id="jit-sade")
]

MOCK_RESOURCE_IN_USE: ResourceInUse = ResourceInUse(tenant_id='02210aae-e8c6-4986-88b3-2ddd8bdc17f8',
                                                    resource_type='ci',
                                                    jit_event_id='e2dd03d7-18dc-47d5-bc46-16388fe7d32d',
                                                    execution_id='e91dc75a-a69d-44e9-adf6-aa80d70ee31d',
                                                    created_at='2022-11-29T16:55:11.711435')

MOCK_INTERNAL_SLACK_MESSAGE_WITH_BLOCKS_RESOURCE: List[InternalSlackMessageBody] = [
    InternalSlackMessageBody(text='Resource expired',
                             channel_id='jit-resources-mgmt-local',
                             blocks=[{'type': 'header', 'text': {'type': 'plain_text', 'text': 'Resource expired'}},
                                     {'type': 'section',
                                      'text': {'type': 'mrkdwn',
                                               'text': 'tenant_id: 02210aae-e8c6-4986-88b3-2ddd8bdc17f8\n'
                                                       'resource_type: ci\n'
                                                       'jit_event_id: e2dd03d7-18dc-47d5-bc46-16388fe7d32d\n'
                                                       'execution_id: e91dc75a-a69d-44e9-adf6-aa80d70ee31d\n'
                                                       'created_at: 2022-11-29T16:55:11.711435'}},
                                     {'type': 'divider'}])
]

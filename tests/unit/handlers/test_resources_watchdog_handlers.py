from aws_lambda_typing.context import Context

import src.handlers.resources_watchdog
from src.handlers.resources_watchdog import free_resources_handler
from src.handlers.resources_watchdog import notify_free_resource_failed
from src.handlers.resources_watchdog import watchdog
from src.lib.constants import BATCH_ITEMS_FAILURE
from tests.mocks.execution_mocks import MOCK_EXECUTION
from tests.mocks.resources_mocks import generate_messages_from_resources_in_use
from tests.mocks.sqs_mocks import MOCK_SQS_EVENT


def test_resources_watchdog_handler(mocker):
    """
    Testing the resources_watchdog handler
    """
    mocked_find_resources_to_free_and_push_to_queue = mocker.patch.object(
        src.handlers.resources_watchdog,
        'find_executions_to_terminate_and_push_to_queue')
    watchdog({}, {})
    mocked_find_resources_to_free_and_push_to_queue.assert_called_once()


def test_free_resources_handler__all_succeeded(mocker):
    """
    Testing the free_resources handler
    """
    mocker.patch.object(src.handlers.resources_watchdog, 'terminate_execution_and_free_resources_core')
    mock_messages = generate_messages_from_resources_in_use([MOCK_EXECUTION])

    response = free_resources_handler({'Records': mock_messages}, {})

    assert response == {BATCH_ITEMS_FAILURE: []}


def test_notify_free_resource_failed(mocker):
    """
    Testing the notify_free_resource_failed handler
    """
    mock_forward_free_resource_failed_msg_to_notification_service = \
        mocker.patch.object(src.handlers.resources_watchdog, 'forward_free_resource_failed_msg_to_notification_service')
    notify_free_resource_failed(MOCK_SQS_EVENT, Context())
    mock_forward_free_resource_failed_msg_to_notification_service.assert_called_once()

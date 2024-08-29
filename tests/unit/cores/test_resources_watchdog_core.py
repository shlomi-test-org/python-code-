import json
from unittest.mock import MagicMock
from uuid import uuid4

import jit_utils.aws_clients.sqs
from jit_utils.models.execution import ExecutionError, ExecutionErrorType, ResourceType

import src.lib.cores.resources_watchdog_core
import src.lib.cores.utils.transactions
from src.lib.cores.resources_watchdog_core import find_executions_to_terminate_and_push_to_queue, \
    forward_about_expired_resource_to_notification_service, forward_free_resource_failed_msg_to_notification_service, \
    forward_slack_messages_to_notification_service_via_sqs, terminate_execution_and_free_resources_core
from src.lib.models.execution_models import ExecutionStatus, ExecutionWithVendorLogs
from tests.mocks.execution_mocks import MOCK_EXECUTION, generate_mock_executions
from tests.mocks.resources_mocks import generate_mock_resource_in_use
from tests.mocks.sqs_mocks import MOCK_SQS_EVENT, MOCK_SQS_EVENT_INTERNAL_SLACK_MESSAGE
from tests.unit.cores.utils.mock_runner import MockExecutionRunner


def test_find_resources_to_free_and_push_to_queue__no_resources_found(mocker):
    """
    Test that find_resources_to_free_and_push_to_queue returns 0 if no resources are found.
    Assert that get_resources_in_use_exceeded_time_limitation has been called.
    Assert that send_fifo_messages_batch hasn't been called.
    """
    mocked_get_executions_to_terminate = mocker.patch.object(
        src.lib.cores.resources_watchdog_core.ExecutionsManager,
        'get_executions_to_terminate',
        return_value=([], None),
    )
    mocked_send_fifo_messages_batch = mocker.patch.object(
        src.lib.cores.resources_watchdog_core.SQSClient,
        'send_fifo_messages_batch',
        return_value=None,
    )
    resources_to_free = find_executions_to_terminate_and_push_to_queue()
    assert resources_to_free == 0
    mocked_get_executions_to_terminate.assert_called_once()
    mocked_send_fifo_messages_batch.assert_not_called()


def test_find_resources_to_free_and_push_to_queue__resources_found(mocker):
    """
    Test that find_resources_to_free_and_push_to_queue returns the number of resources found.
    Assert that get_resources_in_use_exceeded_time_limitation has been called.
    Assert that send_fifo_messages_batch has been called.
    """
    mock_executions_to_cancel = [MOCK_EXECUTION] * 3
    mocked_get_executions_to_terminate = mocker.patch.object(
        src.lib.cores.resources_watchdog_core.ExecutionsManager,
        'get_executions_to_terminate',
        return_value=(mock_executions_to_cancel, None),
    )
    mocked_send_fifo_messages_batch = mocker.patch.object(
        src.lib.cores.resources_watchdog_core.SQSClient,
        'send_fifo_messages_batch',
        return_value=None,
    )

    resources_to_free = find_executions_to_terminate_and_push_to_queue()

    assert resources_to_free == len(mock_executions_to_cancel)
    mocked_get_executions_to_terminate.assert_called_once()
    assert mocked_send_fifo_messages_batch.call_count == 1


def test_free_resource_core__new_flow_succeeded(mocker):
    """
    Test that free_resource_core doesn't raise exception
    """
    tenant_id_new_flow = str(uuid4())
    mocked_execution_new_flow = generate_mock_executions(1, tenant_id_new_flow, status=ExecutionStatus.DISPATCHED)[0]
    mocked_execution_manager = MagicMock()
    mocker.patch.object(
        src.lib.cores.utils.transactions, "ExecutionsManager", return_value=mocked_execution_manager
    )
    mocked_send_execution_event = mocker.patch.object(
        src.lib.cores.resources_watchdog_core,
        'send_execution_event',
        return_value=None,
    )
    spy_generate_update_execution_query = mocker.spy(mocked_execution_manager, 'update_execution')
    spy_execute_transaction = mocker.spy(mocked_execution_manager, 'execute_transaction')

    mock_execution_runner = MockExecutionRunner()
    mocked_get_execution_runner_watchdog_core = mocker.patch(
        'src.lib.cores.resources_watchdog_core.get_execution_runner',
        return_value=mock_execution_runner,
    )
    mocked_get_execution_runner_execution_core = mocker.patch(
        'src.lib.cores.executions_core.get_execution_runner',
        return_value=mock_execution_runner,
    )
    mocked_forward_slack_notification = mocker.patch(
        'src.lib.cores.resources_watchdog_core.forward_about_expired_resource_to_notification_service'
    )

    failed_resources = terminate_execution_and_free_resources_core([mocked_execution_new_flow])
    assert failed_resources == []
    assert spy_generate_update_execution_query.call_count == 1
    assert spy_execute_transaction.call_count == 1
    assert mocked_send_execution_event.call_count == 1
    assert mocked_get_execution_runner_watchdog_core.call_count == 2
    assert mocked_get_execution_runner_execution_core.call_count == 1
    assert mock_execution_runner.call_count == 1
    assert mocked_forward_slack_notification.call_count == 1
    assert len(mocked_forward_slack_notification.call_args_list[0][0][0]) == 1
    assert mocked_forward_slack_notification.call_args_list[0][0][0][0].status == ExecutionStatus.DISPATCHED
    assert mocked_forward_slack_notification.call_args_list[0][0][0][0].vendor_logs_url == "logs_url"


def test_free_resource_core__failed(mocker):
    """
    Test that free_resource_core raises exception
    """
    mock_resource_in_use = generate_mock_resource_in_use(str(uuid4()), ResourceType.CI, 1)[0]
    generate_mock_executions(1, str(uuid4()))[0]
    mocked_execution_manager = MagicMock()

    def raise_exception(*args, **kwargs):
        raise Exception("Error")

    mocker.patch.object(
        src.lib.cores.utils.transactions, "ExecutionsManager", return_value=mocked_execution_manager
    )
    mocker.patch.object(
        src.lib.cores.utils.transactions,
        'generate_free_resource_queries',
        return_value=[]
    )
    mocked_forward_slack_notification = mocker.patch(
        'src.lib.cores.resources_watchdog_core.forward_about_expired_resource_to_notification_service'
    )
    mocked_execution_manager.execute_transaction = raise_exception

    failed_resources = terminate_execution_and_free_resources_core([mock_resource_in_use])
    assert failed_resources == [mock_resource_in_use]
    assert mocked_execution_manager.update_execution.call_count == 0
    assert mocked_forward_slack_notification.call_count == 1


def test_forward_free_resource_failed_msg_to_notification_service(mocker):
    """
    Test that forward_free_resource_failed_msg_to_notification_service sends the correct formatted messages
    """
    mock_forward_sqs_messages_to_notification_service = mocker.patch.object(
        src.lib.cores.resources_watchdog_core,
        'forward_slack_messages_to_notification_service_via_sqs'
    )

    forward_free_resource_failed_msg_to_notification_service(MOCK_SQS_EVENT['Records'])
    assert mock_forward_sqs_messages_to_notification_service.call_count == 1

    passed_messages = mock_forward_sqs_messages_to_notification_service.call_args.kwargs['messages']
    assert len(passed_messages) == 2
    assert passed_messages[0].text == f"Resource {MOCK_SQS_EVENT['Records'][0]['body']} could not be freed"


def test_forward_sqs_messages_to_notification_service(mocker):
    """
    Test that forward_sqs_messages_to_notification_service calls send_message
    """
    mocked_send_message = mocker.patch.object(jit_utils.aws_clients.sqs.SQSClient, 'send_message')
    forward_slack_messages_to_notification_service_via_sqs(MOCK_SQS_EVENT_INTERNAL_SLACK_MESSAGE)
    assert mocked_send_message.call_count == 2


def test_forward_about_expired_resource_to_notification_service__execution(mocker):
    """
    Test that forward_about_expired_resource_to_notification_service sends the correct formatted messages for execution
    """
    mock_forward_sqs_messages_to_notification_service = mocker.patch.object(
        src.lib.cores.resources_watchdog_core,
        'forward_slack_messages_to_notification_service_via_sqs')
    forward_about_expired_resource_to_notification_service([ExecutionWithVendorLogs(**MOCK_EXECUTION.dict())])
    assert mock_forward_sqs_messages_to_notification_service.call_count == 1
    assert mock_forward_sqs_messages_to_notification_service.call_args.kwargs['messages'][0].text == 'Resource expired'


def test_forward_about_expired_resource_to_notification_service__user_errors(mocker):
    """
    Test that forward_about_expired_resource_to_notification_service sends the correct formatted messages for execution
    """
    mock_forward_sqs_messages_to_notification_service = mocker.patch.object(
        src.lib.cores.resources_watchdog_core,
        'forward_slack_messages_to_notification_service_via_sqs')

    execution_with_old_format_error = ExecutionWithVendorLogs(**MOCK_EXECUTION.dict())
    execution_with_old_format_error.error_body = (
        "{\"tenant_id\": \"2c461cd3-65e0-4842-bff4-eab068e93f7a\","
        " \"run_id\": null,"
        " \"reason\": \"bad_user_configurations\","
        " \"error_body\": \"Actions are not active for repo=\'dude\'\"}"
    )

    new_execution = ExecutionWithVendorLogs(**MOCK_EXECUTION.dict())
    new_format_error_body = ExecutionError(
        error_body="Actions are not active for repo='repo2'",
        error_type=ExecutionErrorType.USER_INPUT_ERROR
    )
    new_execution.errors = [new_format_error_body]

    forward_about_expired_resource_to_notification_service([
        execution_with_old_format_error,
        new_execution,
    ])
    assert mock_forward_sqs_messages_to_notification_service.call_count == 1
    blocks = mock_forward_sqs_messages_to_notification_service.call_args.kwargs['messages'][0].blocks
    assert json.loads(execution_with_old_format_error.error_body)["error_body"] in repr(blocks)
    assert new_format_error_body.error_body in repr(blocks)


def test_forward_about_expired_resource_to_notification_service__no_executions(mocker):
    """
    Test that forward_about_expired_resource_to_notification_service sends the correct formatted messages for execution
    """
    mock_forward_sqs_messages_to_notification_service = mocker.patch.object(
        src.lib.cores.resources_watchdog_core,
        'forward_slack_messages_to_notification_service_via_sqs')

    forward_about_expired_resource_to_notification_service([])
    assert mock_forward_sqs_messages_to_notification_service.call_count == 0

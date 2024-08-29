import json
import ulid
from jit_utils.aws_clients.events import EventBridgeClient
from jit_utils.models.findings.entities import Finding

from src.lib.findings_utils import send_findings_batch_notification, FindingsInnerUseCase, FindingsNotificationType
from tests.fixtures import build_finding_dict


def test_send_findings_notification_more_than_one_batch(mocker):
    send_event_mock = mocker.patch.object(EventBridgeClient, 'put_events')

    findings = [Finding(**build_finding_dict()) for _ in range(0, 300)]
    send_findings_batch_notification(
        "tenant_id", findings, FindingsNotificationType.FINDINGS_CREATED, FindingsInnerUseCase.UPLOAD_FINDINGS, True
    )

    assert len(send_event_mock.call_args_list) == 12
    assert json.loads(send_event_mock.call_args_list[0].args[3][0])["findings"] == findings[0:25]
    assert json.loads(send_event_mock.call_args_list[0].args[3][0])["batch_number"] == 1
    assert json.loads(send_event_mock.call_args_list[1].args[3][0])["findings"] == findings[25:50]
    assert json.loads(send_event_mock.call_args_list[1].args[3][0])["batch_number"] == 2
    assert json.loads(send_event_mock.call_args_list[11].args[3][0])["findings"] == findings[275:]
    assert json.loads(send_event_mock.call_args_list[11].args[3][0])["batch_number"] == 12
    assert json.loads(send_event_mock.call_args_list[0].args[3][0])["total_batches"] == 12
    ulid.parse(json.loads(send_event_mock.call_args_list[0].args[3][0])["event_id"])


def test_send_findings_notification_one_batch(mocker):
    send_event_mock = mocker.patch.object(EventBridgeClient, 'put_events')

    findings = [Finding(**build_finding_dict()) for _ in range(0, 25)]
    send_findings_batch_notification(
        "tenant_id", findings, FindingsNotificationType.FINDINGS_CREATED, FindingsInnerUseCase.UPLOAD_FINDINGS, True
    )

    assert len(send_event_mock.call_args_list) == 1
    assert json.loads(send_event_mock.call_args_list[0].args[3][0])["findings"] == findings
    ulid.parse(json.loads(send_event_mock.call_args_list[0].args[3][0])["event_id"])


def test_send_findings_notification_no_finding_should_not_call_eventbridge(mocker):
    send_event_mock = mocker.patch.object(EventBridgeClient, 'put_events')

    findings = []
    send_findings_batch_notification(
        "tenant_id", findings, FindingsNotificationType.FINDINGS_CREATED, FindingsInnerUseCase.UPLOAD_FINDINGS, True
    )

    assert len(send_event_mock.call_args_list) == 0

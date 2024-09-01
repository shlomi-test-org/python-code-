import copy
import json

import boto3
import pytest
from freezegun import freeze_time
from jit_utils.models.execution_context import Runner
from jit_utils.models.controls import ControlType

from moto import mock_events
from moto import mock_sqs
from moto.ecs import mock_ecs
from pydantic.error_wrappers import ValidationError

import src.handlers.handle_fargate_jobs_finished
import src.lib.clients.eventbridge
import src.lib.cores.fargate.fargate_core
from src.handlers.handle_fargate_jobs_finished import _make_labels
from src.handlers.handle_fargate_jobs_finished import handle_batch_jobs_failure
from src.handlers.handle_fargate_jobs_finished import handle_ecs_jobs_completion
from src.lib.aws_common import get_prices
from src.lib.constants import EXECUTION_EVENT_BUS_NAME
from src.lib.cores.execution_runner.cloud_execution_runners.aws_execution_runner import AwsExecutionRunner
from src.lib.exceptions import EventMissingStartOrFinish
from jit_utils.models.execution import Execution
from tests.component.common import NoEventBridgeWasSentError
from tests.mocks.batch_job_event_mock import MOCK_BATCH_FAILURE_EVENT
from tests.mocks.batch_job_event_mock import MOCK_ECS_EVENT
from tests.mocks.batch_job_event_mock import MOCK_ECS_EVENT_FAILED_TO_START
from tests.mocks.batch_job_event_mock import MOCK_ECS_EVENT_TWO_CONTAINERS
from tests.mocks.batch_job_event_mock import MOCK_NON_JIT_EVENT
from tests.mocks.batch_job_event_mock import MOCK_PRICING_RESULT
from tests.mocks.batch_job_event_mock import MOCK_WINDOWS_CONTAINER
from tests.mocks.batch_job_event_mock import TASK_DEFINITION_MOCK


def __get_mock_queue_attributes():
    """
    The mock queue listens to eventbridge notifications
    """
    sqs_client = boto3.client("sqs", region_name="us-east-1")
    res = sqs_client.get_queue_url(QueueName="events")
    attr_res = sqs_client.get_queue_attributes(
        QueueUrl=res["QueueUrl"], AttributeNames=["All"]
    )
    return res["QueueUrl"], attr_res["Attributes"]["QueueArn"]  # url, arn


def __delete_keys_from_dict(dictionary, keys_to_remove):
    """
    Delete the keys present in lst_keys from the dictionary.
    Loops recursively over nested dictionaries.
    """
    if not isinstance(dictionary, dict):
        return
    for key in keys_to_remove:
        if key in dictionary:
            del dictionary[key]

    for value in dictionary.values():
        if isinstance(value, dict):
            __delete_keys_from_dict(value, keys_to_remove)
        if isinstance(value, list):
            for val in value:
                __delete_keys_from_dict(val, keys_to_remove)

    return dictionary


def __get_notification_msg():
    """
    Gets the event that was omitted from queue
    """
    url, _ = __get_mock_queue_attributes()

    sqs = boto3.resource("sqs", region_name="us-east-1")
    queue = sqs.Queue(url)

    msgs = queue.receive_messages()
    if len(msgs) == 0:
        raise NoEventBridgeWasSentError()

    res = json.loads(msgs[0].body)
    res.pop("id")
    return res


@pytest.fixture()
def prepare_eventbridge(mocker):
    """
    Clears expensive methods, and prepares subscription to execution service
    """
    mocker.patch(
        "src.lib.clients.eventbridge.get_aws_config",
        return_value={"region_name": "us-east-1"},
    )
    get_prices.cache_clear()

    with mock_events(), mock_sqs():
        sqs_client = boto3.client("sqs", region_name="us-east-1")
        sqs_client.create_queue(QueueName="events")
        _, q_arn = __get_mock_queue_attributes()

        client = boto3.client("events", "us-east-1")

        client.create_event_bus(Name=EXECUTION_EVENT_BUS_NAME)
        client.put_rule(
            Name="to-sqs",
            EventBusName=EXECUTION_EVENT_BUS_NAME,
            EventPattern='{"source": ["execution-service"]}',
        )
        client.put_targets(
            EventBusName=EXECUTION_EVENT_BUS_NAME,
            Rule="to-sqs",
            Targets=[{"Id": "eventsid", "Arn": q_arn}],
        )
        yield


@pytest.fixture()
def create_task_env_vars_fixture():

    # The reason for this fixture is to identify if we do internal changes in the event.
    execution = Execution(
        plan_item_slug="test",
        workflow_slug="test2",
        job_name="teset3",
        control_image="test4",
        jit_event_name="test5",
        created_at="test6",
        control_type=ControlType.DETECTION,
        job_runner=Runner.JIT,
        plan_slug="test7",
        asset_id="test9",
        tenant_id="46db21b6-fb2a-4c5d-9148-37d2248a7c20",
        execution_id="9b3d5825-f9ab-4a2b-bc46-aec569bd201d",
        jit_event_id="7bc127f0-9674-4072-81a3-85c5b107b555",
    )

    env_vars, _ = AwsExecutionRunner._setup_for_execution(execution, "some-callback_token")
    env_vars_ecs_task_list = []
    for var in env_vars:
        env_vars_ecs_task_list.append({"name": var, "value": env_vars[var]})
    yield env_vars_ecs_task_list


def test_make_labels():
    job_definition, job_link, logs_link = _make_labels(
        MOCK_BATCH_FAILURE_EVENT["detail"]
    )
    assert job_definition == "web-app-scanner"
    assert job_link == (
        "https://console.aws.amazon.com/batch/home?#jobs/fargate/detail/a7c17e65-6eb9-4d5c-ad20-90ae910f6660"
    )
    assert logs_link == (
        "https://console.aws.amazon.com/cloudwatch/home?#logsV2:log-groups"
        "/log-group/$252Fecs$252Fweb-app-scanner-container/log-events"
        "/ecs$252Fdefault$252F332089cce2794bfeb27186563687041f"
    )


def test_handle_batch_jobs_failures(mocker, create_task_env_vars_fixture):
    """
    Testing the handle_batch_jobs_failures handler
    """
    mocked_send_task_completion_event = mocker.patch.object(
        src.handlers.handle_fargate_jobs_finished,
        "send_task_completion_event",
        return_value=None,
    )
    mock_alert = mocker.patch("src.handlers.handle_fargate_jobs_finished.alert")
    event = copy.deepcopy(MOCK_BATCH_FAILURE_EVENT)
    event["detail"]["container"]["environment"] = create_task_env_vars_fixture
    handle_batch_jobs_failure(event, {})
    mocked_send_task_completion_event.assert_called_once()
    mock_alert.assert_called_with(
        alert_type='Execution Batch Job Failed',
        message="Batch job failed. See tags for more info.",
    )


@freeze_time("2022-01-14")
@pytest.mark.parametrize(
    "ephemeral_storage,expected_price",
    [
        (0.0, 0.00048550000000000004),
        (10.0, 0.00048550000000000004),
        (20.0, 0.00048550000000000004),
        (30.0, 0.0015955000000000001),
    ],
)
def test_calculate_ecs_price(
    mocker,
    create_task_env_vars_fixture,
    prepare_eventbridge,
    ephemeral_storage,
    expected_price,
):
    """
    Testing a regular ECS price calculation with various storage sizes (up to 20 GB is free - thus same price)
    """
    # mocker.patch.object(FargateHandler, "_get_prices", return_value=MOCK_PRICING_RESULT)
    mocker.patch(
        "src.lib.cores.fargate.fargate_core.get_prices",
        return_value=MOCK_PRICING_RESULT,
    )
    mocker.patch(
        "src.lib.cores.fargate.fargate_core.get_task_definition",
        return_value=TASK_DEFINITION_MOCK,
    )

    event = copy.deepcopy(MOCK_ECS_EVENT)
    event["detail"]["ephemeralStorage"]["sizeInGiB"] = ephemeral_storage
    event["detail"]["overrides"]["containerOverrides"][0][
        "environment"
    ] = create_task_env_vars_fixture
    handle_ecs_jobs_completion(event, {})
    response = __get_notification_msg()
    assert response == {
        "version": "0",
        "detail-type": "fargate-task-finished",
        "source": "execution-service",
        "account": "123456789012",
        "time": "2022-01-14T00:00:00Z",
        "region": "us-east-1",
        "resources": [],
        "detail": {
            "metadata": {
                "tenant_id": "46db21b6-fb2a-4c5d-9148-37d2248a7c20",
                "event_id": "7bc127f0-9674-4072-81a3-85c5b107b555",
                "execution_id": "9b3d5825-f9ab-4a2b-bc46-aec569bd201d",
                "container_image": "121169888995.dkr.ecr.us-east-1.amazonaws.com/prowler:latest",
                "image_digest": "sha256:f1279d66c3547e70c738376225adf59cd9b1b5f899841d07ce64c7fc83d8779a",
            },
            "data": {
                "cpu_architecture": "x86_64",
                "start_time": "2022-11-23T16:36:31.210000",
                "event_time": "2022-11-23T16:37:19.295000",
                "duration_seconds": 49,
                "billable_duration_minutes": 1.0,
                "vcpu": 0.5,
                "memory_gb": 2.0,
                "storage_gb": ephemeral_storage,
                "billable_storage_gb": float(max(0, ephemeral_storage - 20)),
                "is_linux": True,
                "exit_code": 0,
                "price_dollars": expected_price,
            },
        },
    }


@freeze_time("2022-01-14")
def test_calculate_ecs_price_missing_pricing_data(
    mocker, prepare_eventbridge, create_task_env_vars_fixture
):
    """
    Testing a regular ECS price, but AWS pricing API doesn't return all relevant prices,
    This means - we'll use some default parameters and write warning about it, so the prices will still be calculated
    but with default prices (correct for 30.11.22) - PRICING_DEFAULTS dictionary
    """
    # mocker.patch.object(FargateHandler, "_get_prices", return_value=MOCK_PRICING_RESULT)
    pricing_res = copy.deepcopy(MOCK_PRICING_RESULT)
    pricing_res["PriceList"][0] = pricing_res["PriceList"][0].replace(
        "7KPDPTDSCT4J3Z64", "XXX1"
    )  # storage
    pricing_res["PriceList"][1] = pricing_res["PriceList"][0].replace(
        "8CESGAFWKAJ98PME", "XXX2"
    )  # linux x86 CPU

    mocker.patch(
        "src.lib.cores.fargate.fargate_core.get_prices", return_value=pricing_res
    )
    mocker.patch(
        "src.lib.cores.fargate.fargate_core.get_task_definition",
        return_value=TASK_DEFINITION_MOCK,
    )

    event = copy.deepcopy(MOCK_ECS_EVENT)
    event["detail"]["overrides"]["containerOverrides"][0][
        "environment"
    ] = create_task_env_vars_fixture
    handle_ecs_jobs_completion(event, {})
    response = __get_notification_msg()
    assert response == {
        "version": "0",
        "detail-type": "fargate-task-finished",
        "source": "execution-service",
        "account": "123456789012",
        "time": "2022-01-14T00:00:00Z",
        "region": "us-east-1",
        "resources": [],
        "detail": {
            "metadata": {
                "tenant_id": "46db21b6-fb2a-4c5d-9148-37d2248a7c20",
                "event_id": "7bc127f0-9674-4072-81a3-85c5b107b555",
                "execution_id": "9b3d5825-f9ab-4a2b-bc46-aec569bd201d",
                "container_image": "121169888995.dkr.ecr.us-east-1.amazonaws.com/prowler:latest",
                "image_digest": "sha256:f1279d66c3547e70c738376225adf59cd9b1b5f899841d07ce64c7fc83d8779a",
            },
            "data": {
                "cpu_architecture": "x86_64",
                "start_time": "2022-11-23T16:36:31.210000",
                "event_time": "2022-11-23T16:37:19.295000",
                "duration_seconds": 49,
                "billable_duration_minutes": 1.0,
                "vcpu": 0.5,
                "memory_gb": 2.0,
                "storage_gb": 30.0,
                "billable_storage_gb": 10.0,
                "is_linux": True,
                "exit_code": 0,
                "price_dollars": 0.0015955000000000001,
            },
        },
    }


@freeze_time("2022-01-14")
@pytest.mark.parametrize(
    "ephemeral_storage,expected_price",
    [
        (0.0, 0.00038849999999999996),
        (10.0, 0.00038849999999999996),
        (20.0, 0.00038849999999999996),
        (30.0, 0.0014985),
    ],
)
def test_calculate_ecs_ARM_price(
    mocker,
    prepare_eventbridge,
    ephemeral_storage,
    expected_price,
    create_task_env_vars_fixture,
):
    """
    Testing a ARM cpu ECS price calculation (cheaper) with various storage sizes
    """
    mocker.patch(
        "src.lib.cores.fargate.fargate_core.get_prices",
        return_value=MOCK_PRICING_RESULT,
    )
    mocker.patch(
        "src.lib.cores.fargate.fargate_core.get_task_definition",
        return_value=TASK_DEFINITION_MOCK,
    )

    event = copy.deepcopy(MOCK_ECS_EVENT)
    event["detail"]["overrides"]["containerOverrides"][0][
        "environment"
    ] = create_task_env_vars_fixture
    event["detail"]["attributes"][0]["value"] = "arm64"
    event["detail"]["ephemeralStorage"]["sizeInGiB"] = ephemeral_storage
    handle_ecs_jobs_completion(event, {})
    response = __get_notification_msg()
    assert response["detail"] == {
        "metadata": {
            "tenant_id": "46db21b6-fb2a-4c5d-9148-37d2248a7c20",
            "event_id": "7bc127f0-9674-4072-81a3-85c5b107b555",
            "execution_id": "9b3d5825-f9ab-4a2b-bc46-aec569bd201d",
            "container_image": "121169888995.dkr.ecr.us-east-1.amazonaws.com/prowler:latest",
            "image_digest": "sha256:f1279d66c3547e70c738376225adf59cd9b1b5f899841d07ce64c7fc83d8779a",
        },
        "data": {
            "cpu_architecture": "arm64",
            "start_time": "2022-11-23T16:36:31.210000",
            "event_time": "2022-11-23T16:37:19.295000",
            "duration_seconds": 49,
            "billable_duration_minutes": 1.0,
            "vcpu": 0.5,
            "memory_gb": 2.0,
            "storage_gb": ephemeral_storage,
            "billable_storage_gb": float(max(0, ephemeral_storage - 20)),
            "is_linux": True,
            "exit_code": 0,
            "price_dollars": expected_price,
        },
    }


@freeze_time("2022-01-14")
@pytest.mark.parametrize(
    "ephemeral_storage,expected_price",
    [(0.0, 0.0419075), (10.0, 0.0419075), (20.0, 0.0419075), (30.0, 0.0430175)],
)
def test_calculate_windows_container(
    mocker,
    prepare_eventbridge,
    ephemeral_storage,
    expected_price,
    create_task_env_vars_fixture,
):
    """
    Testing windows container - it misses a container sha,
    also - has various storage sizes
    """
    mocker.patch(
        "src.lib.cores.fargate.fargate_core.get_prices",
        return_value=MOCK_PRICING_RESULT,
    )
    mocker.patch(
        "src.lib.cores.fargate.fargate_core.get_task_definition",
        return_value=TASK_DEFINITION_MOCK,
    )

    event = copy.deepcopy(MOCK_WINDOWS_CONTAINER)
    event["detail"]["overrides"]["containerOverrides"][0][
        "environment"
    ] = create_task_env_vars_fixture
    event["detail"]["ephemeralStorage"]["sizeInGiB"] = ephemeral_storage
    handle_ecs_jobs_completion(event, {})
    response = __get_notification_msg()
    assert response["detail"] == {
        "metadata": {
            "tenant_id": "46db21b6-fb2a-4c5d-9148-37d2248a7c20",
            "event_id": "7bc127f0-9674-4072-81a3-85c5b107b555",
            "execution_id": "9b3d5825-f9ab-4a2b-bc46-aec569bd201d",
            "container_image": "mcr.microsoft.com/windows/nanoserver:ltsc2019",
            "image_digest": None,
        },
        "data": {
            "cpu_architecture": "x86_64",
            "start_time": "2022-11-29T09:34:31.210000",
            "event_time": "2022-11-29T09:37:31",
            "duration_seconds": 180,
            "billable_duration_minutes": 15.0,
            "vcpu": 1.0,
            "memory_gb": 3.0,
            "storage_gb": ephemeral_storage,
            "billable_storage_gb": float(max(0, ephemeral_storage - 20)),
            "is_linux": False,
            "exit_code": 0,
            "price_dollars": expected_price,
        },
    }


def test_non_jit_ecs_event(mocker, create_task_env_vars_fixture, prepare_eventbridge):
    """
    Event that did not contain relevant env variable arrived, this is not a jit execution event
    """
    mocker.patch(
        "src.lib.cores.fargate.fargate_core.get_prices",
        return_value=MOCK_PRICING_RESULT,
    )
    mocker.patch(
        "src.lib.cores.fargate.fargate_core.get_task_definition",
        return_value=TASK_DEFINITION_MOCK,
    )

    handle_ecs_jobs_completion(MOCK_NON_JIT_EVENT, {})
    with pytest.raises(NoEventBridgeWasSentError):
        __get_notification_msg()


@pytest.mark.parametrize(
    "missing_property",
    [
        "cpu",
        "memory",
        "attributes",  # cpu-architecture
        "region",
    ],
)
def test_invalid_ecs_event(
    mocker, create_task_env_vars_fixture, prepare_eventbridge, missing_property
):
    """
    several missing parameters from the event, it shouldn't happen in real ECS event,
    but handled this case anyway
    """
    mocker.patch(
        "src.lib.cores.fargate.fargate_core.get_task_definition",
        return_value=TASK_DEFINITION_MOCK,
    )

    event = copy.deepcopy(MOCK_ECS_EVENT)
    event["detail"]["overrides"]["containerOverrides"][0][
        "environment"
    ] = create_task_env_vars_fixture
    event = __delete_keys_from_dict(event, [missing_property])

    with pytest.raises(ValidationError):
        handle_ecs_jobs_completion(event, {})


@pytest.mark.parametrize(
    "missing_property",
    [
        "pullStartedAt",
        "stoppedAt",
    ],
)
def test_event_without_start_end_time(
    mocker, create_task_env_vars_fixture, prepare_eventbridge, missing_property
):
    """
    2 mandatory parameters that if not exist the event not relevant (as cant calculate price)
    """

    def raise_ecs_error(arn):
        client = boto3.client("ecs", region_name="us-east-1")
        raise client.exceptions.ClientException(
            error_response={"message": "msg"}, operation_name="b"
        )

    mocker.patch(
        "src.lib.cores.fargate.fargate_core.get_prices",
        return_value=MOCK_PRICING_RESULT,
    )
    mocker.patch(
        "src.lib.cores.fargate.fargate_core.get_task_definition",
        side_effect=raise_ecs_error,
    )

    event = copy.deepcopy(MOCK_ECS_EVENT)
    event["detail"]["overrides"]["containerOverrides"][0][
        "environment"
    ] = create_task_env_vars_fixture
    event = __delete_keys_from_dict(event, [missing_property])

    with pytest.raises(EventMissingStartOrFinish):
        handle_ecs_jobs_completion(event, {})


def test_event_container_didnt_start_should_not_raise_error(
    mocker, prepare_eventbridge, create_task_env_vars_fixture
):
    """
    real event with missing pull start time
    """

    def raise_ecs_error(arn):
        client = boto3.client("ecs", region_name="us-east-1")
        raise client.exceptions.ClientException(
            error_response={"message": "msg"}, operation_name="b"
        )

    mocker.patch(
        "src.lib.cores.fargate.fargate_core.get_prices",
        return_value=MOCK_PRICING_RESULT,
    )
    mocker.patch(
        "src.lib.cores.fargate.fargate_core.get_task_definition",
        side_effect=raise_ecs_error,
    )

    event = copy.deepcopy(MOCK_ECS_EVENT_FAILED_TO_START)
    event["detail"]["overrides"]["containerOverrides"][0][
        "environment"
    ] = create_task_env_vars_fixture
    with pytest.raises(EventMissingStartOrFinish):
        handle_ecs_jobs_completion(event, {})


@mock_ecs
def test_task_doesnt_contain_task_definition(
    mocker, prepare_eventbridge, create_task_env_vars_fixture
):
    """
    Happens in the rare case where task finished, but someone deleted the task definition.
    In this case, we will use the first container defined in the ECS event to take the
    image + imageDigest, but it can't guarantee it's the essential (main) one.
    """

    def raise_ecs_error(arn):
        client = boto3.client("ecs", region_name="us-east-1")
        raise client.exceptions.ClientException(
            error_response={"message": "msg"}, operation_name="b"
        )

    mocker.patch(
        "src.lib.cores.fargate.fargate_core.get_prices",
        return_value=MOCK_PRICING_RESULT,
    )
    mocker.patch(
        "src.lib.cores.fargate.fargate_core.get_task_definition",
        side_effect=raise_ecs_error,
    )

    event = copy.deepcopy(MOCK_ECS_EVENT_TWO_CONTAINERS)
    event["detail"]["overrides"]["containerOverrides"][0][
        "environment"
    ] = create_task_env_vars_fixture
    handle_ecs_jobs_completion(event, {})
    response = __get_notification_msg()
    assert response["detail"]["data"]["exit_code"] == 999
    assert response["detail"]["metadata"]["container_image"] == "first"
    assert response["detail"]["metadata"]["image_digest"] == "12345"


def test_unsupported_CPU_architecture(mocker, prepare_eventbridge):
    """
    Invalid cpu-architecture for task (not arm or x86) - this cannot happen but we'll treat it as bad request.
    """

    mocker.patch(
        "src.lib.cores.fargate.fargate_core.get_prices",
        return_value=MOCK_PRICING_RESULT,
    )
    mocker.patch(
        "src.lib.cores.fargate.fargate_core.get_task_definition",
        return_value=TASK_DEFINITION_MOCK,
    )

    event = copy.deepcopy(MOCK_ECS_EVENT)
    event["detail"]["attributes"][0]["value"] = "unknown"

    handle_ecs_jobs_completion(event, {})
    with pytest.raises(NoEventBridgeWasSentError):
        __get_notification_msg()

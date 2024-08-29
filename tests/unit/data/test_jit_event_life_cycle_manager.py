import freezegun
import pytest
from unittest.mock import MagicMock
from botocore.exceptions import ClientError
from jit_utils.jit_event_names import JitEventName

from src.lib.data.jit_event_life_cycle_table import JitEventLifeCycleManager
from jit_utils.models.trigger.jit_event_life_cycle import JitEventStatus
from src.lib.models.jit_event_life_cycle import JitEventDBEntity
from src.lib.exceptions import JitEventLifeCycleDBEntityNotFoundException
from tests.common import CodeRelatedJitEventFactory
from tests.component.utils.mocks.mocks import TEST_TENANT_ID, ASSET_GITHUB_REPO_1


@pytest.fixture()
def jit_event_mock():
    return CodeRelatedJitEventFactory.build(
        tenant_id=TEST_TENANT_ID,
        asset_id=ASSET_GITHUB_REPO_1.asset_id,
        jit_event_name=JitEventName.PullRequestCreated,
    )


def test_put_jit_event_creates_new_event(jit_event_mock):
    # Arrange
    manager = JitEventLifeCycleManager()
    manager.table = MagicMock()

    # Act
    manager.put_jit_event(jit_event_mock, JitEventStatus.STARTED)

    # Assert
    manager.table.put_item.assert_called_once()


def test_put_jit_event_handles_dynamodb_exception(jit_event_mock):
    # Arrange
    manager = JitEventLifeCycleManager()
    manager.table = MagicMock()
    manager.table.put_item.side_effect = ClientError(
        {"Error": {"Code": "TestException", "Message": "Test exception"}}, "put_item")

    # Act and Assert
    with pytest.raises(ClientError):
        manager.put_jit_event(jit_event_mock, JitEventStatus.STARTED)


def test_get_jit_event_returns_existing_event(jit_event_mock):
    # Arrange
    manager = JitEventLifeCycleManager()
    manager.table = MagicMock()
    manager.table.get_item.return_value = {
        'Item': {
            'tenant_id': 'test_tenant',
            'jit_event_id': 'test_event',
            'jit_event_name': 'pull_request_created',
            'plan_item_slugs': ['test_plan_item_slug'],
            'status': 'creating',
        }
    }

    # Act
    result = manager.get_jit_event('test_tenant', 'test_event')

    # Assert
    assert isinstance(result, JitEventDBEntity)
    assert result.tenant_id == 'test_tenant'
    assert result.jit_event_id == 'test_event'
    assert result.status == JitEventStatus.CREATING


def test_get_jit_event_raises_exception_for_non_existing_event():
    # Arrange
    manager = JitEventLifeCycleManager()
    manager.table = MagicMock()
    manager.table.get_item.return_value = {}

    # Act and Assert
    with pytest.raises(JitEventLifeCycleDBEntityNotFoundException):
        manager.get_jit_event('test_tenant', 'test_event')


@freezegun.freeze_time("2021-01-01 00:00:00")
def test_updates_total_assets_for_existing_jit_event():
    # Arrange
    manager = JitEventLifeCycleManager()
    manager.table = MagicMock()
    manager.table.update_item.return_value = {
        'Attributes': {
            'tenant_id': 'test_tenant',
            'jit_event_id': 'test_event',
            'jit_event_name': 'pull_request_created',
            'plan_item_slugs': ['test_plan_item_slug'],
            'status': 'creating',
        }
    }

    # Act
    manager.update_jit_event_assets_count('test_tenant', 'test_event', 100)

    # Assert
    manager.table.update_item.assert_called_once_with(
        Key={'PK': manager.get_key(tenant='test_tenant'), 'SK': manager.get_key(jit_event='test_event')},
        AttributeUpdates={
            'total_assets': {'Value': 100, 'Action': 'PUT'},
            'remaining_assets': {'Value': 100, 'Action': 'PUT'},
            'modified_at': {'Value': '2021-01-01T00:00:00', 'Action': 'PUT'},

        },
        ReturnValues='ALL_NEW',
    )


def test_raises_exception_when_updating_total_assets_for_non_existing_jit_event():
    # Arrange
    manager = JitEventLifeCycleManager()
    manager.table = MagicMock()
    manager.table.update_item.side_effect = ClientError(
        {"Error": {"Code": "TestException", "Message": "Test exception"}},
        "update_item")

    # Act and Assert
    with pytest.raises(ClientError):
        manager.update_jit_event_assets_count('test_tenant', 'test_event', 100)


def test_creates_new_jit_event_asset():
    # Arrange
    manager = JitEventLifeCycleManager()
    manager.table = MagicMock()

    # Act
    manager.create_jit_event_asset('test_tenant', 'test_event', 'test_asset', 10)

    # Assert
    manager.table.put_item.assert_called_once()


def test_create_jit_event_asset_handles_duplicate_gracefully():
    # Arrange
    manager = JitEventLifeCycleManager()
    manager.table = MagicMock()

    # Create a mock exception that mimics the structure of ConditionalCheckFailedException
    error_response = {'Error': {'Code': 'ConditionalCheckFailedException', 'Message': 'Condition check failed'}}
    exception = ClientError(error_response, 'put_item')

    # Set the side effect of put_item to raise our mock exception
    manager.table.put_item.side_effect = exception

    # Act and Assert
    manager.create_jit_event_asset('test_tenant', 'test_event', 'test_asset', 10)

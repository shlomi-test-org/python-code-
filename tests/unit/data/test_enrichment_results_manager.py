from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from botocore.exceptions import ClientError
from freezegun import freeze_time
from jit_utils.jit_event_names import JitEventName

from src.lib.data.enrichment_results_db_models import EnrichmentResultsItemNotFoundError
from src.lib.data.enrichment_results_table import EnrichmentResultsManager
from src.lib.models.enrichment_results import BaseEnrichmentResultsItem

# Constants
TENANT_ID = str(uuid4())
VENDOR = "github"
OWNER = "some-owner"
REPO = "some-repo"
MOCK_ENRICHED_DATA = {"languages": ["python"], "frameworks": ["flask"]}
JIT_EVENT_ID = str(uuid4())
FIXED_TIMESTAMP = "2021-01-01T00:00:00"
MOCK_EXCEPTION_TEXT = "Test exception"


@pytest.fixture
def create_results_params():
    return BaseEnrichmentResultsItem(
        tenant_id=TENANT_ID,
        vendor=VENDOR,
        owner=OWNER,
        repo=REPO,
        enrichment_results=MOCK_ENRICHED_DATA,
        jit_event_id=JIT_EVENT_ID,
        jit_event_name=JitEventName.MergeDefaultBranch,
    )


@pytest.fixture
def enrichment_results_manager():
    manager = EnrichmentResultsManager()
    manager.table = MagicMock()
    return manager


@freeze_time(FIXED_TIMESTAMP)
def test_create_results_for_repository(enrichment_results_manager, create_results_params):
    """
    Test the creation of a new Enrichment result item for a repository.

    Act:
        - Call the `create_results_for_repository` method with the parameters.

    Assert:
        - Ensure the `put_item` method is called once (one item is inserted).
        - Ensure the insertion is done with the expected parameters.
    """
    # Act
    enrichment_results_manager.create_results_for_repository(create_results_params)

    # Assert
    expected_call_args = {
        'Item': {
            'PK': f'TENANT#{TENANT_ID}',
            'SK': f'VENDOR#{VENDOR}#OWNER#{OWNER}#REPO#{REPO}#CREATED_AT#{FIXED_TIMESTAMP.lower()}',
            'tenant_id': TENANT_ID,
            'vendor': VENDOR,
            'owner': OWNER,
            'repo': REPO,
            'created_at': FIXED_TIMESTAMP,
            'enrichment_results': MOCK_ENRICHED_DATA,
            'jit_event_id': JIT_EVENT_ID,
            'jit_event_name': JitEventName.MergeDefaultBranch
        }
    }
    enrichment_results_manager.table.put_item.assert_called_once()
    actual_call_args = enrichment_results_manager.table.put_item.call_args[1]
    assert actual_call_args == expected_call_args


def test_create_results_for_repository_raises_exception(enrichment_results_manager, create_results_params):
    """
    Test the creation of a new Enrichment result item for a repository when an exception occurs.

    Arrange:
        - Mock the `put_item` method to raise a ClientError.

    Act and Assert:
        - Ensure the `put_item` method raises a ClientError and the error is logged.
    """
    # Arrange
    enrichment_results_manager.table.put_item.side_effect = ClientError(
        {"Error": {"Code": "TestException", "Message": MOCK_EXCEPTION_TEXT}}, "put_item")

    # Act and Assert
    with pytest.raises(ClientError) as exc:
        enrichment_results_manager.create_results_for_repository(create_results_params)

    assert exc.value.response["Error"]["Message"] == MOCK_EXCEPTION_TEXT


def test_get_results_for_repository(enrichment_results_manager):
    """
    Test fetching the latest Enrichment result item for a repository.

    Arrange:
        - Mock the `query` method to return a single item.

    Act:
        - Call the `get_results_for_repository` method with the parameters.

    Assert:
        - Ensure the returned item is the expected one.
    """
    # Arrange
    expected_item = {
        'PK': f'TENANT#{TENANT_ID}',
        'SK': f'VENDOR#{VENDOR}#OWNER#{OWNER}#REPO#{REPO}#CREATED_AT#{FIXED_TIMESTAMP.lower()}',
        'tenant_id': TENANT_ID,
        'vendor': VENDOR,
        'owner': OWNER,
        'repo': REPO,
        'created_at': FIXED_TIMESTAMP,
        'enrichment_results': MOCK_ENRICHED_DATA,
        'jit_event_id': JIT_EVENT_ID,
        'jit_event_name': JitEventName.MergeDefaultBranch.value
    }
    enrichment_results_manager.table.query.return_value = {
        'Items': [expected_item]
    }

    # Act
    result = enrichment_results_manager.get_results_for_repository(
        tenant_id=TENANT_ID,
        vendor=VENDOR,
        owner=OWNER,
        repo=REPO,
    )

    # Assert
    assert result == BaseEnrichmentResultsItem(**expected_item)


def test_get_results_for_repository_no_results(enrichment_results_manager):
    """
    Test fetching the latest Enrichment result item for a repository when no results exist.

    Arrange:
        - Mock the `query` method to return an empty list.

    Act:
        - Call the `get_results_for_repository` method with the parameters.

    Assert:
        - Ensure a `EnrichmentResultsItemNotFoundError` is raised with the expected message.
    """
    # Arrange
    enrichment_results_manager.table.query.return_value = {'Items': []}

    # Act and Assert
    with pytest.raises(EnrichmentResultsItemNotFoundError):
        enrichment_results_manager.get_results_for_repository(
            tenant_id=TENANT_ID,
            vendor=VENDOR,
            owner=OWNER,
            repo=REPO,
        )


def test_get_results_for_repository_raises_exception(enrichment_results_manager):
    """
    Test fetching the latest Enrichment result item for a repository when an exception occurs.

    Arrange:
        - Mock the `query` method to raise a ClientError.

    Act and Assert:
        - Ensure the `query` method raises a ClientError and the error is logged.
    """
    # Arrange
    enrichment_results_manager.table.query.side_effect = ClientError(
        {"Error": {"Code": "TestException", "Message": MOCK_EXCEPTION_TEXT}}, "query")

    # Act and Assert
    with pytest.raises(ClientError) as exc:
        enrichment_results_manager.get_results_for_repository(
            tenant_id=TENANT_ID,
            vendor=VENDOR,
            owner=OWNER,
            repo=REPO,
        )

    assert exc.value.response["Error"]["Message"] == MOCK_EXCEPTION_TEXT

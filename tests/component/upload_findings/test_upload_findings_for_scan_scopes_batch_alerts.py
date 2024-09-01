import datetime
import uuid
from decimal import Decimal
import pytest
import responses
from freezegun import freeze_time
from jit_utils.models.findings.entities import Resolution, Ticket

from src.lib.models.finding_model import UiResolution
from tests.component.ignore_rules.utils import build_asset_id_ignore_rule_dict, build_filename_ignore_rule_dict, \
    build_fingerprint_ignore_rule_dict, build_plan_item_ignore_rule_dict
from tests.component.utils.assert_finding_full import assert_finding_full
from tests.component.utils.mock_clients.mock_asset import mock_get_asset_api
from tests.component.utils.mock_clients.mock_authentication import mock_get_internal_token_api
from tests.component.utils.mock_mongo_driver import mock_mongo_driver
from tests.component.utils.put_new_batch_status_in_db import put_new_batch_status_in_db
from tests.fixtures import build_finding_dict
from jit_utils.models.tags.entities import Tag

TENANT_ID = "32997b4d-14b6-45c7-bef1-a31c7c7f352c"
ASSET_ID = "599bd3e3-3b3e-4e3e-8e3e-3b3e3b3e3b3e"
CONTROL_NAME = "control_name"
JIT_EVENT_ID = "329abd3e3-1e2e-55c7-bef1-a31c7c7f352c"
EXECUTION_ID = "abcd8888-1234-5678-1234-567812345678"
CREATED_AT = "2023-01-01T00:00:00"
JIT_EVENT_NAME = "trigger_scheduled_task"
SCAN_SCOPE_1 = {"scope_attr": "scope_1"}
SCAN_SCOPE_2 = {"scope_attr": "scope_2"}
SCAN_SCOPE_3 = {"scope_attr": "scope_3"}
JOB = {"workflow_slug": "my-workflow-slug", "job_name": "my-job-name"}
TAGS = [{'name': "team", 'value': "birds"}]


def setup_test(mocker, mocked_tables, snapshot_count):
    # Assign
    # Mock mongo driver
    mongo_db = mock_mongo_driver(mocker)
    findings_collection = mongo_db.findings
    ignore_rules_collection = mongo_db.ignore_rules
    _, upload_findings_status_table = mocked_tables
    put_new_batch_status_in_db(TENANT_ID, JIT_EVENT_ID, EXECUTION_ID, snapshot_count)

    mock_get_internal_token_api()
    mock_get_asset_api(ASSET_ID, TAGS)

    return findings_collection, ignore_rules_collection, upload_findings_status_table


def assert_status_item_updated(upload_findings_status_table):
    db_items = upload_findings_status_table.scan()['Items']
    assert len(db_items) == 1

    assert db_items[0] == {
        'PK': f'TENANT#{TENANT_ID}',
        'SK': f'JIT_EVENT_ID#{JIT_EVENT_ID}#EXECUTION_ID#{EXECUTION_ID}',
        'jit_event_id': JIT_EVENT_ID, 'jit_event_name': JIT_EVENT_NAME,
        'execution_id': EXECUTION_ID, 'created_at': CREATED_AT,
        'tenant_id': TENANT_ID, 'snapshots_count': Decimal('0'),
        'error_count': Decimal('0'), 'completed_at': None, 'failed_snapshots': [], 'is_backlog': True
    }


def build_finding_dict_with_default_values(**kwargs):
    default_params = {
        "tenant_id": TENANT_ID,
        "asset_id": ASSET_ID,
        "control_name": CONTROL_NAME,
        "created_at": CREATED_AT,
        "jobs": [JOB],
        "with_specs": True,
        "location_text": "location_text",
        "fingerprint": str(uuid.uuid4()),
        "tags": [Tag(**tag) for tag in TAGS]
    }
    return build_finding_dict(**{**default_params, **kwargs})


def call_handler(findings_for_scan_scope, job=JOB):
    event = {
        "detail": {
            'batch_id': 'batch_id',
            "tenant_id": TENANT_ID,
            "control_name": CONTROL_NAME,
            "asset_id": ASSET_ID,
            "created_at": CREATED_AT,
            "jit_event_id": JIT_EVENT_ID,
            "jit_event_name": JIT_EVENT_NAME,
            "execution_id": EXECUTION_ID,
            "findings_for_scan_scope": findings_for_scan_scope,
            "job": job,
        }
    }
    # Act
    from src.handlers.findings.upload_findings import upload_findings_for_scan_scopes_batch_handler
    upload_findings_for_scan_scopes_batch_handler(event, None)


@freeze_time("2023-01-01")
@responses.activate
def test_upload_findings_for_snapshots_batch(mocker, mocked_tables):
    """
    This tests checks 4 events from 2 scan scopes.
    snapshot1:
        first event (reoccurring) is a reoccuring finding (it's in DB and also received in event)
        second event (should_be_fixed) - exists in DB but not in scan scope, meaning - should turn to fixed
    snapshot2:
        contains 2 events, those are new thus they should be inserted as is.

    Setup:
        1) Upload a reoccuring finding to the db
        2) upload a finding which should be fixed (not exist in the event)
        3) upload finding that was already fixed in previous execution
    Test:
        1) call the handler

    Assert:
        1) first event should stay open, but the ids should be kept from the db
        2) second event turns into fixed
        3) An 'finding changed' event is sent to eventbridge with the fixed finding details
        3) 3,4 events (from scan scope 2) are added as new
        4) verify all snapshots are uploaded
        5) verify all findings are uploaded to mango
    """
    findings_collection, _, upload_findings_status_table = setup_test(mocker, mocked_tables, 2)

    recurring_finding = build_finding_dict_with_default_values(is_code_finding=False,
                                                               scan_scope=SCAN_SCOPE_1)

    open_should_be_fixed_finding = build_finding_dict_with_default_values(is_code_finding=False,
                                                                          scan_scope=SCAN_SCOPE_1)

    fixed_finding = build_finding_dict_with_default_values(
        resolution=UiResolution.FIXED,
        fixed_at_execution_id="previous_execution_id",
        scan_scope=SCAN_SCOPE_1
    )
    findings_collection.insert_many([recurring_finding, open_should_be_fixed_finding, fixed_finding])
    # We want to verify that we append the new jobs to the existing ones
    new_finding_1 = build_finding_dict_with_default_values(scan_scope=SCAN_SCOPE_2)
    new_finding_2 = build_finding_dict_with_default_values(scan_scope=SCAN_SCOPE_2)

    findings_for_scan_scope = [
        {"scan_scope": SCAN_SCOPE_1, "findings": [recurring_finding.copy()]},
        {"scan_scope": SCAN_SCOPE_2, "findings": [new_finding_1, new_finding_2]},
    ]
    call_handler(findings_for_scan_scope)

    assert_status_item_updated(upload_findings_status_table)

    db_results = list(findings_collection.find({}))
    assert (len(db_results) == 5)

    # created_at changes to the one in  DB, also the first ids and the first jit name
    assert_finding_full(
        finding_in_db=db_results[0],
        expected_finding=recurring_finding,
        id=recurring_finding["id"],  # The id should be kept from the db (reoccurring)
    )

    assert_finding_full(
        finding_in_db=db_results[1],
        expected_finding=open_should_be_fixed_finding,
        resolution=UiResolution.FIXED,
        fixed_at_execution_id=EXECUTION_ID,
        fixed_at_jit_event_id=JIT_EVENT_ID,
        ended_at=CREATED_AT
    )
    assert_finding_full(finding_in_db=db_results[2], expected_finding=fixed_finding)
    assert_finding_full(finding_in_db=db_results[3], expected_finding=new_finding_1)
    assert_finding_full(finding_in_db=db_results[4], expected_finding=new_finding_2)


@freeze_time("2023-01-01")
@responses.activate
def test_upload_findings_for_snapshots_batch__same_finding_from_different_workflows(mocker, mocked_tables):
    """
    This tests checks that the handles 'finds' findings even if it not from the same 'job'
    Setup:
        1) Upload 2 findings to the db, with test_ids: 't1' and 't2'.
    Test:
        1) call the handler with the same finding but with different job & workflow test_ids: 't2', and 't3'.
    Assert:
        1) we should have 3 findings: t1, t2, t3.
    """
    findings_collection, _, upload_findings_status_table = setup_test(mocker, mocked_tables, 1)

    t1_finding = build_finding_dict_with_default_values(
        is_code_finding=False,
        scan_scope=SCAN_SCOPE_1,
        test_id='t1',
    )
    t2_finding = build_finding_dict_with_default_values(
        is_code_finding=False,
        scan_scope=SCAN_SCOPE_1,
        test_id='t2',
    )
    findings_collection.insert_many([t1_finding, t2_finding])

    different_job = {"workflow_slug": "different-workflow", "job_name": "different-job"}
    updated_t2_finding = {
        **t2_finding,
        'jobs': [different_job],
    }

    t3_finding = build_finding_dict_with_default_values(
        is_code_finding=False,
        scan_scope=SCAN_SCOPE_1,
        test_id='t3',
    )

    findings_for_scan_scope = [
        {"scan_scope": SCAN_SCOPE_1, "findings": [updated_t2_finding, t3_finding]},
    ]
    call_handler(findings_for_scan_scope, job=different_job)

    assert_status_item_updated(upload_findings_status_table)

    db_results = list(findings_collection.find({}))
    assert (len(db_results) == 3)

    assert_finding_full(
        finding_in_db=db_results[0],
        expected_finding=t1_finding,
    )
    assert_finding_full(
        finding_in_db=db_results[1],
        expected_finding=updated_t2_finding,
        jobs=[different_job, JOB]
    )
    assert_finding_full(
        finding_in_db=db_results[2],
        expected_finding=t3_finding,
    )


@freeze_time("2023-01-01")
@responses.activate
def test_upload_findings_for_snapshots_batch_with_asset_not_active(mocker, mocked_tables):
    """
    This test checks the behavior of the upload findings for scan scope batch handler when reactivating an
    'INACTIVE' finding alongside processing a completely new finding. It verifies that findings with
    previously 'INACTIVE' resolution are properly updated to 'OPEN' while preserving their original creation
    date and ensuring that new findings are added with the correct attributes.

    Setup:
        1) Insert a single finding with a resolution of INACTIVE into the mocked database.
        2) Prepare two new findings for the scan scope: one completely new, and another mirroring the 'INACTIVE'
           finding, intended to simulate its reactivation.

    Test:
        1) Trigger the upload findings for snapshots batch handler with the prepared event, including the two new
           findings.

    Assert:
        1) Verify that there are exactly two findings in the database post-operation.
        2) The new finding is with an 'OPEN' resolution and a new 'created_at' date.
        3) The reactivated finding (initially 'INACTIVE') is now 'OPEN', with its 'created_at' date unchanged.
    """
    # Assign
    findings_collection, _, upload_findings_status_table = setup_test(mocker, mocked_tables, 1)

    # Insert a finding with resolution INACTIVE
    asset_not_active_finding = build_finding_dict_with_default_values(
        scan_scope=SCAN_SCOPE_1,
        fingerprint="unique_fingerprint",
        resolution=Resolution.INACTIVE,
        is_code_finding=False
    )
    findings_collection.insert_one(asset_not_active_finding)

    reactivated_finding = asset_not_active_finding.copy()
    reactivated_finding["id"] = "reactivated_finding"
    reactivated_finding["resolution"] = Resolution.OPEN
    reactivated_finding["issue_text"] = "reactivated issue text"
    reactivated_finding["created_at"] = "2024-01-01T00:00:00.000000"

    new_finding = build_finding_dict_with_default_values(scan_scope=SCAN_SCOPE_1)
    findings_for_scan_scope = [{"id": '1', "scan_scope": SCAN_SCOPE_1, "findings": [new_finding, reactivated_finding]}]

    call_handler(findings_for_scan_scope)

    assert_status_item_updated(upload_findings_status_table)

    # Assert
    db_results = list(findings_collection.find({}))

    # Assert total findings count
    assert len(db_results) == 2

    assert_finding_full(
        finding_in_db=db_results[0],
        expected_finding=reactivated_finding,

        id=asset_not_active_finding["id"],  # The id should be kept from the db (reoccurring)
        created_at=asset_not_active_finding["created_at"],  # The creation date should be kept from the db
        resolution=Resolution.OPEN,
    )
    assert_finding_full(finding_in_db=db_results[1], expected_finding=new_finding)


@freeze_time("2023-01-01")
@responses.activate
def test_upload_findings_with_reactivation_and_ignore_rules(mocker, mocked_tables):
    """
    This test verifies the reactivation of 'INACTIVE' findings and the application of ignore rules.
    It introduces two previously 'INACTIVE' findings - one associated with an ignore rule and one without.
    It then reactivates these findings and introduces a new finding to observe the correct application of states
    and rules.

    Setup:
        1) Insert two 'INACTIVE' findings into the mocked database.
        2) Associate an ignore rule with the first finding.
        3) Prepare three new findings for the snapshot: one new and two reactivating the 'INACTIVE' findings.

    Test:
        1) Execute the upload findings for snapshots batch handler with the prepared event.

    Assert:
        1) All three findings are now 'OPEN' in the database.
        2) The creation dates for the reactivated findings remain unchanged.
        3) Ignore rules are correctly applied to the relevant finding.
    """
    findings_collection, ignore_rules_collection, upload_findings_status_table = setup_test(mocker, mocked_tables, 1)

    # Constants
    ORIGINAL_CREATED_DATE = "2023-03-26T06:09:03.063186"
    REACTIVATION_DATE = "2024-01-01T00:00:00.000000"

    # Create an ignore rule in the DB for the first inactive finding
    ignore_rule_for_first = build_fingerprint_ignore_rule_dict(fingerprint="inactiveFingerprintOne")
    ignore_rules_collection.insert_one(ignore_rule_for_first)

    # Findings setup
    first_inactive_finding = build_finding_dict_with_default_values(
        finding_id="inactive_finding_with_ignore",
        fingerprint="inactiveFingerprintOne",
        created_at=ORIGINAL_CREATED_DATE,
        resolution=Resolution.INACTIVE,
        ignored=True,
        ignore_rules_ids=[ignore_rule_for_first['id']],
        scan_scope=SCAN_SCOPE_1,
        is_code_finding=False
    )

    second_inactive_finding = build_finding_dict_with_default_values(
        finding_id="inactive_finding_without_ignore",
        fingerprint="inactiveFingerprintTwo",
        created_at=ORIGINAL_CREATED_DATE,
        resolution=Resolution.INACTIVE,
        scan_scope=SCAN_SCOPE_1,
        is_code_finding=False
    )

    findings_collection.insert_many([first_inactive_finding, second_inactive_finding])

    # Prepare new findings for reactivation and addition
    new_finding = build_finding_dict_with_default_values(
        created_at=REACTIVATION_DATE,
        scan_scope=SCAN_SCOPE_1,
        is_code_finding=False
    )

    reactivation_for_first_inactive = first_inactive_finding.copy()
    reactivation_for_first_inactive["id"] = "reactivated_first"
    reactivation_for_first_inactive["resolution"] = Resolution.OPEN
    reactivation_for_first_inactive["created_at"] = REACTIVATION_DATE
    reactivation_for_first_inactive["ignored"] = False
    reactivation_for_first_inactive["ignore_rules_ids"] = []

    reactivation_for_second_inactive = second_inactive_finding.copy()
    reactivation_for_second_inactive["id"] = "reactivated_second"
    reactivation_for_second_inactive["resolution"] = Resolution.OPEN
    reactivation_for_second_inactive["created_at"] = REACTIVATION_DATE
    # Act

    findings_for_scan_scope = [{
        "id": '1', "scan_scope": SCAN_SCOPE_1,
        "findings": [new_finding, reactivation_for_first_inactive, reactivation_for_second_inactive]
    }]

    call_handler(findings_for_scan_scope)

    assert_status_item_updated(upload_findings_status_table)

    # Assert
    db_results = list(findings_collection.find({}))

    # Assert total findings count
    assert len(db_results) == 3

    assert_finding_full(
        finding_in_db=db_results[0],
        expected_finding=reactivation_for_first_inactive,
        id=first_inactive_finding["id"],
        resolution=Resolution.OPEN.value,
        created_at=ORIGINAL_CREATED_DATE,
        modified_at=datetime.datetime.now().isoformat(),
        ignored=False,
    )

    assert_finding_full(
        finding_in_db=db_results[1],
        expected_finding=reactivation_for_second_inactive,
        id=second_inactive_finding["id"],
        resolution=Resolution.OPEN.value,
        created_at=ORIGINAL_CREATED_DATE,
        modified_at=datetime.datetime.now().isoformat(),
        ignored=False,
    )

    assert_finding_full(
        finding_in_db=db_results[2],
        expected_finding=new_finding,
    )


@freeze_time("2023-01-01")
@responses.activate
def test_upload_findings_for_snapshots_batch_same_fingerprint(mocker, mocked_tables):
    """
    This tests checks that if there are findings with the same fingerprint in the same scan scope,
    only one of them is stored in the DB.
    snapshot1:
        first finding
    snapshot2:
        contains 2 findings, with the same fingerprint
    Test:
        1) call the handler

    Assert:
        1) only 2 findings should be uploaded to DB
        2) first finding should be uploaded to DB
        3) second finding should be uploaded to DB
    """
    # Assign
    findings_collection, _, upload_findings_status_table = setup_test(mocker, mocked_tables, 2)

    finding_1 = build_finding_dict_with_default_values(
        scan_scope=SCAN_SCOPE_1,
    )
    finding_2 = build_finding_dict_with_default_values(
        scan_scope=SCAN_SCOPE_2,
    )
    finding_3 = build_finding_dict_with_default_values(
        scan_scope=SCAN_SCOPE_2,
        fingerprint=finding_2["fingerprint"]  # This should be deduped
    )

    findings_for_scan_scope = [
        {"scan_scope": SCAN_SCOPE_1, "findings": [finding_1]},
        {"scan_scope": SCAN_SCOPE_2, "findings": [finding_2, finding_3]},
    ]
    call_handler(findings_for_scan_scope)  # TODO: Fix payload

    # Assert
    assert_status_item_updated(upload_findings_status_table)
    db_results = list(findings_collection.find({}))

    # assert 2 findings were added to the db
    assert len(db_results) == 2
    assert_finding_full(
        finding_in_db=db_results[0],
        expected_finding=finding_1,
    )
    assert_finding_full(
        finding_in_db=db_results[1],
        expected_finding=finding_2,
    )


@responses.activate
def test_upload_findings_for_snapshots_batch_with_large_amount_of_findings(mocker, mocked_tables):
    findings_collection, _, upload_findings_status_table = setup_test(mocker, mocked_tables, 2)

    findings_to_upload_scope_1 = [
        build_finding_dict_with_default_values(scan_scope=SCAN_SCOPE_1)
        for _ in range(0, 101)
    ]
    findings_to_upload_scope_2 = [
        build_finding_dict_with_default_values(scan_scope=SCAN_SCOPE_2)
        for _ in range(0, 153)
    ]
    # Create mock findings for scan_scope
    findings_for_scan_scope = [
        {
            "scan_scope": SCAN_SCOPE_1,
            "findings": findings_to_upload_scope_1,
        },
        {
            "scan_scope": SCAN_SCOPE_2,
            "findings": findings_to_upload_scope_2,
        }
    ]
    call_handler(findings_for_scan_scope)

    assert_status_item_updated(upload_findings_status_table)

    mongo_findings = list(findings_collection.find({}))

    assert len(mongo_findings) == 254
    for finding_in_db, expected_finding in zip(mongo_findings, findings_to_upload_scope_1 + findings_to_upload_scope_2):
        assert_finding_full(finding_in_db, expected_finding)


@freeze_time("2023-01-01")
@responses.activate
@pytest.mark.parametrize("ignored", [True, False])
def test_upload_findings_for_snapshots_batch_with_fingerprint_transition_open_finding(mocker, mocked_tables, ignored):
    """
    Set up:
        1) There is an existing finding with fingerprint X
        2) New finding is uploaded with fingerprint Y and old_fingerprint X
    Test:
        1) call upload_findings_for_snapshots_batch_handler
    Åssert:
        1) The existing finding should be updated with fingerprint Y
    """
    findings_collection, _, upload_findings_status_table = setup_test(mocker, mocked_tables, 1)

    old_finding_fingerprint, new_finding_fingerprint = "X", "Y"

    finding = build_finding_dict_with_default_values(
        fingerprint=old_finding_fingerprint,
        scan_scope=SCAN_SCOPE_1,
        is_code_finding=False,
        ignored=ignored
    )

    findings_collection.insert_one(finding)

    new_finding = build_finding_dict_with_default_values(
        fingerprint=new_finding_fingerprint,
        old_fingerprints=[old_finding_fingerprint],
        scan_scope=SCAN_SCOPE_1,
        is_code_finding=False,
        ignored=ignored
    )
    findings_for_scan_scope = [
        {"scan_scope": SCAN_SCOPE_1, "findings": [new_finding]},
    ]

    call_handler(findings_for_scan_scope)

    assert_status_item_updated(upload_findings_status_table)

    # Assert
    db_results = list(findings_collection.find({}))

    assert len(db_results) == 1

    assert_finding_full(
        finding_in_db=db_results[0],
        expected_finding=new_finding,
        id=finding["id"],
    )


@freeze_time("2023-01-01")
@responses.activate
def test_upload_findings_with_asset_and_fingerprint_ignore_rules(mocker, mocked_tables):
    """
    Test:
        1) Insert an ignore rule for an asset ID and an ignore rule for a fingerprint.
        2) Upload 50 findings with the same asset ID and one finding with the ignored fingerprint.
    Assert:
        1) Ensure that all 51 findings are with resolution ignored=True.
    """
    findings_collection, ignore_rules_collection, upload_findings_status_table = \
        setup_test(mocker, mocked_tables, 1)
    ignored_fingerprint = "ignored_fp"

    # create ignore rule for asset_id
    asset_id_ignore_rule = build_asset_id_ignore_rule_dict(asset_id=ASSET_ID, tenant_id=TENANT_ID)
    ignore_rules_collection.insert_one(asset_id_ignore_rule)

    # create ignore rule for fingerprint
    fingerprint_ignore_rule = build_fingerprint_ignore_rule_dict(fingerprint=ignored_fingerprint, tenant_id=TENANT_ID)
    ignore_rules_collection.insert_one(fingerprint_ignore_rule)

    # create 51 findings, 50 with the same asset_id and 1 with the ignored fingerprint
    findings = []
    for i in range(50):
        findings.append(
            build_finding_dict_with_default_values(
                finding_id=str(i),
                fingerprint="some_fingerprint" + str(i),
                scan_scope=SCAN_SCOPE_1,
                is_code_finding=False,
                asset_id=ASSET_ID
            )
        )
    # 1 finding with the ignored fingerprint
    findings.append(
        build_finding_dict_with_default_values(
            finding_id="50",  # Adjust the id for the 51st finding
            fingerprint=ignored_fingerprint,
            scan_scope=SCAN_SCOPE_1,
            is_code_finding=False,
            asset_id=str(uuid.uuid4())  # Different asset_id
        )
    )
    findings_for_scan_scope = [{'scan_scope': SCAN_SCOPE_1, "findings": findings}]
    call_handler(findings_for_scan_scope)

    assert_status_item_updated(upload_findings_status_table)

    # Assert conditions after event processing
    ignored_findings = list(findings_collection.find({}))

    assert len(ignored_findings) == 51  # All 51 findings are ignored
    for indx, (db_finding, expected_finding) in enumerate(zip(ignored_findings, findings)):
        if indx < 50:  # Ignored by asset_id
            assert_finding_full(db_finding, expected_finding, ignored=True, resolution=Resolution.INACTIVE.value,
                                ignore_rules_ids=[asset_id_ignore_rule['id']])
        else:  # Ignored by fingerprint
            assert_finding_full(db_finding, expected_finding, ignored=True,
                                ignore_rules_ids=[fingerprint_ignore_rule['id']])


@freeze_time("2023-01-01")
@responses.activate
def test_upload_unrelated_finding_with_existing_inactive_asset(mocker, mocked_tables):
    """
    Test:
        - Given no ignore rules and an existing finding with resolution 'INACTIVE',
        - When a new and unrelated finding gets uploaded,
        - Then the existing finding remains with resolution 'INACTIVE'.
    """
    findings_collection, ignore_rules_collection, upload_findings_status_table = \
        setup_test(mocker, mocked_tables, 1)

    existing_fingerprint = "existing_123"

    # Existing finding with resolution INACTIVE
    existing_finding = build_finding_dict_with_default_values(
        fingerprint=existing_fingerprint,
        filename='file1',
        scan_scope=SCAN_SCOPE_1,
        resolution='INACTIVE',
        is_code_finding=False
    )
    findings_collection.insert_one(existing_finding)

    new_finding = build_finding_dict_with_default_values(
        fingerprint="new_456",
        scan_scope=SCAN_SCOPE_1,
        is_code_finding=False,
    )

    findings_for_snapshots = [{'scan_scope': SCAN_SCOPE_1, "findings": [new_finding]}]
    call_handler(findings_for_snapshots)

    assert_status_item_updated(upload_findings_status_table)

    # Ensure the existing finding remains unchanged
    db_items = list(findings_collection.find({}))
    assert len(db_items) == 2
    assert_finding_full(db_items[0], existing_finding)
    assert_finding_full(db_items[1], new_finding)


@freeze_time("2023-01-01")
@responses.activate
def test_upload_findings_for_snapshots_batch_with_resolved_findings(
        mocker, mocked_tables
):
    """
    Test upload_findings_for_snapshots_batch_handler with resolved findings.
    No findings in the batch event, meaning the existing findings are resolved.
    Two findings are resolved, one of them is FIXED and the other is INACTIVE.

    Setup:
        1) Upload an open finding.
        2) Upload an open ignored=true.

    Test:
        1) call the handler

    Assert:
        1) first finding should become fixed
        2) second finding should become inactive
        3) verify all findings are uploaded to mango
    """
    findings_collection, ignore_rules_collection, upload_findings_status_table = \
        setup_test(mocker, mocked_tables, 1)

    open_finding = build_finding_dict_with_default_values(
        finding_id="finding_id_1",
        fingerprint="fingerprint1",
        scan_scope=SCAN_SCOPE_1,
        is_code_finding=False,
    )

    open_ignored_finding = build_finding_dict_with_default_values(
        finding_id="finding_id_2",
        fingerprint="fingerprint2",
        scan_scope=SCAN_SCOPE_1,
        ignored=True,
        is_code_finding=False,
    )
    findings_collection.insert_many([open_finding, open_ignored_finding])

    findings_for_scan_scope = [{"scan_scope": SCAN_SCOPE_1, "findings": []}]
    call_handler(findings_for_scan_scope)

    assert_status_item_updated(upload_findings_status_table)

    db_results = list(findings_collection.find({}))
    assert len(db_results) == 2

    # Finding should be fixed
    should_be_fixed_finding_mongo = db_results[0]
    assert_finding_full(
        should_be_fixed_finding_mongo,
        open_finding,
        resolution=Resolution.FIXED,
        fixed_at_execution_id=EXECUTION_ID,
        fixed_at_jit_event_id=JIT_EVENT_ID,
        ended_at=datetime.datetime.now().isoformat()
    )
    # Finding should be inactive
    should_be_inactive_finding_mongo = db_results[1]
    assert_finding_full(
        should_be_inactive_finding_mongo,
        open_ignored_finding,
        resolution=Resolution.INACTIVE,
        fixed_at_execution_id=EXECUTION_ID,
        fixed_at_jit_event_id=JIT_EVENT_ID,
        ended_at=datetime.datetime.now().isoformat()
    )


@freeze_time("2023-01-01")
@responses.activate
def test_upload_findings_with_plan_item_and_asset_id_and_filename_ignore_rules(mocker, mocked_tables):
    """
    Test uploading findings with ignore rules based on 'plan_item' and a random 'asset_id'.
    This test verifies the behavior of the upload findings handler when ignore rules are applied to specific fields.
    We create two ignore rules: one for a specific 'plan_item' value and another for a specific 'asset_id'.
    Three findings are then uploaded:
    - The first matches the 'plan_item' ignore rule but not the 'asset_id'.
    - The second matches the 'asset_id' ignore rule but not the 'plan_item'.
    - The third does not match either ignore rule.
    The test ensures that findings matching either of the ignore rules are marked as ignored,
    while the finding unrelated to both rules is not ignored.

    Setup:
        1) Create an ignore rule based on a specific 'plan_item'.
        2) Create another ignore rule based on a specific 'asset_id'.
        3) Prepare three findings: one matching only the 'plan_item', one matching only the 'asset_id',
        and one unrelated to both.

    Test:
        1) Trigger the upload findings for snapshots batch handler with the prepared findings.

    Assert:
        1) The finding matching the 'plan_item' ignore rule is marked as ignored & is INACTIVE.
        2) The finding matching the 'asset_id' ignore rule is marked as ignored & is INACTIVE.
        3) The unrelated finding is not marked as ignored.
    """

    findings_collection, ignore_rules_collection, upload_findings_status_table = \
        setup_test(mocker, mocked_tables, 1)

    asset_id_to_ignore = str(uuid.uuid4())
    irrelevant_asset_id = str(uuid.uuid4())

    plan_item_to_ignore = "plan_item_to_ignore"
    irrelevant_plan_item = "irrelevant_plan_item"

    filename_regex = r"^relevant/path/.*"  # Regex to match filenames starting with 'relevant/path/'
    file_path = "relevant/path/file.txt"
    irrelevant_file_path = "irrelevant/path/file.txt"

    # Create two ignore rules: one for plan_item and one for a random asset_id
    plan_item_ignore_rule = build_plan_item_ignore_rule_dict(
        tenant_id=TENANT_ID,
        plan_items=[plan_item_to_ignore]
    )
    asset_id_ignore_rule = build_asset_id_ignore_rule_dict(
        tenant_id=TENANT_ID,
        asset_id=asset_id_to_ignore
    )
    filename_ignore_rule = build_filename_ignore_rule_dict(
        tenant_id=TENANT_ID,
        filename_regex=filename_regex,
    )

    ignore_rules_collection.insert_many([plan_item_ignore_rule, asset_id_ignore_rule, filename_ignore_rule])

    # Create three findings
    findings = [
        build_finding_dict_with_default_values(
            scan_scope=SCAN_SCOPE_1, plan_item=plan_item_to_ignore, filename=irrelevant_file_path,
            with_specs=True, asset_id=irrelevant_asset_id),  # Match plan_item
        build_finding_dict_with_default_values(
            scan_scope=SCAN_SCOPE_1, plan_item=irrelevant_plan_item, filename=irrelevant_file_path,
            with_specs=True, asset_id=asset_id_to_ignore),  # Match asset_id
        build_finding_dict_with_default_values(
            scan_scope=SCAN_SCOPE_1, plan_item=irrelevant_plan_item, filename=file_path,
            with_specs=True, asset_id=irrelevant_asset_id),  # Match filename
        build_finding_dict_with_default_values(
            scan_scope=SCAN_SCOPE_1, plan_item=irrelevant_plan_item, filename=irrelevant_file_path,
            with_specs=True, asset_id=irrelevant_asset_id),  # Match neither
    ]

    findings_for_scan_scope = [{'scan_scope': findings[0]['scan_scope'], "findings": findings}]
    call_handler(findings_for_scan_scope)

    assert_status_item_updated(upload_findings_status_table)

    # Assert the results
    db_findings = list(findings_collection.find({}))
    assert len(db_findings) == 4
    # Match plan_item
    assert_finding_full(finding_in_db=db_findings[0], expected_finding=findings[0], resolution=Resolution.INACTIVE,
                        ignored=True, ignore_rules_ids=[plan_item_ignore_rule['id']])

    # Match asset_id
    assert_finding_full(finding_in_db=db_findings[1], expected_finding=findings[1], resolution=Resolution.INACTIVE,
                        ignored=True, ignore_rules_ids=[asset_id_ignore_rule['id']])

    # Match filename
    assert_finding_full(finding_in_db=db_findings[2], expected_finding=findings[2], resolution=Resolution.INACTIVE,
                        ignored=True, ignore_rules_ids=[filename_ignore_rule['id']])

    # Match neither
    assert_finding_full(finding_in_db=db_findings[3], expected_finding=findings[3], resolution=Resolution.OPEN)


@freeze_time("2023-01-01")
@responses.activate
def test_recurring_findings_update(mocker, mocked_tables):
    """
    Test that existing findings, when they recur in a subsequent execution, are correctly identified and merged with
    existing records.
    The merging ensures that specific fields from the original finding are retained, while others are updated based on
    the latest information.
    Setup:
        1) Insert initial findings into the mocked database.
        2) Simulate an event where the same findings recur with some updated attributes.

    Test:
        1) Execute the handler with the recurring findings.

    Assert:
        1) Verify that the recurring findings are merged correctly with existing entries.
        2) Ensure fields like 'created_at', 'ignore_rules_ids', 'tickets' and 'tags' are retained from the original.
        3) Check that no duplicates are created.
    """
    # Setup
    findings_collection, _, upload_findings_status_table = setup_test(mocker, mocked_tables, 1)
    common_fingerprint = "fingerprint"
    # Insert initial findings
    initial_finding = build_finding_dict_with_default_values(
        tenant_id=TENANT_ID,
        asset_id=ASSET_ID,
        control_name=CONTROL_NAME,
        created_at="2023-01-01T00:00:00",
        jobs=[JOB],
        fingerprint=common_fingerprint,
        ignored=True,
        ignore_rules_ids=["ignore_rule_id"],
        finding_id="1",
        scan_scope=SCAN_SCOPE_1,
        tickets=[Ticket(
            ticket_id="ticket123",
            ticket_url="http://example.com/ticket123",
            ticket_name="Sample Ticket",
            user_id="user123",
            vendor="vendorX",
            created_at="2023-01-01T00:00:00",
        )]
    )
    findings_collection.insert_one(initial_finding)

    # Simulate recurring finding
    recurring_finding = build_finding_dict_with_default_values(
        tenant_id=TENANT_ID,
        asset_id=ASSET_ID,
        control_name=CONTROL_NAME,
        created_at="2024-01-01T00:00:00",
        jobs=[JOB],
        fingerprint=common_fingerprint,
        tags=[],
        finding_id="2",
        ignored=False,
        ignore_rules_ids=[],
        scan_scope=SCAN_SCOPE_1
    )
    # Prepare the event for the handler
    findings_for_scan_scope = [
        {"scan_scope": SCAN_SCOPE_1, "findings": [recurring_finding]}
    ]

    # Execute
    call_handler(findings_for_scan_scope)

    # Assert
    assert_status_item_updated(upload_findings_status_table)
    db_results = list(findings_collection.find({}))

    # Ensure the findings are updated, not duplicated
    assert len(db_results) == 1
    updated_finding = db_results[0]
    assert_finding_full(
        finding_in_db=updated_finding,
        expected_finding=recurring_finding,
        id=initial_finding["id"],
        created_at=initial_finding["created_at"],
        first_workflow_id=initial_finding["first_workflow_id"],
        first_workflow_suite_id=initial_finding["first_workflow_suite_id"],
        ignored=initial_finding["ignored"],
        ignore_rules_ids=initial_finding["ignore_rules_ids"],
        modified_at=CREATED_AT,
        tags=initial_finding["tags"],
        tickets=initial_finding["tickets"]
    )


@freeze_time("2023-01-01")
@responses.activate
def test_upload_findings_for_snapshots_batch__when_finding_has_inner_scope_of_the_control_scope(mocker, mocked_tables):
    """
    This tests checks what hapens when the control scope is wider than the scope of the findings in the DB.
    When the control scope is wider than the scope of the findings in the DB, the findings should be considered as
    part of the control scope and should be updated accordingly.
    The scope of the control is {branch: main} (which means this was a full scan of the main branch)
    The scope of the finding is {branch: main, filepath: src/main.py}
                (because we add the file name of the finding to scope in the handler)

    Although the control scope is wider than the finding scope, we should be able to update the finding accordingly.

    Setup:
        1) Upload a reoccuring finding to the db
    Test:
        1) call the handler with the wider scope

    Assert:
        1) The finding should be updated accordingly
    """
    findings_collection, _, upload_findings_status_table = setup_test(mocker, mocked_tables, 1)
    control_scope = dict(branch='main')
    finding_scope = dict(branch='main', filepath='src/main.py')
    recurring_finding = build_finding_dict_with_default_values(
        is_code_finding=True, branch='main', filename='src/main.py', scan_scope=finding_scope
    )
    findings_collection.insert_many([recurring_finding])
    findings_for_scan_scope = [{"scan_scope": control_scope, "findings": [recurring_finding.copy()]}]
    call_handler(findings_for_scan_scope)

    assert_status_item_updated(upload_findings_status_table)
    db_results = list(findings_collection.find({}))
    assert (len(db_results) == 1)
    # created_at changes to the one in  DB, also the first ids and the first jit name
    assert_finding_full(
        finding_in_db=db_results[0],
        expected_finding=recurring_finding,
        id=recurring_finding["id"],  # The id should be kept from the db (reoccurring)
    )

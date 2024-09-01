from src.lib.data.mongo.findings_manager import FindingsDBManager
from src.lib.models.finding_model import UploadFindingsQueryOptions
from tests.component.utils.mock_mongo_driver import mock_mongo_driver
from tests.fixtures import build_finding_dict

TENANT_ID = "2c799663-2852-4038-a261-b208611f5e2b"
ASSET_ID = "6d50c3df-4ae5-468e-85af-b13444afae0a"
CONTROL_NAME = "control_name"
SCAN_SCOPE_1 = {"some_attribute": "some_value_1"}
SCAN_SCOPE_2 = {"some_attribute": "some_value_2"}
TEST_ID_1 = "test_id_1"
TEST_ID_2 = "test_id_2"
JOB_1 = {"job_name": "job_1", "workflow_slug": "workflow_1"}
JOB_2 = {"job_name": "job_2", "workflow_slug": "workflow_2"}


def test_get_findings_for_batch_upload__happy_flow(mocker):
    collection = mock_mongo_driver(mocker).findings
    finding_should_match_by_job = build_finding_dict(
        tenant_id=TENANT_ID,
        asset_id=ASSET_ID,
        control_name=CONTROL_NAME,
        scan_scope=SCAN_SCOPE_1,
        test_id=TEST_ID_1,
        jobs=[JOB_1],
        is_code_finding=False,
    )
    finding_should_match_by_test_id = build_finding_dict(
        tenant_id=TENANT_ID,
        asset_id=ASSET_ID,
        control_name=CONTROL_NAME,
        scan_scope=SCAN_SCOPE_1,
        test_id=TEST_ID_2,
        jobs=[JOB_2],
        is_code_finding=False,
    )
    finding_should_not_be_found = build_finding_dict(
        tenant_id=TENANT_ID,
        asset_id=ASSET_ID,
        control_name=CONTROL_NAME,
        scan_scope=SCAN_SCOPE_2,
        test_id=TEST_ID_1,
        jobs=[JOB_1, JOB_2],
        is_code_finding=False,
    )
    collection.insert_many([finding_should_match_by_job, finding_should_match_by_test_id, finding_should_not_be_found])

    options = UploadFindingsQueryOptions(
        tenant_id=TENANT_ID,
        asset_id=ASSET_ID,
        control_name=CONTROL_NAME,
        job=JOB_1,
        scan_scope=SCAN_SCOPE_1,
        scanned_test_ids=[TEST_ID_2],
    )
    found_findings = FindingsDBManager().get_findings_for_batch_upload(options)

    assert len(found_findings) == 2
    found_findings_ids = [finding.id for finding in found_findings]
    assert found_findings_ids == [finding_should_match_by_test_id["_id"], finding_should_match_by_job["_id"]]

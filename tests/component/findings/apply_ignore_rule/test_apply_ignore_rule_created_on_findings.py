import uuid
from typing import List

from aws_lambda_typing.context import Context
from datetime import datetime, timedelta
from uuid import uuid4

from jit_utils.models.ignore_rule.entities import FieldToBeIgnoredBy, OperatorTypes
from moto import mock_sqs
from moto.config.models import random_string

from src.lib.constants import IGNORE_RULE_UPSERTED_SIDE_EFFECTS_QUEUE_NAME
from src.lib.models.events import IgnoreRuleUpsertedSideEffectsOnFindings
from tests.component.ignore_rules.utils import (build_filename_ignore_rule_dict,
                                                build_fingerprint_ignore_rule_dict,
                                                build_asset_id_ignore_rule_dict, build_ignore_rule_dict_by_fields)
from tests.component.utils.assert_queue_content import assert_queue_content
from tests.component.utils.mock_mongo_driver import mock_mongo_driver
from tests.component.utils.mock_sqs_queue import mock_sqs_queue
from tests.fixtures import build_finding_dict
from src.handlers.findings.apply_ignore_rule_on_findings import apply_ignore_rule_created_on_findings
from jit_utils.models.findings.entities import Resolution


@mock_sqs
def test_apply_ignore_rule_created_on_findings(mocked_tables, mocker, env_variables):
    """
    Test the 'apply_ignore_rule_created_on_findings' handler.

    Setup:
    1. Insert one ignore rule into the database and one related finding.

    Test:
    Call the 'apply_ignore_rule_created_on_findings' handler.

    Assert:
    1. The corresponding finding should be updated in the database if needed.
    2. The IgnoreRuleCreatedSideEffectsOnFindings message should be sent to the queue
    """
    tenant_id = '19881e72-6d3b-49df-b79f-298ad89b8056'
    fingerprint = 'fingerprint'
    control_name = 'control_name'
    asset_id = '19881e72-1234-49df-b79f-298ad89b8056'
    finding_id = '5c481b2c-aaf1-4289-b2ac-3ddc79bc0196'
    yesterday_date = datetime.utcnow() - timedelta(days=1)
    now_string = datetime.utcnow().isoformat()
    ignore_rule = build_fingerprint_ignore_rule_dict(asset_id=asset_id,
                                                     control_name='control_name',
                                                     fingerprint=fingerprint)

    mocked_event = {
        'detail': {
            'tenant_id': tenant_id,
            **ignore_rule
        },
    }

    mongo_client = mock_mongo_driver(mocker)

    # Setup: 1. insert one finding to DB
    finding = build_finding_dict(tenant_id=tenant_id, fingerprint=fingerprint,
                                 asset_id=asset_id, finding_id=finding_id,
                                 control_name=control_name,
                                 created_at=yesterday_date.isoformat(),
                                 fix_suggestion=None,
                                 with_specs=True)

    mocked_findings_collection = mongo_client.findings
    mocked_ignore_rules_collection = mongo_client.ignore_rules

    mocked_ignore_rules_collection.insert_one(ignore_rule)
    mocked_findings_collection.insert_one(finding)

    # Mock the creation of the 'IgnoreRuleCreatedSideEffectsQueue' sqs queue
    mock_sqs_queue(queue_name=IGNORE_RULE_UPSERTED_SIDE_EFFECTS_QUEUE_NAME)

    apply_ignore_rule_created_on_findings(mocked_event, Context())
    # Assert: 1. The finding should be ignored.
    finding = mocked_findings_collection.find({'id': finding_id})[0]
    assert finding['ignored'] is True
    assert finding['specs'][0]['v'] is True
    assert finding['ignore_rules_ids'] == [ignore_rule.get('id')]
    assert finding['modified_at'] == now_string
    # Assert: 2. The IgnoreRuleCreatedSideEffectsOnFindings message should be sent to the queue
    expected_message = IgnoreRuleUpsertedSideEffectsOnFindings(
        tenant_id=tenant_id,
        ignore_rule=ignore_rule,
        total_effected_findings_count=1
    )
    assert_queue_content(
        queue_name=IGNORE_RULE_UPSERTED_SIDE_EFFECTS_QUEUE_NAME,
        expected_messages=[expected_message.dict()]
    )


@mock_sqs
def test_apply_ignore_rule_created_on_findings__finding_already_ignored(mocked_tables, mocker, env_variables):
    """
    Test the 'apply_ignore_rule_created_on_findings' handler.

    Setup:
    1. Insert one ignore rule into the database and one related finding.

    Test:
    Call the 'apply_ignore_rule_created_on_findings' handler.

    Assert:
    1. The corresponding finding should be updated in the database if needed.
    2. The IgnoreRuleCreatedSideEffectsOnFindings message should be sent to the queue
    """
    tenant_id = '19881e72-6d3b-49df-b79f-298ad89b8056'
    fingerprint = 'fingerprint'
    asset_id = '19881e72-1234-49df-b79f-298ad89b8056'
    finding_id = '5c481b2c-aaf1-4289-b2ac-3ddc79bc0196'
    control_name = 'control_name'
    yesterday_date = datetime.utcnow() - timedelta(days=1)
    now_string = datetime.utcnow().isoformat()
    mocked_existing_ignore_rule_id = 'dummy-ignore-rule-id'
    ignore_rule = build_fingerprint_ignore_rule_dict(asset_id=asset_id,
                                                     control_name=control_name,
                                                     fingerprint=fingerprint)

    mocked_event = {
        'detail': {
            'tenant_id': tenant_id,
            **ignore_rule
        },
    }

    mongo_client = mock_mongo_driver(mocker)

    # Setup: 1. insert one finding to DB
    finding = build_finding_dict(tenant_id=tenant_id, fingerprint=fingerprint,
                                 asset_id=asset_id, finding_id=finding_id,
                                 created_at=yesterday_date.isoformat(),
                                 ignored=True,
                                 with_specs=True,
                                 control_name=control_name,
                                 fix_suggestion=None,
                                 ignore_rules_ids=[mocked_existing_ignore_rule_id])

    mocked_findings_collection = mongo_client.findings
    mocked_ignore_rules_collection = mongo_client.ignore_rules

    mocked_ignore_rules_collection.insert_one(ignore_rule)
    mocked_findings_collection.insert_one(finding)

    # Mock the creation of the 'IgnoreRuleCreatedSideEffectsQueue' sqs queue
    mock_sqs_queue(queue_name=IGNORE_RULE_UPSERTED_SIDE_EFFECTS_QUEUE_NAME)

    # Act
    apply_ignore_rule_created_on_findings(mocked_event, Context())

    # Assert: 1. The finding should be ignored.
    finding = mocked_findings_collection.find({'id': finding_id})[0]
    assert finding['ignored'] is True
    assert finding['specs'][0]['v'] is True
    assert finding['ignore_rules_ids'] == [mocked_existing_ignore_rule_id, ignore_rule.get('id')]
    assert finding['modified_at'] == now_string
    # Assert: 2. The IgnoreRuleCreatedSideEffectsOnFindings message should be sent to the queue
    expected_message = IgnoreRuleUpsertedSideEffectsOnFindings(
        tenant_id=tenant_id,
        ignore_rule=ignore_rule,
        total_effected_findings_count=1
    )
    assert_queue_content(
        queue_name=IGNORE_RULE_UPSERTED_SIDE_EFFECTS_QUEUE_NAME,
        expected_messages=[expected_message.dict()]
    )


@mock_sqs
def test_apply_ignore_rule_created_on_findings__ignore_rule_already_applied_to_finding(
        mocked_tables, mocker, env_variables
):
    """
    Test the 'apply_ignore_rule_created_on_findings' handler
    when the ignore rule is already applied to the finding.

    Setup:
    1. Insert one ignore rule into the database and one related finding.

    Test:
    Call the 'apply_ignore_rule_created_on_findings' handler.

    Assert:
    1. the corresponding finding should be updated in the database if needed.
    2. The IgnoreRuleCreatedSideEffectsOnFindings message should not be sent to the queue
    """
    tenant_id = '19881e72-6d3b-49df-b79f-298ad89b8056'
    fingerprint = 'fingerprint'
    asset_id = '19881e72-1234-49df-b79f-298ad89b8056'
    finding_id = '5c481b2c-aaf1-4289-b2ac-3ddc79bc0196'
    yesterday_date = datetime.utcnow() - timedelta(days=1)
    ignore_rule = build_fingerprint_ignore_rule_dict(asset_id=asset_id,
                                                     fingerprint=fingerprint)

    mocked_event = {
        'detail': {
            'tenant_id': tenant_id,
            **ignore_rule
        },
    }

    mongo_client = mock_mongo_driver(mocker)

    # Setup: 1. insert one finding to DB
    finding = build_finding_dict(tenant_id=tenant_id, fingerprint=fingerprint,
                                 asset_id=asset_id, finding_id=finding_id,
                                 created_at=yesterday_date.isoformat(),
                                 ignored=True,
                                 with_specs=True,
                                 fix_suggestion=None,
                                 ignore_rules_ids=[ignore_rule.get('id')])

    mocked_findings_collection = mongo_client.findings
    mocked_ignore_rules_collection = mongo_client.ignore_rules

    mocked_ignore_rules_collection.insert_one(ignore_rule)
    mocked_findings_collection.insert_one(finding)

    # Mock the creation of the 'IgnoreRuleCreatedSideEffectsQueue' sqs queue
    mock_sqs_queue(queue_name=IGNORE_RULE_UPSERTED_SIDE_EFFECTS_QUEUE_NAME)

    # Assert: 1. The finding should be ignored.
    finding = mocked_findings_collection.find({'id': finding_id})[0]
    assert finding['ignored'] is True
    assert finding['specs'][0]['v'] is True
    assert finding['ignore_rules_ids'] == [ignore_rule.get('id')]

    # Assert: 2. No side effects should be triggered, as the ignore rule is already applied to the finding
    apply_ignore_rule_created_on_findings(mocked_event, Context())
    assert_queue_content(
        queue_name=IGNORE_RULE_UPSERTED_SIDE_EFFECTS_QUEUE_NAME,
        expected_messages=[]
    )


@mock_sqs
def test_apply_ignore_rule_created_asset_excluded_type_on_findings(mocked_tables, mocker, env_variables):
    """
    Test the 'apply_ignore_rule_created_on_findings' handler.
    Ignore rule  of type 'exclude' with asset_id field applied on open finding.
    The finding should be updated to be ignored with resolution 'INACTIVE'.

    Setup:
    1. Insert one ignore rule of type 'exclude' by asset into the database.
    2. Insert findings with random asset_ids.
    3. Insert one related finding with the same asset_id

    Test:
    Call the 'apply_ignore_rule_created_on_findings' handler.

    Assert:
    1. An ignore rule should be applied on the related finding.
    2. The finding should be updated to be ignored with resolution 'INACTIVE'.
    3. The IgnoreRuleCreatedSideEffectsOnFindings message should be sent to the queue
    """
    tenant_id = '19881e72-6d3b-49df-b79f-298ad89b8056'
    fingerprint = 'fingerprint'
    control_name = 'control_name'
    asset_id = '19881e72-1234-49df-b79f-298ad89b8056'
    finding_id = '5c481b2c-aaf1-4289-b2ac-3ddc79bc0196'
    yesterday_date = datetime.utcnow() - timedelta(days=1)
    now_string = datetime.utcnow().isoformat()
    ignore_rule = build_asset_id_ignore_rule_dict(asset_id=asset_id, tenant_id=tenant_id)

    mocked_event = {
        'detail': {
            **ignore_rule
        },
    }

    mongo_client = mock_mongo_driver(mocker)
    mocked_ignore_rules_collection = mongo_client.ignore_rules
    mocked_findings_collection = mongo_client.findings
    # Setup: 1. insert one ignore rule to DB
    mocked_ignore_rules_collection.insert_one(ignore_rule)
    # Setup: 2 Insert random findings for the tenant with different asset_ids to make sure they are not affected
    random_findings_in_db = [
        build_finding_dict(
            finding_id=f"finding_id-{i}",
            fingerprint=f"fingerprint-{i}",
            tenant_id=tenant_id,
            asset_id=str(uuid4()),
            control_name=control_name,
            test_id=f"test_id-{i}",
            issue_text=random_string(),  # This is to make sure that the findings are not identical
            fix_suggestion=None,
        )
        for i in range(10)
    ]
    mocked_findings_collection.insert_many(random_findings_in_db)

    # Setup: 3. insert one ignore rule to DB of the excluded asset_id
    finding = build_finding_dict(tenant_id=tenant_id, fingerprint=fingerprint,
                                 asset_id=asset_id, finding_id=finding_id,
                                 control_name=control_name,
                                 created_at=yesterday_date.isoformat(),
                                 resolution=Resolution.OPEN,
                                 fix_suggestion=None,
                                 with_specs=True)
    mocked_findings_collection.insert_one(finding)

    # Mock the creation of the 'IgnoreRuleCreatedSideEffectsQueue' sqs queue
    mock_sqs_queue(queue_name=IGNORE_RULE_UPSERTED_SIDE_EFFECTS_QUEUE_NAME)
    apply_ignore_rule_created_on_findings(mocked_event, Context())
    # Assert: 1 + 2. The finding should be ignored and resolution should be 'INACTIVE'
    finding = mocked_findings_collection.find({'id': finding_id})[0]
    assert finding['ignored'] is True
    assert finding['specs'][0]['v'] is True
    assert finding['ignore_rules_ids'] == [ignore_rule.get('id')]
    assert finding['modified_at'] == now_string
    assert finding['resolution'] == Resolution.INACTIVE
    # Assert: 3. The IgnoreRuleCreatedSideEffectsOnFindings message should be sent to the queue
    expected_message = IgnoreRuleUpsertedSideEffectsOnFindings(
        tenant_id=tenant_id,
        ignore_rule=ignore_rule,
        total_effected_findings_count=1
    )
    assert_queue_content(
        queue_name=IGNORE_RULE_UPSERTED_SIDE_EFFECTS_QUEUE_NAME,
        expected_messages=[expected_message.dict()]
    )


@mock_sqs
def test_apply_ignore_rule_created_asset_excluded_type_no_findings_for_asset(mocked_tables, mocker, env_variables):
    """
    Test the 'apply_ignore_rule_created_on_findings' handler.
    Ignore rule  of type 'exclude' with asset_id field applied on open finding.
    No findings found for the asset.

    Setup:
    1. Insert one ignore rule of type 'exclude' by asset into the database.
    2. Insert findings with random asset_id into the database.

    Test:
    Call the 'apply_ignore_rule_created_on_findings' handler

    Assert:
    1. No findings should be affected
    2. No side effects should be triggered, no findings were affected
    """
    tenant_id = '19881e72-6d3b-49df-b79f-298ad89b8056'
    control_name = 'control_name'
    asset_id = '19881e72-1234-49df-b79f-298ad89b8056'
    ignore_rule = build_asset_id_ignore_rule_dict(asset_id=asset_id, tenant_id=tenant_id)

    mocked_event = {
        'detail': {
            **ignore_rule
        },
    }

    mongo_client = mock_mongo_driver(mocker)
    mocked_ignore_rules_collection = mongo_client.ignore_rules
    mocked_findings_collection = mongo_client.findings
    # Setup: 1. insert one ignore rule to DB
    mocked_ignore_rules_collection.insert_one(ignore_rule)
    # Setup: 2 Insert random findings for the tenant with different asset_ids to make sure they are not affected
    random_findings_in_db = [
        build_finding_dict(
            finding_id=f"finding_id-{i}",
            fingerprint=f"fingerprint-{i}",
            tenant_id=tenant_id,
            with_specs=True,
            asset_id=str(uuid4()),
            control_name=control_name,
            test_id=f"test_id-{i}",
            issue_text=random_string(),  # This is to make sure that the findings are not identical
            fix_suggestion=None,
        )
        for i in range(10)
    ]
    mocked_findings_collection.insert_many(random_findings_in_db)

    # Mock the creation of the 'IgnoreRuleCreatedSideEffectsQueue' sqs queue
    mock_sqs_queue(queue_name=IGNORE_RULE_UPSERTED_SIDE_EFFECTS_QUEUE_NAME)

    apply_ignore_rule_created_on_findings(mocked_event, Context())

    # Assert: No findings should be affected
    findings_from_db = mocked_findings_collection.find({})
    for finding in findings_from_db:
        assert not finding['ignored']
        assert not finding['ignore_rules_ids']
        assert not finding['specs'][0]['v']

    # No side effects should be triggered, no findings were affected
    apply_ignore_rule_created_on_findings(mocked_event, Context())
    assert_queue_content(
        queue_name=IGNORE_RULE_UPSERTED_SIDE_EFFECTS_QUEUE_NAME,
        expected_messages=[]
    )


@mock_sqs
def test_apply_ignore_rule_on_findings_with_filename_regex(mocked_tables, mocker, env_variables):
    """
    Test the 'apply_ignore_rule_created_on_findings' handler.
    Ignore rule of type 'exclude' with filename regex applied on open finding.
    Only the finding with a filename that matches the regex should be ignored.

    Setup:
    1. Insert one ignore rule of type 'exclude' by filename into the database.
    2. Insert two findings: one with a filename that matches the regex, and one that does not.

    Test:
    Call the 'apply_ignore_rule_created_on_findings' handler.

    Assert:
    1. The finding with the matching filename should be updated to ignored=True.
    2. The finding without a matching filename should remain unaffected.
    3. The IgnoreRuleCreatedSideEffectsOnFindings message should be sent to the queue
    """
    tenant_id = '19881e72-6d3b-49df-b79f-298ad89b8056'
    matching_filename = 'matching_filename.txt'
    non_matching_filename = 'completely-unrelated-file.txt'
    filename_regex = 'matching_filename*'

    ignore_rule = build_filename_ignore_rule_dict(tenant_id=tenant_id, filename_regex=filename_regex)

    mocked_event = {
        'detail': {
            'tenant_id': tenant_id,
            **ignore_rule
        },
    }

    mongo_client = mock_mongo_driver(mocker)
    mocked_findings_collection = mongo_client.findings

    # Setup: 1. insert two findings to DB, one matching the filename pattern and one not
    finding_matching = build_finding_dict(tenant_id=tenant_id, finding_id=str(uuid4()), fix_suggestion=None,
                                          filename=matching_filename, with_specs=True)
    finding_non_matching = build_finding_dict(tenant_id=tenant_id, finding_id=str(uuid4()),
                                              fix_suggestion=None, filename=non_matching_filename, with_specs=True)

    mocked_findings_collection.insert_many([finding_matching, finding_non_matching])

    # Mock the creation of the 'IgnoreRuleCreatedSideEffectsQueue' sqs queue
    mock_sqs_queue(queue_name=IGNORE_RULE_UPSERTED_SIDE_EFFECTS_QUEUE_NAME)
    # Act
    apply_ignore_rule_created_on_findings(mocked_event, Context())

    finding_updated = mocked_findings_collection.find_one({'id': finding_matching['id']})
    assert finding_updated['ignored'] is True

    finding_not_updated = mocked_findings_collection.find_one({'id': finding_non_matching['id']})
    assert finding_not_updated['ignored'] is False

    # Assert: 3. The IgnoreRuleCreatedSideEffectsOnFindings message should be sent to the queue
    expected_message = IgnoreRuleUpsertedSideEffectsOnFindings(
        tenant_id=tenant_id,
        ignore_rule=ignore_rule,
        total_effected_findings_count=1
    )
    assert_queue_content(
        queue_name=IGNORE_RULE_UPSERTED_SIDE_EFFECTS_QUEUE_NAME,
        expected_messages=[expected_message.dict()],
    )


@mock_sqs
def test_apply_ignore_rule_on_findings_with_asset_and_filename_regex(mocked_tables, mocker, env_variables):
    """
    Test the 'apply_ignore_rule_created_on_findings' handler.
    Ignore rule of type 'exclude' with filename regex and asset_id applied on open finding.
    Only the finding with a filename that matches the regex and asset_id should be ignored.

    Setup:
    1. Insert one ignore rule of type 'exclude' by filename & asset_id into the database.
    2. Insert 3 findings: one with a filename and asset_id that matches the regex,
                          one with a filename that matches the regex but asset_id that does not,
                            and one with a filename that does not match the regex but asset_id that does.
    Test:
    Call the 'apply_ignore_rule_created_on_findings' handler.

    Assert:
    1. The finding with the matching filename and asset_id should be updated to ignored=True.
    2. The finding without a matching filename & asset_id should remain unaffected.
    3. The IgnoreRuleCreatedSideEffectsOnFindings message should be sent to the queue
    """
    tenant_id = '19881e72-6d3b-49df-b79f-298ad89b8056'
    matching_filename = 'matching_filename.txt'
    non_matching_filename = 'completely-unrelated-file.txt'
    filename_regex = 'matching_filename*'
    matching_asset_id = str(uuid4())
    non_matching_asset_id = str(uuid4())

    fields: List[FieldToBeIgnoredBy] = [
        FieldToBeIgnoredBy(name="filename", value=filename_regex, operator=OperatorTypes.REGEX),
        FieldToBeIgnoredBy(name="asset_id", value=matching_asset_id)
    ]

    ignore_rule = build_ignore_rule_dict_by_fields(tenant_id=tenant_id,
                                                   fields=fields)

    mocked_event = {
        'detail': {
            'tenant_id': tenant_id,
            **ignore_rule
        },
    }

    mongo_client = mock_mongo_driver(mocker)
    mocked_findings_collection = mongo_client.findings

    # Setup: 1. insert 3 findings to DB, one matching the filters and two not matching
    finding_matching = build_finding_dict(tenant_id=tenant_id, finding_id=str(uuid4()), fix_suggestion=None,
                                          filename=matching_filename, with_specs=True,
                                          asset_id=matching_asset_id)
    finding_non_matching_1 = build_finding_dict(tenant_id=tenant_id, finding_id=str(uuid4()),
                                                asset_id=matching_asset_id,
                                                fix_suggestion=None, filename=non_matching_filename, with_specs=True)
    finding_non_matching_2 = build_finding_dict(tenant_id=tenant_id, finding_id=str(uuid4()),
                                                asset_id=non_matching_asset_id,
                                                fix_suggestion=None, filename=matching_filename, with_specs=True)

    mocked_findings_collection.insert_many([finding_matching, finding_non_matching_1, finding_non_matching_2])
    # Mock the creation of the 'IgnoreRuleCreatedSideEffectsQueue' sqs queue
    mock_sqs_queue(queue_name=IGNORE_RULE_UPSERTED_SIDE_EFFECTS_QUEUE_NAME)
    # Act
    apply_ignore_rule_created_on_findings(mocked_event, Context())

    finding_updated = mocked_findings_collection.find_one({'id': finding_matching['id']})
    assert finding_updated['ignored'] is True

    finding_not_updated_1 = mocked_findings_collection.find_one({'id': finding_non_matching_1['id']})
    assert finding_not_updated_1['ignored'] is False

    finding_not_updated_2 = mocked_findings_collection.find_one({'id': finding_non_matching_2['id']})
    assert finding_not_updated_2['ignored'] is False

    # Assert: 3. The IgnoreRuleCreatedSideEffectsOnFindings message should be sent to the queue
    expected_message = IgnoreRuleUpsertedSideEffectsOnFindings(
        tenant_id=tenant_id,
        ignore_rule=ignore_rule,
        total_effected_findings_count=1
    )
    assert_queue_content(
        queue_name=IGNORE_RULE_UPSERTED_SIDE_EFFECTS_QUEUE_NAME,
        expected_messages=[expected_message.dict()],
    )


@mock_sqs
def test_apply_ignore_rule_on_findings_with_asset_filename_and_test_id(mocked_tables, mocker, env_variables):
    """
    Test the 'apply_ignore_rule_created_on_findings' handler.
    Ignore rule of type 'ignore' with filename, asset_id, and test_id applied on open finding.
    Only the finding with a filename, asset_id, and test_id that matches the given values should be ignored.

    Setup:
    1. Insert one ignore rule of type 'exclude' by filename, asset_id & test_id into the database.
    2. Insert 3 findings: one with a filename, asset_id, and test_id that matches the values,
                          one with a filename and asset_id that matches the values but test_id that does not,
                          one with a filename and test_id that matches the values but asset_id that does not.
                          and one with a filename that does not match the values but asset_id and test_id that do.
    Test:
    Call the 'apply_ignore_rule_created_on_findings' handler.

    Assert:
    1. The finding with the matching filename, asset_id, and test_id should be updated to ignored=True.
    2. The finding without a matching filename, asset_id & test_id should remain unaffected.
    3. The IgnoreRuleCreatedSideEffectsOnFindings message should be sent to the queue
    """
    tenant_id = '19881e72-6d3b-49df-b79f-298ad89b8056'
    matching_filename = 'matching_filename.txt'
    non_matching_filename = 'completely-unrelated-file.txt'
    matching_asset_id = str(uuid4())
    non_matching_asset_id = str(uuid4())
    matching_test_id = 'matching_test_id'
    non_matching_test_id = 'non_matching_test_id'

    fields: List[FieldToBeIgnoredBy] = [
        FieldToBeIgnoredBy(name="filename", value=matching_filename),
        FieldToBeIgnoredBy(name="asset_id", value=matching_asset_id),
        FieldToBeIgnoredBy(name="test_id", value=matching_test_id)
    ]

    ignore_rule = build_ignore_rule_dict_by_fields(tenant_id=tenant_id,
                                                   fields=fields)

    mocked_event = {
        'detail': {
            'tenant_id': tenant_id,
            **ignore_rule
        },
    }

    mongo_client = mock_mongo_driver(mocker)
    mocked_findings_collection = mongo_client.findings

    # Setup: 1. insert 3 findings to DB, one matching the filters and two not matching
    finding_matching = build_finding_dict(tenant_id=tenant_id, finding_id=str(uuid.uuid4()), fix_suggestion=None,
                                          filename=matching_filename, with_specs=True,
                                          asset_id=matching_asset_id, test_id=matching_test_id)
    finding_non_matching_1 = build_finding_dict(tenant_id=tenant_id, finding_id=str(uuid.uuid4()),
                                                asset_id=matching_asset_id,
                                                filename=matching_filename,
                                                test_id=non_matching_test_id)
    finding_non_matching_2 = build_finding_dict(tenant_id=tenant_id, finding_id=str(uuid.uuid4()),
                                                asset_id=non_matching_asset_id,
                                                fix_suggestion=None, filename=matching_filename,
                                                test_id=matching_test_id)
    findig_non_matching_3 = build_finding_dict(tenant_id=tenant_id, finding_id=str(uuid.uuid4()),
                                               asset_id=matching_asset_id,
                                               filename=non_matching_filename,
                                               test_id=matching_test_id)

    mocked_findings_collection.insert_many([finding_matching, finding_non_matching_1, finding_non_matching_2,
                                            findig_non_matching_3])
    # Mock the creation of the 'IgnoreRuleCreatedSideEffectsQueue' sqs queue
    mock_sqs_queue(queue_name=IGNORE_RULE_UPSERTED_SIDE_EFFECTS_QUEUE_NAME)
    # Act
    apply_ignore_rule_created_on_findings(mocked_event, Context())

    finding_updated = mocked_findings_collection.find_one({'id': finding_matching['id']})
    assert finding_updated['ignored'] is True

    finding_not_updated_1 = mocked_findings_collection.find_one({'id': finding_non_matching_1['id']})
    assert finding_not_updated_1['ignored'] is False

    finding_not_updated_2 = mocked_findings_collection.find_one({'id': finding_non_matching_2['id']})
    assert finding_not_updated_2['ignored'] is False

    finding_not_updated_3 = mocked_findings_collection.find_one({'id': findig_non_matching_3['id']})
    assert finding_not_updated_3['ignored'] is False

    # Assert: 3. The IgnoreRuleCreatedSideEffectsOnFindings message should be sent to the queue
    expected_message = IgnoreRuleUpsertedSideEffectsOnFindings(
        tenant_id=tenant_id,
        ignore_rule=ignore_rule,
        total_effected_findings_count=1
    )
    assert_queue_content(
        queue_name=IGNORE_RULE_UPSERTED_SIDE_EFFECTS_QUEUE_NAME,
        expected_messages=[expected_message.dict()],
    )


@mock_sqs
def test_apply_ignore_rule_on_findings_with_test_id(mocked_tables, mocker, env_variables):
    """
    Test the 'apply_ignore_rule_created_on_findings' handler.
    Ignore rule of type 'ignore' with test_id applied on open finding.
    Only the finding with a test_id that matches the given value should be ignored.

    Setup:
    1. Insert one ignore rule of type 'ignore' by test_id into the database.
    2. Insert 3 findings: one with a test_id that matches the value, and two that do not.
    Test:
    Call the 'apply_ignore_rule_created_on_findings' handler.

    Assert:
    1. The finding with the matching test_id should be updated to ignored=True.
    2. The findings without a matching test_id should remain unaffected.
    3. The IgnoreRuleCreatedSideEffectsOnFindings message should be sent to the queue
    """
    tenant_id = '19881e72-6d3b-49df-b79f-298ad89b8056'
    matching_test_id = 'matching_test_id'
    non_matching_test_id_1 = 'non_matching_test_id_1'
    non_matching_test_id_2 = 'non_matching_test_id_2'

    fields: List[FieldToBeIgnoredBy] = [
        FieldToBeIgnoredBy(name="test_id", value=matching_test_id)
    ]

    ignore_rule = build_ignore_rule_dict_by_fields(tenant_id=tenant_id,
                                                   fields=fields)

    mocked_event = {
        'detail': {
            'tenant_id': tenant_id,
            **ignore_rule
        },
    }

    mongo_client = mock_mongo_driver(mocker)
    mocked_findings_collection = mongo_client.findings

    # Setup: 1. insert 3 findings to DB, one matching the filters and two not matching
    finding_matching = build_finding_dict(tenant_id=tenant_id, finding_id=str(uuid.uuid4()), fix_suggestion=None,
                                          filename='some_filename.txt', with_specs=True,
                                          asset_id=str(uuid.uuid4()), test_id=matching_test_id)
    finding_non_matching_1 = build_finding_dict(tenant_id=tenant_id, finding_id=str(uuid.uuid4()),
                                                asset_id=str(uuid.uuid4()),
                                                filename='some_filename.txt',
                                                test_id=non_matching_test_id_1)
    finding_non_matching_2 = build_finding_dict(tenant_id=tenant_id, finding_id=str(uuid.uuid4()),
                                                asset_id=str(uuid.uuid4()), fix_suggestion=None,
                                                filename='some_filename.txt',
                                                test_id=non_matching_test_id_2)

    mocked_findings_collection.insert_many([finding_matching, finding_non_matching_1, finding_non_matching_2])

    # Mock the creation of the 'IgnoreRuleCreatedSideEffectsQueue' sqs queue
    mock_sqs_queue(queue_name=IGNORE_RULE_UPSERTED_SIDE_EFFECTS_QUEUE_NAME)
    # Act
    apply_ignore_rule_created_on_findings(mocked_event, Context())

    finding_updated = mocked_findings_collection.find_one({'id': finding_matching['id']})
    assert finding_updated['ignored'] is True

    finding_not_updated_1 = mocked_findings_collection.find_one({'id': finding_non_matching_1['id']})
    assert finding_not_updated_1['ignored'] is False

    finding_not_updated_2 = mocked_findings_collection.find_one({'id': finding_non_matching_2['id']})
    assert finding_not_updated_2['ignored'] is False

    # Assert: 3. The IgnoreRuleCreatedSideEffectsOnFindings message should be sent to the queue
    expected_message = IgnoreRuleUpsertedSideEffectsOnFindings(
        tenant_id=tenant_id,
        ignore_rule=ignore_rule,
        total_effected_findings_count=1
    )
    assert_queue_content(
        queue_name=IGNORE_RULE_UPSERTED_SIDE_EFFECTS_QUEUE_NAME,
        expected_messages=[expected_message.dict()],
    )

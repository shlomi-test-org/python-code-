from aws_lambda_typing.context import Context
from pydantic import BaseModel
from src.handlers.findings.apply_ignore_rule_on_findings import apply_ignore_rule_deleted_on_findings
from tests.component.ignore_rules.utils import (build_filename_ignore_rule_dict,
                                                build_fingerprint_ignore_rule_dict,
                                                build_asset_id_ignore_rule_dict)
from tests.component.utils.mock_mongo_driver import mock_mongo_driver
from tests.fixtures import build_finding_dict
from test_utils.aws.mock_eventbridge import mock_eventbridge
from jit_utils.models.findings.entities import Finding, Resolution
from copy import deepcopy


class UpdateResult(BaseModel):
    matched_count: int
    modified_count: int


def test_apply_ignore_rule_deleted_on_findings(mocked_tables, mocker, env_variables):
    tenant_id = '19881e72-6d3b-49df-b79f-298ad89b8056'
    fingerprint = 'fingerprint'
    asset_id = '19881e72-1234-49df-b79f-298ad89b8056'
    finding_id = '5c481b2c-aaf1-4289-b2ac-3ddc79bc0196'
    ignore_rule_id = "e6390f00-19ac-4a6e-9f4a-c0616cb94528"
    now_string = "2022-01-14T00:00:00.000000"
    control_name = 'control_name'

    finding = build_finding_dict(tenant_id=tenant_id, fingerprint=fingerprint,
                                 asset_id=asset_id, finding_id=finding_id, ignore_rules_ids=[ignore_rule_id],
                                 ignored=True,
                                 with_specs=True,
                                 control_name=control_name)
    ignore_rule = build_fingerprint_ignore_rule_dict(asset_id=asset_id,
                                                     ignore_rule_id=ignore_rule_id,
                                                     control_name=control_name,
                                                     fingerprint=fingerprint)

    mocked_event = {
        'detail': {
            'tenant_id': tenant_id,
            **ignore_rule
        },
    }

    mongo_client = mock_mongo_driver(mocker)
    mocked_findings_collection = mongo_client.findings
    mocked_findings_collection.insert_one(finding)

    # Mock mongomock update_many method, because it does not support
    # passing of aggregation pipeline (list of dicts, it only supports dict)
    def custom_update_many(filter, update, upsert=False, array_filters=None):
        assert filter == {'fingerprint': fingerprint, 'tenant_id': tenant_id,
                          'ignore_rules_ids': {'$in': [ignore_rule.get('id')]}}
        # Update the finding
        finding_to_update = mocked_findings_collection.find({'fingerprint': fingerprint})[0]
        # deepcopy the specs
        specs = deepcopy(finding_to_update['specs'])
        specs[0]['v'] = False
        mocked_findings_collection.update_one(finding_to_update, {
            '$set': {
                'ignore_rules_ids': [], 'ignored': False,
                'specs': specs,
            }
        })
        return UpdateResult(matched_count=1, modified_count=1)

    # Patch the update_many method
    mocker.patch.object(mocked_findings_collection, 'update_many', side_effect=custom_update_many)
    # Setup: 3. Mock create 'findings' event bus
    with mock_eventbridge(bus_name='findings') as get_sent_events:
        # Test: 1. Call 'apply_ignore_rule_deleted_on_findings' handler
        apply_ignore_rule_deleted_on_findings(mocked_event, Context())

        sent_messages = get_sent_events()
        assert len(sent_messages) == 2
        # Assert: 3. 'findings-updates' Event sent to eventbridge.
        finding_object = Finding(**finding)
        finding_object.ignore_rules_ids.remove(ignore_rule_id)
        finding_object.ignored = False
        finding_object.modified_at = now_string
        finding_object.resolution = 'OPEN'

        assert sent_messages[1]['source'] == 'finding-service'
        assert sent_messages[1]['detail-type'] == 'findings-updated'
        assert sent_messages[1]['detail'] == {'tenant_id': tenant_id,
                                              'findings': [{**(finding_object.dict())}],
                                              'is_backlog': False, 'event_id': sent_messages[1]['detail']['event_id'],
                                              'inner_use_case': 'delete-ignore-rules', 'total_batches': 1,
                                              'batch_number': 1}

        # Assert: 4. 'FindingUpdated' Event sent to eventbridge.
        assert sent_messages[0]['source'] == 'finding-service'
        assert sent_messages[0]['detail-type'] == 'FindingUpdated'

        assert sent_messages[0]['detail'] == {
            'prev_resolution': 'IGNORED',
            'new_resolution': 'OPEN',
            'tenant_id': tenant_id,
            'fix_suggestion_source': 'control',
            'plan_items': ['dummy-plan-item'],
            'finding_id': finding_id,
            'has_fix_suggestion': True,
            'is_backlog': finding['backlog'],
            'asset_id': asset_id,
            'asset_name': finding['asset_name'],
            'jit_event_id': finding['jit_event_id'],
            'jit_event_name': finding['jit_event_name'],
            'control_name': finding['control_name'],
            'plan_layer': finding['plan_layer'],
            'test_id': 'B105',
            'vulnerability_type': finding['vulnerability_type'],
            'timestamp': '2022-01-14 00:00:00',
            'created_at': finding['created_at'],
            'duration_minutes': 0.0,
            'priority_factors': finding['priority_factors'],
            'priority_score': finding['priority_score'],
            'asset_priority_score': finding['asset_priority_score'],
        }

        # Assert: 5. Finding is updated in DB
        updated_finding = mocked_findings_collection.find({'fingerprint': fingerprint})[0]
        assert updated_finding['ignore_rules_ids'] == []
        assert updated_finding['ignored'] is False
        assert updated_finding['resolution'] == 'OPEN'


def test_apply_ignore_rule_deleted_on_findings__ignore_rule_already_deleted_from_finding(mocked_tables, mocker,
                                                                                         env_variables):
    tenant_id = '19881e72-6d3b-49df-b79f-298ad89b8056'
    fingerprint = 'fingerprint'
    asset_id = '19881e72-1234-49df-b79f-298ad89b8056'
    finding_id = '5c481b2c-aaf1-4289-b2ac-3ddc79bc0196'

    finding = build_finding_dict(tenant_id=tenant_id, fingerprint=fingerprint,
                                 asset_id=asset_id, finding_id=finding_id, ignore_rules_ids=[],
                                 ignored=True,
                                 with_specs=True)
    ignore_rule = build_fingerprint_ignore_rule_dict(asset_id=asset_id,
                                                     fingerprint=fingerprint)

    mocked_event = {
        'detail': {
            'tenant_id': tenant_id,
            **ignore_rule
        },
    }

    mongo_client = mock_mongo_driver(mocker)
    mocked_findings_collection = mongo_client.findings
    mocked_findings_collection.insert_one(finding)

    # Mock mongomock update_many method, because it does not support
    # passing of aggregation pipeline (list of dicts, it only supports dict)
    def custom_update_many(filter, update, upsert=False, array_filters=None):
        return UpdateResult(matched_count=0, modified_count=0)

    # Patch the update_many method
    mocker.patch.object(mocked_findings_collection, 'update_many', side_effect=custom_update_many)
    # Setup: 3. Mock create 'findings' event bus
    with mock_eventbridge(bus_name='findings') as get_sent_events:
        # Test: 1. Call 'apply_ignore_rule_deleted_on_findings' handler
        apply_ignore_rule_deleted_on_findings(mocked_event, Context())

        sent_messages = get_sent_events()
        assert len(sent_messages) == 0


def test_apply_ignore_rule_deleted_on_findings_with_more_than_one_ignore_rule(mocked_tables, mocker,
                                                                              env_variables):
    """
    Test remove specific ignore rule from a finding with multiple ignore rules
    Setup:
        1) Store a finding with more than one ignore rule
        2) Mock a specific ignore rule to be deleted

    Test:
        1) Call 'apply_ignore_rule_deleted_on_findings' handler with the mocked ignore rule
    Assert:
        1) The specified ignore rule is removed from the finding
        2) The finding is correctly updated in the database
        3) An event with the updated finding is sent to eventbridge
        4) An event of type 'FindingUpdated' is not sent to eventbridge (since the finding remains ignored)
    """

    tenant_id = '19881e72-6d3b-49df-b79f-298ad89b8056'
    fingerprint = 'fingerprint'
    asset_id = '19881e72-1234-49df-b79f-298ad89b8056'
    finding_id = '5c481b2c-aaf1-4289-b2ac-3ddc79bc0196'
    ignore_rule_id = "e6390f00-19ac-4a6e-9f4a-c0616cb94528"
    ignore_rule_id_2 = "e6390f00-19ac-4a6e-9f4a-c0616cb94529"
    now_string = "2022-01-14T00:00:00.000000"
    control_name = 'control_name'

    finding = build_finding_dict(tenant_id=tenant_id, fingerprint=fingerprint,
                                 asset_id=asset_id, finding_id=finding_id,
                                 ignore_rules_ids=[ignore_rule_id, ignore_rule_id_2],
                                 ignored=True,
                                 with_specs=True,
                                 control_name=control_name)
    ignore_rule = build_fingerprint_ignore_rule_dict(asset_id=asset_id,
                                                     ignore_rule_id=ignore_rule_id,
                                                     control_name=control_name,
                                                     fingerprint=fingerprint)

    mocked_event = {
        'detail': {
            'tenant_id': tenant_id,
            **ignore_rule
        },
    }

    mongo_client = mock_mongo_driver(mocker)
    mocked_findings_collection = mongo_client.findings
    mocked_findings_collection.insert_one(finding)

    # Mock mongomock update_many method, because it does not support
    # passing of aggregation pipeline (list of dicts, it only supports dict)
    def custom_update_many(filter, update, upsert=False, array_filters=None):
        assert filter == {'fingerprint': fingerprint, 'tenant_id': tenant_id,
                          'ignore_rules_ids': {'$in': [ignore_rule.get('id')]}}
        # Update the finding
        finding_to_update = mocked_findings_collection.find({'fingerprint': fingerprint})[0]
        # deepcopy the specs
        specs = deepcopy(finding_to_update['specs'])
        specs[0]['v'] = False
        mocked_findings_collection.update_one(finding_to_update, {
            '$set': {
                'ignore_rules_ids': [ignore_rule_id_2], 'ignored': True,
                'specs': specs,
            }
        })
        return UpdateResult(matched_count=1, modified_count=1)

    # Patch the update_many method
    mocker.patch.object(mocked_findings_collection, 'update_many', side_effect=custom_update_many)
    # Setup: 3. Mock create 'findings' event bus
    with mock_eventbridge(bus_name='findings') as get_sent_events:
        # Test: 1. Call 'apply_ignore_rule_deleted_on_findings' handler
        apply_ignore_rule_deleted_on_findings(mocked_event, Context())

        sent_messages = get_sent_events()
        assert len(sent_messages) == 1
        # Assert: 3. 'findings-updates' Event sent to eventbridge.
        finding_object = Finding(**finding)
        finding_object.ignore_rules_ids.remove(ignore_rule_id)
        finding_object.ignored = True
        finding_object.modified_at = now_string
        finding_object.resolution = 'IGNORED'

        assert sent_messages[0]['source'] == 'finding-service'
        assert sent_messages[0]['detail-type'] == 'findings-updated'
        assert sent_messages[0]['detail'] == {'tenant_id': tenant_id,
                                              'findings': [{**(finding_object.dict())}],
                                              'is_backlog': False, 'event_id': sent_messages[0]['detail']['event_id'],
                                              'inner_use_case': 'delete-ignore-rules', 'total_batches': 1,
                                              'batch_number': 1}

        # FindingUpdated from ignored to ignored event shouldn't be sent
        # Assert: 5. Finding is updated in DB
        updated_finding = mocked_findings_collection.find({'fingerprint': fingerprint})[0]
        assert updated_finding['ignore_rules_ids'] == [ignore_rule_id_2]
        assert updated_finding['ignored'] is True
        assert updated_finding['resolution'] == 'OPEN'


def test_apply_ignore_rule_type_exclude_deleted_on_findings(mocked_tables, mocker, env_variables):
    """
      Test remove ignore rule of type 'exclude' by asset_id from a finding
      Setup:
          1) Store a finding with ignore rule
          2) Mock a specific ignore rule of type excluded to be deleted

      Test:
          1) Call 'apply_ignore_rule_deleted_on_findings' handler with the mocked ignore rule
      Assert:
          1) The specified ignore rule is removed from the finding
          2) The finding is correctly updated in the database
          3) No events are sent to eventbridge
          4) The finding remains with resolution 'INACTIVE'

      """

    tenant_id = '19881e72-6d3b-49df-b79f-298ad89b8056'
    fingerprint = 'fingerprint'
    asset_id = '19881e72-1234-49df-b79f-298ad89b8056'
    finding_id = '5c481b2c-aaf1-4289-b2ac-3ddc79bc0196'
    ignore_rule_id = "e6390f00-19ac-4a6e-9f4a-c0616cb94528"
    control_name = 'control_name'

    finding = build_finding_dict(tenant_id=tenant_id, fingerprint=fingerprint,
                                 asset_id=asset_id, finding_id=finding_id, ignore_rules_ids=[ignore_rule_id],
                                 ignored=True,
                                 with_specs=True,
                                 control_name=control_name,
                                 resolution=Resolution.INACTIVE)
    ignore_rule = build_asset_id_ignore_rule_dict(asset_id=asset_id, tenant_id=tenant_id)

    mocked_event = {
        'detail': {
            'tenant_id': tenant_id,
            **ignore_rule
        },
    }

    mongo_client = mock_mongo_driver(mocker)
    mocked_findings_collection = mongo_client.findings
    mocked_findings_collection.insert_one(finding)

    # Mock mongomock update_many method, because it does not support
    # passing of aggregation pipeline (list of dicts, it only supports dict)
    def custom_update_many(filter, update, upsert=False, array_filters=None):
        assert filter == {'asset_id': asset_id, 'tenant_id': tenant_id,
                          'ignore_rules_ids': {'$in': [ignore_rule.get('id')]}}
        # Update the finding
        finding_to_update = mocked_findings_collection.find({'fingerprint': fingerprint})[0]
        # deepcopy the specs
        specs = deepcopy(finding_to_update['specs'])
        specs[0]['v'] = False
        mocked_findings_collection.update_one(finding_to_update, {
            '$set': {
                'ignore_rules_ids': [], 'ignored': False,
                'specs': specs,
            }
        })
        return UpdateResult(matched_count=1, modified_count=1)

    # Patch the update_many method
    mocker.patch.object(mocked_findings_collection, 'update_many', side_effect=custom_update_many)
    # Setup: 3. Mock create 'findings' event bus
    with mock_eventbridge(bus_name='findings') as get_sent_events:
        # Test: 1. Call 'apply_ignore_rule_deleted_on_findings' handler
        apply_ignore_rule_deleted_on_findings(mocked_event, Context())

        sent_messages = get_sent_events()
        assert len(sent_messages) == 0

        # Assert: 5. Finding is updated in DB
        updated_finding = mocked_findings_collection.find({'asset_id': asset_id})[0]
        assert updated_finding['ignore_rules_ids'] == []
        assert updated_finding['ignored'] is False
        assert updated_finding['resolution'] == Resolution.INACTIVE


def test_filename_ignore_rule_deleted_on_findings(mocked_tables, mocker, env_variables):
    tenant_id = '19881e72-6d3b-49df-b79f-298ad89b8056'
    filename_regex = 'matching_file*'
    filename = 'matching_file_example.txt'
    finding_id = '5c481b2c-aaf1-4289-b2ac-3ddc79bc0196'

    # Build the ignore rule with filename regex
    ignore_rule = build_filename_ignore_rule_dict(tenant_id, filename_regex)

    # Create a finding with a filename that matches the ignore rule
    finding = build_finding_dict(tenant_id=tenant_id, finding_id=finding_id,
                                 ignored=True, filename=filename,
                                 ignore_rules_ids=[ignore_rule['id']],
                                 with_specs=True)

    mocked_event = {
        'detail': {
            'tenant_id': tenant_id,
            **ignore_rule
        },
    }

    mongo_client = mock_mongo_driver(mocker)
    mocked_findings_collection = mongo_client.findings
    mocked_findings_collection.insert_one(finding)

    def custom_update_many(filter, update, upsert=False, array_filters=None):
        finding_to_update = mocked_findings_collection.find_one(filter)
        if finding_to_update:
            mocked_findings_collection.update_one({'id': finding_to_update['id']}, {
                '$set': {
                    'ignore_rules_ids': [],
                    'ignored': False,
                }
            })
            return UpdateResult(matched_count=1, modified_count=1)
        else:
            return UpdateResult(matched_count=0, modified_count=0)

    mocker.patch.object(mocked_findings_collection, 'update_many', side_effect=custom_update_many)

    with mock_eventbridge(bus_name='findings'):
        apply_ignore_rule_deleted_on_findings(mocked_event, Context())

        updated_finding = mocked_findings_collection.find_one({'_id': finding['_id']})
        assert updated_finding['ignore_rules_ids'] == []
        assert updated_finding['ignored'] is False

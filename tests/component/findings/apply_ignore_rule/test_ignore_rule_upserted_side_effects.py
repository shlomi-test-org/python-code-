import json
from typing import Dict

from aws_lambda_typing.context import Context
from datetime import datetime, timedelta
from uuid import uuid4

from moto import mock_sqs
from moto.config.models import random_string

from src.handlers.ignore_rules.handle_ignore_rule_upserted_side_effects import handler
from src.lib.constants import IGNORE_RULE_UPSERTED_SIDE_EFFECTS_QUEUE_NAME
from src.lib.findings_utils import FindingsInnerUseCase
from src.lib.models.events import IgnoreRuleUpsertedSideEffectsOnFindings
from tests.component.ignore_rules.utils import (
    build_fingerprint_ignore_rule_dict,
    build_asset_id_ignore_rule_dict, build_plan_items_ignore_rule_dict)
from tests.component.utils.assert_queue_content import assert_queue_content
from tests.component.utils.mock_mongo_driver import mock_mongo_driver
from tests.component.utils.mock_sqs_queue import mock_sqs_queue
from tests.fixtures import build_finding_dict
from test_utils.aws.mock_eventbridge import mock_eventbridge
from jit_utils.models.findings.entities import Finding, Resolution, UiResolution


def mock_sqs_evnet(body: Dict):
    return {
        "Records": [
            {
                "body": json.dumps(body),

            }
        ]
    }


def test_handle_ignore_rule_create_side_effects(mocked_tables, mocker, env_variables):
    """
    Setup:
    1. Insert one finding into the database.

    Test:
    Call the 'handle_ignore_rule_create_side_effects' handler.

    Assert:
    1. A 'findings-updated' event should be sent to the EventBridge.
    2. A 'FindingUpdated' event should be sent to the EventBridge.
    """
    tenant_id = '19881e72-6d3b-49df-b79f-298ad89b8056'
    fingerprint = 'fingerprint'
    control_name = 'control_name'
    asset_id = '19881e72-1234-49df-b79f-298ad89b8056'
    finding_id = '5c481b2c-aaf1-4289-b2ac-3ddc79bc0196'
    yesterday_date = datetime.utcnow() - timedelta(days=1)
    ignore_rule = build_fingerprint_ignore_rule_dict(asset_id=asset_id,
                                                     control_name='control_name',
                                                     fingerprint=fingerprint)

    mongo_client = mock_mongo_driver(mocker)

    # Setup: 1. insert one ignored finding to DB
    finding = build_finding_dict(tenant_id=tenant_id, fingerprint=fingerprint,
                                 asset_id=asset_id, finding_id=finding_id,
                                 control_name=control_name,
                                 ignore_rules_ids=[ignore_rule.get('id')],
                                 ignored=True,
                                 modified_at=datetime.utcnow().isoformat(),
                                 created_at=yesterday_date.isoformat(),
                                 fix_suggestion=None,
                                 with_specs=True)
    # Setup: 2. insert one not related finding to DB
    finding_2 = build_finding_dict(tenant_id=tenant_id, fingerprint="fingerprint-2",
                                   asset_id=asset_id, finding_id="finding_id-2",
                                   control_name=control_name,
                                   ignored=True,
                                   modified_at=datetime.utcnow().isoformat(),
                                   created_at=yesterday_date.isoformat(),
                                   fix_suggestion=None,
                                   with_specs=True)

    mocked_findings_collection = mongo_client.findings
    mocked_findings_collection.insert_one(finding)
    mocked_findings_collection.insert_one(finding_2)

    # Mock event body
    event_body = IgnoreRuleUpsertedSideEffectsOnFindings(
        tenant_id=tenant_id,
        ignore_rule=ignore_rule,
        total_effected_findings_count=1
    )
    sqs_event = mock_sqs_evnet(event_body.dict())
    # Mock the creation of the 'findings' event bus
    with mock_eventbridge(bus_name='findings') as get_sent_events:
        mock_sqs_queue(queue_name=IGNORE_RULE_UPSERTED_SIDE_EFFECTS_QUEUE_NAME)

        # Act
        handler(sqs_event, Context())

        sent_messages = get_sent_events()
        assert len(sent_messages) == 2
        # Assert: 3. 'findings-updates' Event sent to eventbridge.
        finding_object = Finding(**finding)
        finding_object.modified_at = datetime.utcnow().isoformat()

        assert sent_messages[1]['source'] == 'finding-service'
        assert sent_messages[1]['detail-type'] == 'findings-updated'
        assert sent_messages[1]['detail'] == {'tenant_id': tenant_id,
                                              'findings': [{**(finding_object.dict()), 'resolution': 'IGNORED'}],
                                              'is_backlog': False, 'event_id': sent_messages[1]['detail']['event_id'],
                                              'inner_use_case': 'add-ignore-rules', 'total_batches': 1,
                                              'batch_number': 1}

        # Assert: 4. 'FindingUpdated' Event sent to eventbridge.
        assert sent_messages[0]['source'] == 'finding-service'
        assert sent_messages[0]['detail-type'] == 'FindingUpdated'
        assert sent_messages[0]['detail'] == {
            'new_resolution': 'IGNORED',
            'tenant_id': tenant_id,
            'duration_minutes': 1440.0,
            'fix_suggestion_source': 'na',
            'plan_items': ['dummy-plan-item'],
            'finding_id': finding_id,
            'has_fix_suggestion': False,
            'asset_id': asset_id,
            'test_id': 'B105',
            'timestamp': '2022-01-14 00:00:00',

            'prev_resolution': finding['resolution'].value,
            'is_backlog': finding['backlog'],
            'asset_name': finding['asset_name'],
            'jit_event_id': finding['jit_event_id'],
            'jit_event_name': finding['jit_event_name'],
            'control_name': finding['control_name'],
            'plan_layer': finding['plan_layer'],
            'vulnerability_type': finding['vulnerability_type'],
            'created_at': finding['created_at'],
            'priority_factors': finding['priority_factors'],
            'priority_score': finding['priority_score'],
            'asset_priority_score': finding['asset_priority_score'],
        }


def test_apply_ignore_rule_create_side_effects__finding_already_ignored(mocked_tables, mocker, env_variables):
    """
    Setup:
    1. Insert one ignored finding into the database.

    Test:
    Call the 'handle_ignore_rule_create_side_effects' handler.

    Assert:
    1. A 'findings-updated' event should be sent to the EventBridge.
    2. A 'FindingUpdated' event should not be sent the finding remains ignored.
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
                                                     modified_at=now_string,
                                                     fingerprint=fingerprint)
    mongo_client = mock_mongo_driver(mocker)

    # Setup: 1. insert one finding to DB
    finding = build_finding_dict(tenant_id=tenant_id, fingerprint=fingerprint,
                                 asset_id=asset_id, finding_id=finding_id,
                                 created_at=yesterday_date.isoformat(),
                                 ignored=True,
                                 with_specs=True,
                                 control_name=control_name,
                                 fix_suggestion=None,
                                 modified_at=(datetime.utcnow() - timedelta(days=1)).isoformat(),
                                 ignore_rules_ids=[mocked_existing_ignore_rule_id, ignore_rule.get('id')])

    mocked_findings_collection = mongo_client.findings
    mocked_ignore_rules_collection = mongo_client.ignore_rules

    mocked_ignore_rules_collection.insert_one(ignore_rule)
    mocked_findings_collection.insert_one(finding)
    # Mock event body
    event_body = IgnoreRuleUpsertedSideEffectsOnFindings(
        tenant_id=tenant_id,
        ignore_rule=ignore_rule,
        total_effected_findings_count=1
    )
    sqs_event = mock_sqs_evnet(event_body.dict())

    # Mock the creation of the 'findings' event bus
    with mock_eventbridge(bus_name='findings') as get_sent_events:
        mock_sqs_queue(queue_name=IGNORE_RULE_UPSERTED_SIDE_EFFECTS_QUEUE_NAME)

        handler(sqs_event, Context())

        sent_messages = get_sent_events()
        assert len(sent_messages) == 1
        # Assert: 3. 'findings-updated' Event
        finding_object = Finding(**finding)

        assert sent_messages[0]['source'] == 'finding-service'
        assert sent_messages[0]['detail-type'] == 'findings-updated'
        assert sent_messages[0]['detail'] == {'tenant_id': tenant_id,
                                              'findings': [{**(finding_object.dict()), 'resolution': 'IGNORED'}],
                                              'is_backlog': False, 'event_id': sent_messages[0]['detail']['event_id'],
                                              'inner_use_case': 'add-ignore-rules', 'total_batches': 1,
                                              'batch_number': 1}


def test_apply_ignore_rule_create_side_effects_asset_excluded_type_on_findings(mocked_tables, mocker, env_variables):
    """
    Ignore rule  of type 'exclude' with asset_id field applied on open finding.

    Setup:
    1. Insert findings with random asset_ids.
    2. Insert one related finding with the same asset_id

    Test:
    Call the 'handle_ignore_rule_create_side_effects' handler.

    Assert:
    1. A 'findings-deleted' event should be sent to the EventBridge,
       the findings previous resolution should be 'OPEN'.
    2. A 'FindingDeleted' event should be sent to the EventBridge.
    """
    tenant_id = '19881e72-6d3b-49df-b79f-298ad89b8056'
    fingerprint = 'fingerprint'
    control_name = 'control_name'
    asset_id = '19881e72-1234-49df-b79f-298ad89b8056'
    finding_id = '5c481b2c-aaf1-4289-b2ac-3ddc79bc0196'
    yesterday_date = datetime.utcnow() - timedelta(days=1)
    ignore_rule = build_asset_id_ignore_rule_dict(asset_id=asset_id, tenant_id=tenant_id)

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

    # Setup: 3. Insert one inactive ignored finding that was effected by the ignore rule with the same asset_id
    finding = build_finding_dict(tenant_id=tenant_id, fingerprint=fingerprint,
                                 asset_id=asset_id, finding_id=finding_id,
                                 control_name=control_name,
                                 created_at=yesterday_date.isoformat(),
                                 resolution=Resolution.INACTIVE,
                                 ignored=True,
                                 ignore_rules_ids=[ignore_rule.get('id')],
                                 fix_suggestion=None,
                                 modified_at=datetime.utcnow().isoformat(),
                                 with_specs=True)
    mocked_findings_collection.insert_one(finding)

    # Mock event body
    event_body = IgnoreRuleUpsertedSideEffectsOnFindings(
        tenant_id=tenant_id,
        ignore_rule=ignore_rule,
        total_effected_findings_count=1
    )
    sqs_event = mock_sqs_evnet(event_body.dict())

    # Mock the creation of the 'findings' event bus
    with mock_eventbridge(bus_name='findings') as get_sent_events:
        mock_sqs_queue(queue_name=IGNORE_RULE_UPSERTED_SIDE_EFFECTS_QUEUE_NAME)

        handler(sqs_event, Context())

        sent_messages = get_sent_events()
        assert len(sent_messages) == 2
        finding_object = Finding(**finding)

        # Assert: 1. 'FindingDeleted' Event sent to eventbridge.
        assert sent_messages[0]['source'] == 'finding-service'
        assert sent_messages[0]['detail-type'] == 'FindingDeleted'
        assert sent_messages[0]['detail'] == {
            'prev_resolution': UiResolution.OPEN,
            'new_resolution': None,
            'has_fix_suggestion': False,
            'fix_suggestion_source': 'na',
            'tenant_id': '19881e72-6d3b-49df-b79f-298ad89b8056',
            'finding_id': '5c481b2c-aaf1-4289-b2ac-3ddc79bc0196',
            'is_backlog': False,
            'asset_id': '19881e72-1234-49df-b79f-298ad89b8056',
            'asset_name': 'repo-name',
            'jit_event_id': 'my-event-id',
            'jit_event_name': 'item_activated',
            'control_name': 'control_name',
            'plan_layer': 'code',
            'plan_items': ['dummy-plan-item'],
            'vulnerability_type': 'code_vulnerability',
            'timestamp': '2022-01-14 00:00:00',
            'created_at': '2022-01-13T00:00:00',
            'test_id': 'B105',
            'duration_minutes': 1440.0,
            'priority_factors': finding['priority_factors'],
            'priority_score': finding['priority_score'],
            'asset_priority_score': finding['asset_priority_score'],
        }

        # Assert: 2. 'finding-deleted' Event sent to eventbridge.
        assert sent_messages[1]['source'] == 'finding-service'
        assert sent_messages[1]['detail-type'] == 'findings-deleted'
        assert sent_messages[1]['detail'] == {'tenant_id': tenant_id,
                                              'findings': [finding_object.dict()],
                                              'is_backlog': False, 'event_id': sent_messages[1]['detail']['event_id'],
                                              'inner_use_case': 'delete-findings', 'total_batches': 1,
                                              'batch_number': 1}


def test_apply_ignore_rule_create_side_effects_findings_with_plan_items(mocked_tables, mocker, env_variables):
    """
    Test the "apply_ignore_rule_updated_on_findings" handler.
    Ignore rule of type "exclude" with plan_items applied on open findings.
    Only the finding with a plan_items that are sub-set of the value should be ignored.

    Setup:
    2. Insert findings: 4 of them should be ignored -
       * 3 ignored by the current ignore rule change
       * 1 ignored by a previous ignore rule change

    Test:
    Call the "apply_ignore_rule_updated_on_findings" handler.

    Assert:
    1. 'findings-deleted' event should be sent to the EventBridge.
    2. 'FindingDeleted' events should be sent to the EventBridge - for newly ignored findings.
    """
    tenant_id = str(uuid4())
    now = datetime.utcnow().isoformat()
    ignore_rule = build_plan_items_ignore_rule_dict(tenant_id=tenant_id, plan_items=["p1", "p2"],
                                                    modified_at=now)
    few_days_ago = datetime.utcnow() - timedelta(days=5)
    event_body = IgnoreRuleUpsertedSideEffectsOnFindings(
        tenant_id=tenant_id,
        ignore_rule=ignore_rule,
        total_effected_findings_count=3
    )
    sqs_event = mock_sqs_evnet(event_body.dict())

    mongo_client = mock_mongo_driver(mocker)
    mocked_findings_collection = mongo_client.findings

    ignore_1 = build_finding_dict(tenant_id=tenant_id, with_specs=True, plan_items=["p1"], ignored=True,
                                  modified_at=now,
                                  resolution=Resolution.INACTIVE, ignore_rules_ids=[ignore_rule.get('id')])
    ignore_2 = build_finding_dict(tenant_id=tenant_id, with_specs=True, plan_items=["p2"], ignored=True,
                                  modified_at=now,
                                  resolution=Resolution.INACTIVE, ignore_rules_ids=[ignore_rule.get('id')])
    ignore_3 = build_finding_dict(tenant_id=tenant_id, with_specs=True, plan_items=["p1", "p2"], ignored=True,
                                  modified_at=now,
                                  resolution=Resolution.INACTIVE, ignore_rules_ids=[ignore_rule.get('id')])
    previously_ignored = build_finding_dict(tenant_id=tenant_id, with_specs=True, plan_items=["p1"], ignored=True,
                                            modified_at=few_days_ago.isoformat(),
                                            resolution=Resolution.INACTIVE, ignore_rules_ids=[ignore_rule.get('id')])

    not_ignore_1 = build_finding_dict(tenant_id=tenant_id, with_specs=True, plan_items=["p1", "p3"], ignored=False)
    not_ignore_2 = build_finding_dict(tenant_id=tenant_id, with_specs=True, plan_items=["p1", "p2", "p3"],
                                      ignored=False)

    mocked_findings_collection.insert_many(
        [ignore_1, ignore_2, ignore_3, previously_ignored, not_ignore_1, not_ignore_2])

    with mock_eventbridge(bus_name="findings") as get_sent_events:
        # Mock the creation of the 'IgnoreRuleCreatedSideEffectsQueue' sqs queue
        mock_sqs_queue(queue_name=IGNORE_RULE_UPSERTED_SIDE_EFFECTS_QUEUE_NAME)

        handler(sqs_event, {})

        sent_messages = get_sent_events()
        assert len(sent_messages) == 4

        for i in range(0, 3):
            assert sent_messages[i]["source"] == "finding-service"
            assert sent_messages[i]["detail-type"] == "FindingDeleted"
            assert sent_messages[i]["detail"]["prev_resolution"] == Resolution.OPEN
            assert sent_messages[i]["detail"]["new_resolution"] is None

        assert sent_messages[3]["source"] == "finding-service"
        assert sent_messages[3]["detail-type"] == "findings-deleted"
        assert sent_messages[3]["detail"]["tenant_id"] == tenant_id
        assert sent_messages[3]["detail"]["is_backlog"] is False
        assert sent_messages[3]["detail"]["inner_use_case"] == FindingsInnerUseCase.DELETE_FINDINGS
        assert sent_messages[3]["detail"]["total_batches"] == 1
        assert sent_messages[3]["detail"]["batch_number"] == 1
        findings = sent_messages[3]["detail"]["findings"]
        assert sorted([f["id"] for f in findings]) == sorted(
            [ignore_1["id"], ignore_2["id"], ignore_3["id"], previously_ignored["id"]])
        assert [f["resolution"] for f in findings] == [Resolution.INACTIVE] * 4
        assert sorted([f["plan_items"] for f in findings]) == sorted([["p1"], ["p1"], ["p2"], ["p1", "p2"]])


def setup_findings(mocked_findings_collection, tenant_id, control_name, asset_id, ignore_rule):
    # Insert random findings for the tenant with different asset_ids
    random_findings_in_db = [
        build_finding_dict(
            finding_id=f"finding_id-{i}",
            fingerprint=f"fingerprint-{i}",
            tenant_id=tenant_id,
            asset_id=str(uuid4()),
            control_name=control_name,
            test_id=f"test_id-{i}",
            issue_text=random_string(),  # Ensure findings are not identical
            fix_suggestion=None,
        )
        for i in range(10)
    ]

    # Insert findings with the same asset_id
    asset_findings_in_db = [
        build_finding_dict(
            finding_id=f"finding_id-{i}",
            fingerprint=f"fingerprint-{i}",
            tenant_id=tenant_id,
            asset_id=asset_id,
            control_name=control_name,
            test_id=f"test_id-{i}",
            issue_text=random_string(),  # Ensure findings are not identical
            ignored=True,
            resolution=Resolution.INACTIVE,
            modified_at=datetime.utcnow().isoformat(),
            ignore_rules_ids=[ignore_rule.get('id')],
            created_at="2023-03-26T06:09:03.063186"
        )
        for i in range(10, 20)
    ]
    mocked_findings_collection.insert_many(random_findings_in_db)
    mocked_findings_collection.insert_many(asset_findings_in_db)


@mock_sqs
def test_ignore_rule_exclude_type_requires_multiple_invocations_to_process_findings(
        mocked_tables, mocker, env_variables):
    """
    Test the side effects of creating an ignore rule of type 'exclude' on findings with a specific asset_id,
    simulating the scenario where multiple invocations are needed to fetch and process all findings.

    Setup:
    1. Insert findings with random asset_ids.
    2. Insert findings with the same asset_id and mark them as ignored.

    Test:
    1. Call the 'handle_ignore_rule_create_side_effects' handler.
    2. Simulate continuation by invoking the handler again with the next page key.

    Assert:
    1. Six events should be sent to EventBridge: five 'FindingDeleted' events and one 'findings-deleted' event.
    2. The 'IgnoreRuleCreatedSideEffectsOnFindings' message should be sent to the SQS queue after the first invocation.
    3. The queue should be empty after the second invocation.
    """
    tenant_id = '19881e72-6d3b-49df-b79f-298ad89b8056'
    control_name = 'control_name'
    asset_id = '19881e72-1234-49df-b79f-298ad89b8056'
    now = datetime.utcnow().isoformat()
    ignore_rule = build_asset_id_ignore_rule_dict(asset_id=asset_id, tenant_id=tenant_id, modified_at=now)

    mongo_client = mock_mongo_driver(mocker)
    mocked_findings_collection = mongo_client.findings

    def run_test_and_assertions(expected_message):
        with mock_eventbridge(bus_name='findings') as get_sent_events:
            mock_sqs_queue(queue_name=IGNORE_RULE_UPSERTED_SIDE_EFFECTS_QUEUE_NAME)
            mocker.patch('src.lib.ignore_rules.ignore_rule_upserted_side_effects.FETCH_FINDINGS_FOR_SIDE_EFFECTS_LIMIT',
                         5)

            sqs_event = mock_sqs_evnet(expected_message.dict())
            handler(sqs_event, Context())

            sent_messages = get_sent_events()
            assert len(sent_messages) == 6

            # Assert: 'FindingDeleted' Events sent to EventBridge
            for message in sent_messages[:5]:
                assert message['source'] == 'finding-service'
                assert message['detail-type'] == 'FindingDeleted'

            # Assert: 'findings-deleted' Event sent to EventBridge
            assert sent_messages[5]['source'] == 'finding-service'
            assert sent_messages[5]['detail-type'] == 'findings-deleted'

            return expected_message

    # Setup findings in the database
    setup_findings(mocked_findings_collection, tenant_id, control_name, asset_id, ignore_rule)

    # First run
    event_body = IgnoreRuleUpsertedSideEffectsOnFindings(tenant_id=tenant_id,
                                                         ignore_rule=ignore_rule,
                                                         total_effected_findings_count=10)
    expected_message = IgnoreRuleUpsertedSideEffectsOnFindings(
        tenant_id=tenant_id,
        ignore_rule=ignore_rule,
        total_effected_findings_count=10,
        next_page_key="ZmluZGluZ19pZC0xNSMyMDIzLTAzLTI2VDA2OjA5OjAzLjA2MzE4Ng==",
        invocation_count=1
    )

    run_test_and_assertions(event_body)

    # Assert: The IgnoreRuleCreatedSideEffectsOnFindings message should be sent to the queue
    assert_queue_content(
        queue_name=IGNORE_RULE_UPSERTED_SIDE_EFFECTS_QUEUE_NAME,
        expected_messages=[expected_message.dict()]
    )

    # Second run (continuation)
    run_test_and_assertions(expected_message)

    # Assert: The queue should be empty after the second invocation
    assert_queue_content(
        queue_name=IGNORE_RULE_UPSERTED_SIDE_EFFECTS_QUEUE_NAME,
        expected_messages=[]
    )


@mock_sqs
def test_ignore_rule_exclude_type_requires_multiple_invocations_to_process_findings_reached_limit(
        mocked_tables, mocker, env_variables):
    """
    Test the side effects of creating an ignore rule of type 'exclude' on findings with a specific asset_id,
    simulating the scenario where the invocation limit is reached, should stop processing findings.

    Setup:
    1. Insert findings with random asset_ids.
    2. Insert findings with the same asset_id and mark them as ignored.

    Test:
    1. Call the 'handle_ignore_rule_create_side_effects' handler.

    Assert:
    1. The queue should be empty after the invocation.
    """
    tenant_id = '19881e72-6d3b-49df-b79f-298ad89b8056'
    control_name = 'control_name'
    asset_id = '19881e72-1234-49df-b79f-298ad89b8056'
    ignore_rule = build_asset_id_ignore_rule_dict(asset_id=asset_id, tenant_id=tenant_id)

    mongo_client = mock_mongo_driver(mocker)
    mocked_findings_collection = mongo_client.findings

    # Setup findings in the database
    setup_findings(mocked_findings_collection, tenant_id, control_name, asset_id, ignore_rule)

    message = IgnoreRuleUpsertedSideEffectsOnFindings(
        tenant_id=tenant_id,
        ignore_rule=ignore_rule,
        total_effected_findings_count=5,
        invocation_count=2
    )

    # Run (continuation)
    with mock_eventbridge(bus_name='findings'):
        mock_sqs_queue(queue_name=IGNORE_RULE_UPSERTED_SIDE_EFFECTS_QUEUE_NAME)
        mocker.patch('src.lib.ignore_rules.ignore_rule_upserted_side_effects.FETCH_FINDINGS_FOR_SIDE_EFFECTS_LIMIT', 5)
        mocker.patch('src.lib.ignore_rules.ignore_rule_upserted_side_effects.'
                     'INVOCATION_BUFFER_COUNT', 0)

        sqs_event = mock_sqs_evnet(message.dict())
        handler(sqs_event, Context())

    # Assert: The queue should be empty after the second invocation
    assert_queue_content(
        queue_name=IGNORE_RULE_UPSERTED_SIDE_EFFECTS_QUEUE_NAME,
        expected_messages=[]
    )

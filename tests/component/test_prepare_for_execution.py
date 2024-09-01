# flake8: noqa E501
import copy
import time
from datetime import datetime
from typing import Dict

import freezegun
import pytest
import responses
from jit_utils.aws_clients.sfn import StepFunctionEvent
from jit_utils.event_models import CodeRelatedJitEvent, JitEvent
from jit_utils.event_models.trigger_event import BulkTriggerSchemeEvent, BulkTriggerExecutionEvent
from jit_utils.models.trigger.jit_event_life_cycle import JitEventStatus
from pydantic import parse_obj_as
from test_utils.aws.mock_eventbridge import mock_eventbridge

from src.handlers.prepare_for_execution import handler
from src.lib.constants import JIT_EVENTS_WITH_DIFF_BASED_ENRICHMENT, TRIGGER_EXECUTION_BUS_NAME, JIT_EVENT_TTL, \
    JIT_EVENT_LIFE_CYCLE_EVENT_BUS_NAME
from src.lib.data.jit_event_life_cycle_table import JitEventLifeCycleManager
from src.lib.models.jit_event_life_cycle import JitEventAssetDBEntity
from src.lib.models.trigger import PrepareForExecutionEventWithEnrichedData, ModeledEnrichedData
from tests.component.conftest import FREEZE_TIME, FROZEN_TIME, setup_jit_event_life_cycle_in_db
from tests.component.utils.mock_responses import mock_plan_service_api
from tests.component.utils.mock_responses.mock_authentication_service import mock_get_internal_token_api
from tests.component.utils.mocks.mocks import (
    PREPARE_EXECUTION_SCHEME_MESSAGE__ITEM_ACTIVATED,
    PREPARE_EXECUTION_EVENT_OUTPUT__ITEM_ACTIVATED, PREPARE_EXECUTION_EVENT_INPUT__NEW_RUNNER_FORMAT_ITEM_ACTIVATED,
    PREPARE_EXECUTION_SCHEME_MESSAGE__NEW_RUNNER_FORMAT_ITEM_ACTIVATED,
    PREPARE_EXECUTION_EVENT_OUTPUT__NEW_RUNNER_FORMAT_ITEM_ACTIVATED,
    PREPARE_FOR_EXECUTION_EVENT__PR_CREATED__ENRICHED_WITHOUT_PULUMI,
    TRIGGER_EXECUTION_EVENT__PR_CREATED__ENRICHED_WITHOUT_PULUMI, PREPARE_EXECUTION_EVENT_INPUT__ITEM_ACTIVATED,
    PREPARE_FOR_EXECUTION_EVENT__PR_CREATED__ENRICHED_WITH_PULUMI, SCHEME_EVENT__PR_CREATED__ENRICHED_WITH_PULUMI,
    TRIGGER_EXECUTION_EVENT__PR_CREATED__ENRICHED_WITH_PULUMI,
    PREPARE_FOR_EXECUTION_EVENT__PLAN_ITEM_ADDED,
    SCHEME_EVENT__PLAN_ITEM_ADDED, TRIGGER_EXECUTION_EVENT__PLAN_ITEM_ADDED,
    SCHEME_EVENT__PR_CREATED__ENRICHED_WITHOUT_PULUMI, PREPARE_FOR_EXECUTION_MANUAL_EXECUTION_EVENT_CLOUD_CONTROL,
    PREPARE_FOR_EXECUTION_EVENT__DUPLICATION_EXECUTIONS)
from tests.conftest import mock_config_file


def get_number_of_calls_to_get_centralized_metadata(input_jit_event: JitEvent, expected_executions) -> int:
    if isinstance(input_jit_event, CodeRelatedJitEvent):
        return 0
    else:
        return len(expected_executions)


@pytest.mark.parametrize("prepare_for_execution_event_with_enriched_data,"
                         " expected_scheme_event,"
                         " expected_trigger_executions_event",
                         [
                             (
                                     PREPARE_FOR_EXECUTION_EVENT__PR_CREATED__ENRICHED_WITHOUT_PULUMI,
                                     SCHEME_EVENT__PR_CREATED__ENRICHED_WITHOUT_PULUMI,
                                     TRIGGER_EXECUTION_EVENT__PR_CREATED__ENRICHED_WITHOUT_PULUMI,
                             ),
                             (
                                     PREPARE_EXECUTION_EVENT_INPUT__ITEM_ACTIVATED,
                                     PREPARE_EXECUTION_SCHEME_MESSAGE__ITEM_ACTIVATED,
                                     PREPARE_EXECUTION_EVENT_OUTPUT__ITEM_ACTIVATED,
                             ),
                             (
                                     PREPARE_EXECUTION_EVENT_INPUT__NEW_RUNNER_FORMAT_ITEM_ACTIVATED,
                                     PREPARE_EXECUTION_SCHEME_MESSAGE__NEW_RUNNER_FORMAT_ITEM_ACTIVATED,
                                     PREPARE_EXECUTION_EVENT_OUTPUT__NEW_RUNNER_FORMAT_ITEM_ACTIVATED,
                             ),
                             (
                                     PREPARE_FOR_EXECUTION_EVENT__PR_CREATED__ENRICHED_WITH_PULUMI,
                                     SCHEME_EVENT__PR_CREATED__ENRICHED_WITH_PULUMI,
                                     TRIGGER_EXECUTION_EVENT__PR_CREATED__ENRICHED_WITH_PULUMI,
                             ),
                             (
                                     PREPARE_FOR_EXECUTION_EVENT__PLAN_ITEM_ADDED,
                                     SCHEME_EVENT__PLAN_ITEM_ADDED,
                                     TRIGGER_EXECUTION_EVENT__PLAN_ITEM_ADDED,
                             ),
                             (
                                     PREPARE_FOR_EXECUTION_EVENT__PLAN_ITEM_ADDED,
                                     SCHEME_EVENT__PLAN_ITEM_ADDED,
                                     TRIGGER_EXECUTION_EVENT__PLAN_ITEM_ADDED,
                             ),
                             (  # This is a case study that tests removal of executions duplication by workflow slug
                                     PREPARE_FOR_EXECUTION_EVENT__DUPLICATION_EXECUTIONS,
                                     SCHEME_EVENT__PLAN_ITEM_ADDED,
                                     TRIGGER_EXECUTION_EVENT__PLAN_ITEM_ADDED,
                             ),
                         ])
@responses.activate
@freezegun.freeze_time(FREEZE_TIME)
def test_prepare_for_execution(
        prepare_for_execution_event_with_enriched_data: PrepareForExecutionEventWithEnrichedData,
        expected_scheme_event: Dict,
        expected_trigger_executions_event: Dict,
        mock_get_configuration_file_for_tenant,
        mock_get_integration_file_for_tenant,
        dynamodb_table_mocks,
        jit_event_life_cycle_manager: JitEventLifeCycleManager,
):
    setup_jit_event_life_cycle_in_db(
        jit_event_life_cycle_manager,
        prepare_for_execution_event_with_enriched_data.prepare_for_execution_event.jit_event
    )
    event: StepFunctionEvent = StepFunctionEvent(
        step_input=prepare_for_execution_event_with_enriched_data,
        state_machine_execution_id="state_machine_execution_id",
    )
    expected_number_of_calls = get_number_of_calls_to_get_centralized_metadata(
        input_jit_event=prepare_for_execution_event_with_enriched_data.prepare_for_execution_event.jit_event,
        expected_executions=expected_trigger_executions_event["executions"]
    )
    tenant_id = prepare_for_execution_event_with_enriched_data.prepare_for_execution_event.jit_event.tenant_id
    mock_response = mock_plan_service_api.mock_get_centralized_repo_files_metadata(tenant_id)
    for job in prepare_for_execution_event_with_enriched_data.prepare_for_execution_event.filtered_jobs:
        plan_item_slugs = [] if job.job_name == "enrich" else [job.plan_item_slug]
        mock_plan_service_api.mock_get_scopes_api(job.workflow_slug, job.job_name, plan_item_slugs)

    with mock_eventbridge(
            bus_name=[
                TRIGGER_EXECUTION_BUS_NAME,
                JIT_EVENT_LIFE_CYCLE_EVENT_BUS_NAME]) as get_events:
        response = handler(event.dict(), {})

        jit_event_life_cycle_table, enrichment_results_table = dynamodb_table_mocks
        # Assert EnrichmentResultsItem is created in DB with the correct values
        enrichment_results_scan = enrichment_results_table.scan()
        prepare_event = prepare_for_execution_event_with_enriched_data.prepare_for_execution_event
        if prepare_event.should_enrich \
                and prepare_event.jit_event.jit_event_name not in JIT_EVENTS_WITH_DIFF_BASED_ENRICHMENT:
            assert len(enrichment_results_scan["Items"]) == 2
            for item in enrichment_results_scan["Items"]:
                assert item["tenant_id"] == prepare_event.asset.tenant_id
                assert item["vendor"] == prepare_event.asset.vendor
                assert item["owner"] == prepare_event.asset.owner
                assert item["repo"] == prepare_event.asset.asset_name
                assert item["enrichment_results"] == prepare_event.enriched_data
                assert item["jit_event_id"] == prepare_event.jit_event.jit_event_id
                assert item["jit_event_name"] == prepare_event.jit_event.jit_event_name
                if "created_at" in item:
                    assert (
                        f"VENDOR#{prepare_event.asset.vendor}#OWNER#{prepare_event.asset.owner}"
                        f"#REPO#{prepare_event.asset.asset_name}#CREATED_AT#"
                    ) in item["SK"]
                if "modified_at" in item:
                    assert item["SK"] == (
                        f"VENDOR#{prepare_event.asset.vendor}#OWNER#{prepare_event.asset.owner}"
                        f"#REPO#{prepare_event.asset.asset_name}"
                    )
        else:
            assert len(enrichment_results_scan["Items"]) == 0

        # Assert jit event life cycle asset is created in DB with the correct values
        jit_event_table_scan = jit_event_life_cycle_table.scan()
        assert len(jit_event_table_scan["Items"]) == 2
        db_item = JitEventAssetDBEntity(**jit_event_table_scan["Items"][1])
        assert db_item.tenant_id == prepare_event.jit_event.tenant_id
        assert db_item.jit_event_id == prepare_event.jit_event.jit_event_id
        assert db_item.asset_id == prepare_event.asset.asset_id
        assert datetime.fromisoformat(db_item.created_at).strftime('%Y-%m-%d %H:%M:%S') == FREEZE_TIME
        assert db_item.ttl == int(time.mktime(FROZEN_TIME.timetuple())) + JIT_EVENT_TTL  # TTL according to FREEZE_TIME
        assert db_item.total_jobs == len(expected_trigger_executions_event["executions"])
        assert db_item.remaining_jobs == len(expected_trigger_executions_event["executions"])
        # messages for create pipelines
        enriched_data = prepare_for_execution_event_with_enriched_data.enriched_data
        scheme_messages = get_events[TRIGGER_EXECUTION_BUS_NAME]()
        if enriched_data:
            assert len(scheme_messages) == 2
            assert scheme_messages[1]["detail"] == expected_scheme_event
        else:
            assert len(scheme_messages) == 0
            # verify jit event life cycle bus has request complete if there are no executions to run
            jit_event_life_cycle_events = get_events[JIT_EVENT_LIFE_CYCLE_EVENT_BUS_NAME]()
            assert len(jit_event_life_cycle_events) == 1
            assert jit_event_life_cycle_events[0]["detail"]["status"] == JitEventStatus.COMPLETED
        # Assert trigger executions messages are not sent in the new flow
        assert get_events[TRIGGER_EXECUTION_BUS_NAME]() == []
        # Assert handler response is identical to the expected trigger executions event
        expected_trigger_executions_event = modify_expected_result(expected_trigger_executions_event)

        # In the past this test used to compare 2 huge dictionaries (13kb), so with minimum time invested I changed
        # the assertions to be per key, so if the test fails we will know which key is the problem
        assert response['tenant_id'] == expected_trigger_executions_event['tenant_id']
        assert response['jit_event_name'] == expected_trigger_executions_event['jit_event_name']
        for i in range(len(expected_trigger_executions_event['executions'])):
            enrichment_result = parse_obj_as(ModeledEnrichedData,
                                             response['executions'][i]['context'].get('enrichment_result'))
            assert enrichment_result == parse_obj_as(ModeledEnrichedData, enriched_data)
            assert response['executions'][i]['job_name'] == expected_trigger_executions_event['executions'][i][
                'job_name']
            assert response['executions'][i]['steps'] == expected_trigger_executions_event['executions'][i]['steps']

            assert response['executions'][i]['context']['auth'] == \
                   expected_trigger_executions_event['executions'][i]['context']['auth']
            assert response['executions'][i]['context']['jit_event'] == \
                   expected_trigger_executions_event['executions'][i]['context']['jit_event']
            assert response['executions'][i]['context']['asset']['asset_id'] == \
                   expected_trigger_executions_event['executions'][i]['context']['asset']['asset_id']
            assert response['executions'][i]['context']['installation']['installation_id'] == \
                   expected_trigger_executions_event['executions'][i]['context']['installation']['installation_id']
            assert response['executions'][i]['context']['config'] == \
                   expected_trigger_executions_event['executions'][i]['context']['config']
            assert response['executions'][i]['context']['job'] == \
                   expected_trigger_executions_event['executions'][i]['context']['job']
            assert response['executions'][i]['context']['centralized'] == \
                   expected_trigger_executions_event['executions'][i]['context']['centralized']
            assert response['executions'][i]['context']['workflow'] == \
                   expected_trigger_executions_event['executions'][i]['context']['workflow']

            assert response['executions'][i]['plan_slug'] == expected_trigger_executions_event['executions'][i][
                'plan_slug']
            assert response['executions'][i]['plan_item_slug'] == expected_trigger_executions_event['executions'][i][
                'plan_item_slug']
            assert sorted(response['executions'][i]['affected_plan_items']) == sorted(
                expected_trigger_executions_event['executions'][i]['affected_plan_items'])
            assert response['executions'][i]['workflow_slug'] == expected_trigger_executions_event['executions'][i][
                'workflow_slug']
            assert response['executions'][i]['job_runner'] == expected_trigger_executions_event['executions'][i][
                'job_runner']
            assert response['executions'][i]['inputs'] == expected_trigger_executions_event['executions'][i]['inputs']

            assert response['executions'][i]['control_type'] == expected_trigger_executions_event['executions'][i][
                'control_type']

        assert mock_response.call_count == expected_number_of_calls


@responses.activate
def test_prepare_for_execution__assert_pipeline_events(dynamodb_table_mocks):
    ### Prepare the event ###
    prepare_for_execution_event = copy.deepcopy(PREPARE_FOR_EXECUTION_MANUAL_EXECUTION_EVENT_CLOUD_CONTROL)
    prepare_for_execution_event.filtered_jobs.append(copy.deepcopy(prepare_for_execution_event.filtered_jobs[0]))
    prepare_for_execution_event.filtered_jobs.append(copy.deepcopy(prepare_for_execution_event.filtered_jobs[0]))
    prepare_for_execution_event.filtered_jobs.append(copy.deepcopy(prepare_for_execution_event.filtered_jobs[0]))
    prepare_for_execution_event.filtered_jobs.append(copy.deepcopy(prepare_for_execution_event.filtered_jobs[0]))
    ### Jobs without pipeline - 3 ###
    prepare_for_execution_event.filtered_jobs[0].job_name = "software-bill-of-materials"
    prepare_for_execution_event.filtered_jobs[1].job_name = "reporter"
    prepare_for_execution_event.filtered_jobs[2].job_name = "enrich"
    ### Jobs with pipeline - 2 ###
    prepare_for_execution_event.filtered_jobs[3].job_name = "sast"
    prepare_for_execution_event.filtered_jobs[4].job_name = "remediation"

    for job in prepare_for_execution_event.filtered_jobs:
        mock_plan_service_api.mock_get_scopes_api(
            job.workflow_slug, job.job_name, ["item-lejljflsjk"]
        )

    ### Mock API calls ###
    mock_get_internal_token_api()
    mock_plan_service_api.mock_get_configuration_file_api()
    mock_plan_service_api.mock_get_integration_file_api()
    mock_plan_service_api.mock_get_centralized_repo_files_metadata(prepare_for_execution_event.jit_event.tenant_id)

    ### Call the lambda and validate ###
    event: StepFunctionEvent = StepFunctionEvent(
        step_input=prepare_for_execution_event,
        state_machine_execution_id="state_machine_execution_id",
    )
    with mock_eventbridge(bus_name=[TRIGGER_EXECUTION_BUS_NAME,
                                    JIT_EVENT_LIFE_CYCLE_EVENT_BUS_NAME]) as get_events:
        response = handler(event.dict(), {})
        trigger_executions_event = BulkTriggerExecutionEvent(**response)
        assert len(trigger_executions_event.executions) == 5
        scheme_messages = get_events[TRIGGER_EXECUTION_BUS_NAME]()
        sent_trigger_schemes = BulkTriggerSchemeEvent(**scheme_messages[1]["detail"])
        assert sent_trigger_schemes.trigger_schemes[0].event_execution_scheme.amount_of_triggered_jobs == 2


@responses.activate
def test_prepare_for_execution__assert_no_pipeline_events(dynamodb_table_mocks):
    ### Prepare the event ###
    prepare_for_execution_event = copy.deepcopy(PREPARE_FOR_EXECUTION_MANUAL_EXECUTION_EVENT_CLOUD_CONTROL)
    ### Jobs without pipeline - 1 ###
    prepare_for_execution_event.filtered_jobs[0].job_name = "repository-software-bill-of-materials"

    mock_plan_service_api.mock_get_scopes_api(
        prepare_for_execution_event.filtered_jobs[0].workflow_slug,
        prepare_for_execution_event.filtered_jobs[0].job_name,
        ["item-software-bill-of-materials"],
    )

    ### Mock API calls ###
    mock_get_internal_token_api()
    mock_plan_service_api.mock_get_configuration_file_api()
    mock_plan_service_api.mock_get_integration_file_api()
    mock_plan_service_api.mock_get_centralized_repo_files_metadata(prepare_for_execution_event.jit_event.tenant_id)

    ### Call the lambda and validate ###
    event: StepFunctionEvent = StepFunctionEvent(
        step_input=prepare_for_execution_event,
        state_machine_execution_id="state_machine_execution_id",
    )
    with mock_eventbridge(bus_name=[TRIGGER_EXECUTION_BUS_NAME,
                                    JIT_EVENT_LIFE_CYCLE_EVENT_BUS_NAME]) as get_events:
        response = handler(event.dict(), {})
        trigger_executions_event = BulkTriggerExecutionEvent(**response)
        assert len(trigger_executions_event.executions) == 1
        scheme_messages = get_events[TRIGGER_EXECUTION_BUS_NAME]()
        assert len(scheme_messages) == 1  # Only the metrics event is expected


def modify_expected_result(expected_trigger_executions_event: Dict) -> Dict:
    for execution in expected_trigger_executions_event["executions"]:
        # edit the expected configuration in the context
        config = mock_config_file()
        config["applications"][0]["application_name"] = execution["context"]["asset"]["asset_name"]
        config["applications"][0]["type"] = execution["context"]["asset"]["asset_type"]
        execution["context"]["config"] = config
        execution["context"]["job"]["integrations"] = None

    return expected_trigger_executions_event


def remove_created_at_fields(event: Dict):
    """
    Remove all the "created_at" field from a nested dict.
    Support dictionary changed size during iteration
    """
    if isinstance(event, dict):
        for key in list(event.keys()):
            if key == "created_at":
                del event[key]
            else:
                remove_created_at_fields(event[key])
    elif isinstance(event, list):
        for item in event:
            remove_created_at_fields(item)
    return event

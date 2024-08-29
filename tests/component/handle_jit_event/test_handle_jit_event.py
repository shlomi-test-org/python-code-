import json
import time
from datetime import datetime
from typing import List, Dict, Optional
from unittest.mock import MagicMock

import freezegun
import pytest
from jit_utils.event_models.common import TriggerFilterAttributes, JitEvent
from jit_utils.models.asset.entities import Asset, LimitedAsset
from jit_utils.models.execution_context import RunnerConfig
from jit_utils.models.plan.plan_file import FullPlanContent
from jit_utils.models.plan.template import WorkflowTemplate
from jit_utils.models.tenant.entities import Installation
from jit_utils.models.trigger.jit_event_life_cycle import JitEventStatus
from jit_utils.models.oauth.entities import VendorEnum
from pydantic import parse_obj_as
from pytest_mock import MockerFixture
from responses import activate
from test_utils.aws.mock_eventbridge import mock_eventbridge

from src.handlers.handle_jit_event import handler, fetch_jit_event_resources_handler, \
    run_jit_event_on_assets_by_ids_handler
from src.lib.constants import (
    JIT_EVENT_TTL, JIT_EVENT_LIFE_CYCLE_EVENT_BUS_NAME,
    JIT_EVENTS_WITH_DIFF_BASED_ENRICHMENT, TRIGGER_EXECUTION_BUS_NAME,
)
from src.lib.data.enrichment_results_table import EnrichmentResultsManager
from src.lib.models.enrichment_results import BaseEnrichmentResultsItem
from src.lib.models.jit_event_life_cycle import JitEventDBEntity
from src.lib.models.trigger import JobTemplateWrapper, PrepareForExecutionEvent, JitEventProcessingResources, \
    JitEventProcessingEventBridgeDetailType
from tests.component.conftest import FREEZE_TIME, FROZEN_TIME
from tests.component.handle_jit_event.handle_jit_event_test_cases import TEST_CASES
from tests.component.utils.mock_responses.mock_asset_service import mock_get_assets_api, mock_get_assets_by_ids_api
from tests.component.utils.mock_responses.mock_authentication_service import mock_get_internal_token_api
from tests.component.utils.mock_responses.mock_github_service import mock_get_pr_change_list
from tests.component.utils.mock_responses.mock_plan_service_api import (
    mock_get_configuration_file_api,
    mock_get_integration_file_api)
from tests.component.utils.mock_responses.mock_plan_service_api import (
    mock_get_plan_api,
    mock_get_plan_item_configurations,
    mock_get_application_configurations,
)
from tests.component.utils.mock_responses.mock_tenant_service import (
    mock_get_domain_installations_api, mock_get_all_installations_api,
)
from tests.component.utils.mocks.mocks import GITHUB_INSTALLATION, AWS_INSTALLATION, ASSET_AWS_WITH_DEPLOYMENT_CONF
from tests.unit.data.test_enrichment_results_manager import MOCK_ENRICHED_DATA

JIT_EVENT_TEST_CASES_NAMES = list(TEST_CASES.keys())

JIT_EVENT_TEST_CASES_NAMES_WITH_ASSET_IDS = [
    "resources_added_event__has_executions",
    "open_pr_event__has_executions",
    "open_pr_event__non_repo_asset__no_executions",
    "code_related_event__has_executions",
    "code_related_event__has_executions_failed_get_pr_change_list",
    "code_related_event__non_repo_asset__no_executions",
    "manual_event__code__has_executions",
    "manual_event__non_code__has_executions",
    "manual_event__no_asset__no_executions",
    "no_assets__no_executions",
    "item_activated_event__has_executions",
    "item_activated_event__no_plan_item__no_executions",
    "no_plan_items__no_executions",
    "open_pr_event__no_asset__no_executions",
    "resource_added_event__no_assets__no_executions",
]

JIT_EVENT_TEST_CASES_NAMES_WITHOUT_ASSET_IDS = sorted(set(JIT_EVENT_TEST_CASES_NAMES)
                                                      - set(JIT_EVENT_TEST_CASES_NAMES_WITH_ASSET_IDS))


def setup_tenant_data(all_assets, plan):
    mock_get_assets_api([asset.dict() for asset in all_assets])
    mock_get_internal_token_api()
    mock_get_plan_api(plan)
    mock_get_all_installations_api([GITHUB_INSTALLATION.dict(), AWS_INSTALLATION.dict()])
    mock_get_domain_installations_api()
    mock_get_configuration_file_api()
    mock_get_integration_file_api()
    mock_get_plan_item_configurations(
        [
            {"plan_item_slug": "item-web-app-scanner"},
            {"plan_item_slug": "item-runtime-misconfiguration-detection"},
        ]
    )  # for deployment event
    mock_get_plan_item_configurations(
        [
            {"plan_item_slug": "item-web-app-scanner"},
            {"plan_item_slug": "item-runtime-misconfiguration-detection"},
        ],
        tag="qa",
    )  # for deployment event
    mock_get_application_configurations(
        [
            {"type": "web", "application_name": "my-deployment"},
            {
                "type": "aws_configuration",
                "application_name": ASSET_AWS_WITH_DEPLOYMENT_CONF.asset_name,
                "account_ids": [ASSET_AWS_WITH_DEPLOYMENT_CONF.aws_account_id],
            },
        ]
    ),  # for deployment event
    mock_get_application_configurations(
        [],
        tag="qa",
    )  # for deployment event


def mock_sfn_and_events(mocker):
    sfn_client_start_exec: MagicMock = mocker.patch(
        "src.lib.cores.jit_event_handlers.jit_event_assets_orchestrator.SFNClient.start_execution")
    return sfn_client_start_exec


def assert_from_trigger_filter_attributes(
        trigger_filter_attributes: TriggerFilterAttributes, job: JobTemplateWrapper, asset: Asset
):
    if trigger_filter_attributes.plan_item_slugs:
        assert job.plan_item_slug in trigger_filter_attributes.plan_item_slugs
    if trigger_filter_attributes.workflow_slugs:
        assert job.workflow_slug in trigger_filter_attributes.workflow_slugs
    if trigger_filter_attributes.job_names:
        assert job.job_name in trigger_filter_attributes.job_names
    if trigger_filter_attributes.asset_ids:
        assert asset.asset_id in trigger_filter_attributes.asset_ids
    if trigger_filter_attributes.asset_envs:
        assert asset.environment in trigger_filter_attributes.asset_envs


def assert_dependency_data(expected_has_dependency, prepare_for_execution_event):
    assert prepare_for_execution_event.should_enrich is expected_has_dependency
    if expected_has_dependency:
        assert prepare_for_execution_event.depends_on_workflows_templates[0].slug == "workflow-enrichment-code"


def sort_result_for_assertions(expected_triggered_assets, sfn_client_start_exec):
    # sort the result event and the expected asset list - so we can compare them in a loop
    prepare_for_execution_events = [
        PrepareForExecutionEvent(**json.loads(raw_event.kwargs["input"]))
        for raw_event
        in sfn_client_start_exec.call_args_list
    ]
    prepare_for_execution_events.sort(key=lambda event: event.asset.asset_id)
    expected_triggered_assets.sort(key=lambda asset: asset.asset_id)
    return prepare_for_execution_events


def assert_event_details(
        expected_trigger_filter_attributes,
        expected_triggered_asset,
        jit_event,
        prepare_for_execution_event):
    assert prepare_for_execution_event.jit_event == jit_event
    assert prepare_for_execution_event.trigger_filter_attributes == expected_trigger_filter_attributes
    for job in prepare_for_execution_event.filtered_jobs:
        runner_config = RunnerConfig(**job.raw_job_template["runner"])
        assert runner_config.type in ["github_actions", "jit"]
        assert runner_config.setup.timeout_minutes == 10
        # mock content for assertion
        job.workflow_template["content"] = ""
        assert parse_obj_as(WorkflowTemplate, job.workflow_template)
        assert_from_trigger_filter_attributes(expected_trigger_filter_attributes, job, expected_triggered_asset)


def assert_resources(expected_triggered_asset, prepare_for_execution_event):
    assert prepare_for_execution_event.asset == expected_triggered_asset
    assert [installation.installation_id for installation in prepare_for_execution_event.installations].sort() == [
        GITHUB_INSTALLATION.installation_id, AWS_INSTALLATION.installation_id
    ].sort()


def setup_test_environment(mocker, test_case_name):
    (
        jit_event,
        plan,
        all_assets,
        expected_triggered_assets,
        expected_trigger_filter_attributes,
        expected_has_dependency,
        has_valid_plan_item_and_workflow,
        expected_jit_event_status,
        expected_enrich_data,  # A list of EnrichmentData objects to be asserted on the list of PrepareForExecutionEvent
    ) = TEST_CASES[test_case_name].values()
    setup_tenant_data(all_assets, plan)
    mock_get_assets_by_ids_api(all_assets, jit_event.trigger_filter_attributes.asset_ids)
    sfn_client_start_exec = mock_sfn_and_events(mocker)

    return (
        jit_event,
        plan,
        all_assets,
        expected_triggered_assets,
        expected_trigger_filter_attributes,
        expected_has_dependency,
        sfn_client_start_exec,
        has_valid_plan_item_and_workflow,
        expected_jit_event_status,
        expected_enrich_data
    )


def assert_execution_events(
        expected_triggered_assets,
        expected_trigger_filter_attributes,
        sfn_client_start_exec,
        jit_life_cycle_events,
        jit_event,
        expected_has_dependency: Optional[bool],  # None to skip default assertions
        expected_enrich_data=None,
):
    # Step Functions were triggered for the relevant assets
    assert sfn_client_start_exec.call_count == len(expected_triggered_assets)
    # Jit event life cycle event was started for the jit event, and ended if there are no assets to run on
    if len(expected_triggered_assets) > 0:
        assert len(jit_life_cycle_events) == 1
    else:
        assert len(jit_life_cycle_events) == 2

    # for each asset we have jobs to run on, we except to generate a prepare_for_execution_event
    prepare_for_execution_events = sort_result_for_assertions(expected_triggered_assets, sfn_client_start_exec)
    for i in range(len(expected_triggered_assets)):
        expected_triggered_asset = expected_triggered_assets[i]
        prepare_for_execution_event = prepare_for_execution_events[i]
        assert_event_details(
            expected_trigger_filter_attributes, expected_triggered_asset, jit_event, prepare_for_execution_event
        )
        assert_resources(expected_triggered_asset, prepare_for_execution_event)
        if expected_has_dependency is not None:
            assert_dependency_data(expected_has_dependency, prepare_for_execution_event)
        if expected_enrich_data is not None:
            assert expected_enrich_data[i] == prepare_for_execution_event.enriched_data


def assert_jit_event_life_cycle_db_record(
        jit_event_life_cycle_table,
        expected_jit_event,
        expected_trigger_filter_attributes,
        expected_triggered_assets,
        expected_status: JitEventStatus = JitEventStatus.STARTED
):
    items = jit_event_life_cycle_table.scan()["Items"]

    assert len(items) == 1
    item = JitEventDBEntity(**items[0])

    assert_jit_event_life_cycle(jit_event=item, expected_jit_event=expected_jit_event, expected_status=expected_status)
    assert item.jit_event == expected_jit_event
    if expected_trigger_filter_attributes and expected_trigger_filter_attributes.plan_item_slugs:
        assert sorted(item.plan_item_slugs) == sorted(list(expected_trigger_filter_attributes.plan_item_slugs))
    if expected_triggered_assets:
        assert item.total_assets == len(expected_triggered_assets)
        assert item.remaining_assets == len(expected_triggered_assets)


@activate
@pytest.mark.parametrize(
    "test_case_name",
    ["item_activated_event__has_executions",
     "item_activated_event__no_plan_item__no_executions"],
)
@freezegun.freeze_time(FREEZE_TIME)
def test_handle_jit_event__dismiss_item_activated(mocker, test_case_name, dynamodb_table_mocks):
    """
    in this test we are going simulate jit events processed by the system.
    we are going to call the `handle-jit-event` lambda handler when dismiss_item_activated ff is on,
    and expect to not handle plan item activated event.
    Inputs:
    * Setup for the event: jit_event + plan + assets
    * Expectations to assert: not events were handles, no executions were triggered
    """
    # setup
    (
        jit_event,
        plan,
        all_assets,
        expected_triggered_assets,
        expected_trigger_filter_attributes,
        expected_has_dependency,
        sfn_client_start_exec,
        has_valid_plan_item_and_workflow,
        expected_jit_event_status,
        expected_enrich_data
    ) = setup_test_environment(mocker, test_case_name)
    mocker.patch('src.handlers.handle_jit_event.get_dismiss_item_activated_event_ff', return_value=True)
    # act
    with mock_eventbridge(bus_name=[JIT_EVENT_LIFE_CYCLE_EVENT_BUS_NAME]) as get_events:
        handler({"detail": jit_event.dict(), "detail-type": "handle-jit-event"}, {})  # noqa
        jit_life_cycle_events = get_events[JIT_EVENT_LIFE_CYCLE_EVENT_BUS_NAME]()

        # verify
        assert len(jit_life_cycle_events) == 0


@activate
@pytest.mark.parametrize("test_case_name", JIT_EVENT_TEST_CASES_NAMES)
@freezegun.freeze_time(FREEZE_TIME)
def test_handle_jit_event(mocker, test_case_name, dynamodb_table_mocks):
    """
    in this test we are going simulate jit events processed by the system.
    we are going to call the `handle-jit-event` lambda handler with varius kind of events,
    and expect to trigger relevant executions based on the event and the tenant's plan + assets.
    Inputs:
    * Setup for the event: jit_event + plan + assets
    * Expectations to assert: triggered_assets, filter_attributes, has_dependency, jit_security_check_events count
    """
    # setup
    (
        jit_event,
        plan,
        all_assets,
        expected_triggered_assets,
        expected_trigger_filter_attributes,
        expected_has_dependency,
        sfn_client_start_exec,
        has_valid_plan_item_and_workflow,
        expected_jit_event_status,
        expected_enrich_data
    ) = setup_test_environment(mocker, test_case_name)
    mocker.patch('src.handlers.handle_jit_event.get_asset_in_scale_ff', return_value=False)
    if test_case_name != 'code_related_event__has_executions_failed_get_pr_change_list':
        mock_get_pr_change_list(json_response=["file1.py", "file2.py"])
    else:
        mock_get_pr_change_list(json_response=[], status=500)

    # act
    with mock_eventbridge(bus_name=[JIT_EVENT_LIFE_CYCLE_EVENT_BUS_NAME]) as get_events:
        handler({"detail": jit_event.dict(), "detail-type": "handle-jit-event"}, {})  # noqa
        jit_life_cycle_events = get_events[JIT_EVENT_LIFE_CYCLE_EVENT_BUS_NAME]()

    # verify
    assert_execution_events(
        expected_triggered_assets,
        expected_trigger_filter_attributes,
        sfn_client_start_exec,
        jit_life_cycle_events,
        jit_event,
        expected_has_dependency,
    )
    # Check that the jit event item was created in the DB, if there are any assets to run on
    jit_event_life_cycle_table, _ = dynamodb_table_mocks
    assert_jit_event_life_cycle_db_record(
        jit_event_life_cycle_table=jit_event_life_cycle_table,
        expected_jit_event=jit_event,
        expected_trigger_filter_attributes=expected_trigger_filter_attributes,
        expected_triggered_assets=expected_triggered_assets,
        expected_status=expected_jit_event_status,
    )


@activate
@pytest.mark.parametrize("test_case_name", JIT_EVENT_TEST_CASES_NAMES_WITH_ASSET_IDS)
@freezegun.freeze_time(FREEZE_TIME)
def test_handle_jit_event__asset_in_scale_ff_on(mocker, test_case_name, caplog):
    """
    in this test we are going simulate jit events processed by the system.
    we are going to call the `handle-jit-event` lambda handler with varius kind of events,
    and expect to trigger relevant executions based on the event and the tenant's plan + assets.
    Inputs:
    * Setup for the event: jit_event + plan + assets
    * Expectations to assert: triggered_assets, filter_attributes, has_dependency, jit_security_check_events count
    """
    # setup
    jit_event, _, _, _, _, _, _, _, _, _ = setup_test_environment(mocker, test_case_name)
    mocker.patch('src.handlers.handle_jit_event.get_asset_in_scale_ff', return_value=True)
    mocker.patch('src.handlers.handle_jit_event.get_dismiss_item_activated_event_ff', return_value=True)

    # act
    with mock_eventbridge(bus_name=[JIT_EVENT_LIFE_CYCLE_EVENT_BUS_NAME]) as get_events:
        handler({"detail": jit_event.dict(), "detail-type": "handle-jit-event"}, {})  # noqa
        jit_life_cycle_events = get_events[JIT_EVENT_LIFE_CYCLE_EVENT_BUS_NAME]()

    assert len(jit_life_cycle_events) == 0


@activate
@pytest.mark.parametrize("test_case_name", JIT_EVENT_TEST_CASES_NAMES_WITH_ASSET_IDS)
@freezegun.freeze_time(FREEZE_TIME)
def test_run_jit_event_on_assets_by_ids(mocker, test_case_name, dynamodb_table_mocks):
    """
    This test is going to simulate the `run-jit-event-on-assets-by-ids` event that is sent by the
     `fetch-jit-event-resources` lambda.
    This handler is going to start the executions for the resourced fetched for a jit event,
    meaning the jit event has associated assets and jobs to run on, including installations.

    Since the current triggering of step functions is very dependent on the jobs content,
    we cannot reliably mock the jobs without calling the fetch jit event resources handler.
    """
    # setup
    (
        jit_event,
        plan,
        all_assets,
        expected_triggered_assets,
        expected_trigger_filter_attributes,
        expected_has_dependency,
        sfn_client_start_exec,
        has_valid_plan_item_and_workflow,
        expected_jit_event_status,
        expected_enrich_data
    ) = setup_test_environment(mocker, test_case_name)
    mocker.patch('src.handlers.handle_jit_event.get_dismiss_item_activated_event_ff', return_value=True)
    mocker.patch('src.handlers.handle_jit_event.get_asset_in_scale_ff', return_value=True)
    mocker.patch('src.handlers.handle_jit_event.has_asset_ids_filter', return_value=True)

    if test_case_name != 'code_related_event__has_executions_failed_get_pr_change_list':
        mock_get_pr_change_list(json_response=["file1.py", "file2.py"])
    else:
        mock_get_pr_change_list(json_response=[], status=500)

    # act
    with mock_eventbridge(bus_name=[JIT_EVENT_LIFE_CYCLE_EVENT_BUS_NAME, TRIGGER_EXECUTION_BUS_NAME]) as get_events:
        fetch_jit_event_resources_handler(
            {"detail": jit_event.dict(), "detail-type": "handle-jit-event"},
            {}
        )
        send_resources_ready_events = get_events[TRIGGER_EXECUTION_BUS_NAME]()
        if jit_event.jit_event_name == "item_activated":
            # verify
            jit_life_cycle_events = get_events[JIT_EVENT_LIFE_CYCLE_EVENT_BUS_NAME]()
            assert len(jit_life_cycle_events) == 0
            assert len(send_resources_ready_events) == 0
        else:
            run_jit_event_on_assets_by_ids_handler(
                send_resources_ready_events[0],
                {}
            )
            jit_life_cycle_events = get_events[JIT_EVENT_LIFE_CYCLE_EVENT_BUS_NAME]()

            # verify
            assert_execution_events(
                expected_triggered_assets,
                expected_trigger_filter_attributes,
                sfn_client_start_exec,
                jit_life_cycle_events,
                jit_event,
                expected_has_dependency,
                expected_enrich_data,
            )
            # Check that the jit event item was created in the DB, if there are any assets to run on
            jit_event_life_cycle_table, enrichment_results_table = dynamodb_table_mocks
            assert_jit_event_life_cycle_db_record(
                jit_event_life_cycle_table=jit_event_life_cycle_table,
                expected_jit_event=jit_event,
                expected_trigger_filter_attributes=expected_trigger_filter_attributes,
                expected_triggered_assets=expected_triggered_assets,
                expected_status=expected_jit_event_status,
            )

            if expected_enrich_data and len(expected_enrich_data) == 1:
                enrichment_results_scan = enrichment_results_table.scan()["Items"]
                assert len(enrichment_results_scan) == 1, (
                    f"Expected 1 item in EnrichmentResults table, got {len(enrichment_results_scan)}"
                )
                assert enrichment_results_scan[0]["enrichment_results"] == expected_enrich_data[0]


@activate
@pytest.mark.parametrize("test_case_name, cache_exists", [
    ("manual_event__code__has_executions", True),
    ("manual_event__code__has_executions", False),  # cache does not already exist but we should enrich
    ("resources_added_event__has_executions", True),
    ("code_related_event__has_executions", False),  # cache is not created for PR events (Enrichment scans diff)
])
@freezegun.freeze_time(FREEZE_TIME)
def test_run_jit_event_on_assets_by_ids__enrichment_results(mocker, test_case_name, cache_exists, dynamodb_table_mocks):
    """
    Test the `run-jit-event-on-assets-by-ids` handler's ability to fetch Enrichment results:
        - Handler should fetch available Enrichment results instead of running Enrichment,
            for non `JIT_EVENTS_WITH_DIFF_BASED_ENRICHMENT` events.
        - When the Enrichment results do not exist, the handler should set `should_enrich` to True.
            This will later lead to running Enrichment control in the State Machine.

    Setup:
    - Setup a test environment based on the test case name.
    - Use mocker.spy method on `get_results_for_repository` to validate the returned item.
    - Mock EnrichmentResults DynamoDB records for relevant test cases.

    Act:
    - Call the `run_jit_event_on_assets_by_ids_handler` handler with an event from `fetch-jit-event-resources`.

    Assert:
    - Ensure the `prepare_for_execution` events are generated correctly:
        - If the cache exists, the enriched data should be fetched from the cache, and we should not enrich further.
        - If the cache does not exist, the enriched data should be empty and should_enrich should be True.
    - Ensure the standard flow of the handler is valid (`assert_execution_events`).
    """
    # Setup
    (
        jit_event,
        _,
        all_assets,
        expected_triggered_assets,
        expected_trigger_filter_attributes,
        _,
        sfn_client_start_exec,
        _,
        _,
        _,
    ) = setup_test_environment(mocker, test_case_name)
    mocker.patch('src.handlers.handle_jit_event.get_asset_in_scale_ff', return_value=True)
    spy_get_results = mocker.spy(EnrichmentResultsManager, 'get_results_for_repository')
    mock_get_pr_change_list(json_response=["file1.json"])

    if cache_exists and jit_event.jit_event_name not in JIT_EVENTS_WITH_DIFF_BASED_ENRICHMENT:
        for asset in all_assets:
            if asset.vendor in [VendorEnum.GITHUB.value, VendorEnum.GITLAB.value]:  # only SCM vendors will have cache
                mock_item = BaseEnrichmentResultsItem(
                    tenant_id=asset.tenant_id,
                    vendor=asset.vendor,
                    owner=asset.owner,
                    repo=asset.asset_name,
                    enrichment_results=MOCK_ENRICHED_DATA,
                    jit_event_id=jit_event.jit_event_id,
                    jit_event_name=jit_event.jit_event_name,
                )
                EnrichmentResultsManager().create_results_for_repository(mock_item)

    # Act
    with mock_eventbridge(bus_name=[JIT_EVENT_LIFE_CYCLE_EVENT_BUS_NAME, TRIGGER_EXECUTION_BUS_NAME]) as get_events:
        fetch_jit_event_resources_handler(
            {"detail": jit_event.dict(), "detail-type": "handle-jit-event"},
            {}
        )
        send_resources_ready_events = get_events[TRIGGER_EXECUTION_BUS_NAME]()
        run_jit_event_on_assets_by_ids_handler(
            send_resources_ready_events[0],
            {}
        )
        jit_life_cycle_events = get_events[JIT_EVENT_LIFE_CYCLE_EVENT_BUS_NAME]()

    # Assert
    prepare_for_execution_events = sort_result_for_assertions(expected_triggered_assets, sfn_client_start_exec)
    for event in prepare_for_execution_events:
        if cache_exists:
            assert spy_get_results.spy_return == mock_item
            assert event.should_enrich is False
            assert event.enriched_data == MOCK_ENRICHED_DATA
        else:
            assert event.should_enrich is True
            assert event.enriched_data == {}

    assert_execution_events(
        expected_triggered_assets,
        expected_trigger_filter_attributes,
        sfn_client_start_exec,
        jit_life_cycle_events,
        jit_event,
        expected_has_dependency=None,
    )


@activate
@pytest.mark.parametrize(
    "test_case_name",
    JIT_EVENT_TEST_CASES_NAMES,
)
@freezegun.freeze_time(FREEZE_TIME)
def test_fetch_jit_event_resources(mocker, test_case_name, dynamodb_table_mocks):
    """
    This test is asserting that for each jit event type, the `fetch-jit-event-resources` handler is going to
    fetch the relevant resources for the jit event, and send event for further processing.
    assert the resources fetched will be sent with the right event detail type.
    """
    # setup
    (
        jit_event,
        plan,
        all_assets,
        expected_triggered_assets,
        expected_trigger_filter_attributes,
        expected_has_dependency,
        sfn_client_start_exec,
        has_valid_plan_item_and_workflow,
        _,  # expected_jit_event_status is not relevant for this test because after this handler the jit event
        # is only started, the following run_jit_event_on_assets_by_ids_handler will complete it
        _
    ) = setup_test_environment(mocker, test_case_name)

    # we want to test this handler on all jit event types, even tho we only run it on a subset for now
    mocker.patch('src.handlers.handle_jit_event.get_asset_in_scale_ff', return_value=True)
    mocker.patch('src.handlers.handle_jit_event.has_asset_ids_filter', return_value=True)

    # act
    with mock_eventbridge(bus_name=[TRIGGER_EXECUTION_BUS_NAME, JIT_EVENT_LIFE_CYCLE_EVENT_BUS_NAME]) as get_events:
        fetch_jit_event_resources_handler({"detail": jit_event.dict(), "detail-type": "handle-jit-event"}, {})  # noqa
        jit_life_cycle_events = get_events[JIT_EVENT_LIFE_CYCLE_EVENT_BUS_NAME]()
        send_resources_ready_events = get_events[TRIGGER_EXECUTION_BUS_NAME]()
        # verify
        assert len(jit_life_cycle_events) == 1
        assert len(send_resources_ready_events) == 1
        actual_detail_type = send_resources_ready_events[0]["detail-type"]
        if jit_event.trigger_filter_attributes.asset_ids:
            assert actual_detail_type == JitEventProcessingEventBridgeDetailType.RUN_JIT_EVENT_BY_ASSET_IDS
        elif jit_event.trigger_filter_attributes.asset_envs:
            assert actual_detail_type == JitEventProcessingEventBridgeDetailType.RUN_JIT_EVENT_BY_DEPLOYMENT_ENV
        elif jit_event.trigger_filter_attributes.plan_item_slugs:
            assert actual_detail_type == JitEventProcessingEventBridgeDetailType.RUN_JIT_EVENT_BY_ASSET_TYPES

    # Check that the jit event item was created in the DB
    jit_event_life_cycle_table, _ = dynamodb_table_mocks
    response = jit_event_life_cycle_table.scan()
    response = JitEventDBEntity(**response["Items"][0])
    assert_jit_event_life_cycle(response, jit_event, JitEventStatus.STARTED)

    jit_event_resources = send_resources_ready_events[0]["detail"]
    jit_event_resources = JitEventProcessingResources(**jit_event_resources)
    assert_installations(
        installations=jit_event_resources.installations,
        expected_installations=[GITHUB_INSTALLATION, AWS_INSTALLATION],
    )
    assert jit_event_resources.jit_event == jit_event
    assert_plan_depends_on(
        depends_on=jit_event_resources.plan_depends_on_workflows,
        expected_depends_on=FullPlanContent(**plan).depends_on,
    )
    if has_valid_plan_item_and_workflow:
        assert len(jit_event_resources.jobs) > 0
    else:
        assert len(jit_event_resources.jobs) == 0


def assert_jit_event_life_cycle(jit_event: JitEventDBEntity,
                                expected_jit_event: JitEvent,
                                expected_status: JitEventStatus = JitEventStatus.STARTED) -> None:
    assert jit_event.tenant_id == expected_jit_event.tenant_id
    assert jit_event.jit_event_id == expected_jit_event.jit_event_id
    assert jit_event.status == expected_status
    assert jit_event.jit_event_name == expected_jit_event.jit_event_name
    assert datetime.fromisoformat(jit_event.created_at).strftime('%Y-%m-%d %H:%M:%S') == FREEZE_TIME
    assert jit_event.ttl == int(time.mktime(FROZEN_TIME.timetuple())) + JIT_EVENT_TTL  # TTL according to FREEZE_TIME


def assert_installations(installations: List[Installation], expected_installations: List[Installation]) -> None:
    # TODO: mocks of installations have Asset model instead of Limited asset that creates a diff in the test
    for installation in expected_installations:
        if installation.centralized_repo_asset:
            installation.centralized_repo_asset = LimitedAsset(**installation.centralized_repo_asset.dict())
    assert installations == expected_installations


def assert_plan_depends_on(
        depends_on: Dict[str, WorkflowTemplate],
        expected_depends_on: Dict[str, WorkflowTemplate],
) -> None:
    if not expected_depends_on:
        return
    expected_enrichemnt_code = expected_depends_on['workflow-enrichment-code']
    actual_enrichment_code = depends_on['workflow-enrichment-code']
    assert expected_enrichemnt_code.depends_on == actual_enrichment_code.depends_on
    assert expected_enrichemnt_code.slug == actual_enrichment_code.slug
    assert expected_enrichemnt_code.name == actual_enrichment_code.name
    assert expected_enrichemnt_code.content == actual_enrichment_code.content
    assert expected_enrichemnt_code.asset_types == actual_enrichment_code.asset_types
    assert expected_enrichemnt_code.params == actual_enrichment_code.params
    assert expected_enrichemnt_code.plan_item_template_slug == actual_enrichment_code.plan_item_template_slug


@activate
@pytest.mark.parametrize(
    "test_case_name",
    JIT_EVENT_TEST_CASES_NAMES,
)
def test_fetch_jit_event_resources__return_on_ff_off(mocker: MockerFixture, test_case_name: str):
    """
    This test is asserting that for each jit event type, the `fetch-jit-event-resources` handler is going to
    fetch the relevant resources for the jit event, and send event for further processing.
    assert the resources fetched will be sent with the right event detail type.
    """
    # setup
    (
        jit_event,
        plan,
        all_assets,
        expected_triggered_assets,
        expected_trigger_filter_attributes,
        expected_has_dependency,
        sfn_client_start_exec,
        has_valid_plan_item_and_workflow,
        expected_jit_event_status,
        _,
    ) = setup_test_environment(mocker, test_case_name)

    # we want to test this handler on all jit event types, even tho we only run it on a subset for now
    mocker.patch('src.handlers.handle_jit_event.get_asset_in_scale_ff', return_value=False)

    validate_fetch_jit_event_resources_handler(jit_event=jit_event)


@activate
@pytest.mark.parametrize(
    "test_case_name",
    JIT_EVENT_TEST_CASES_NAMES_WITHOUT_ASSET_IDS,
)
def test_fetch_jit_event_resources__return_on_jit_event_has_no_asset_ids(mocker: MockerFixture, test_case_name: str):
    """
    This test is asserting that for each jit event type, the `fetch-jit-event-resources` handler is going to
    fetch the relevant resources for the jit event, and send event for further processing.
    assert the resources fetched will be sent with the right event detail type.
    """
    # setup
    (
        jit_event,
        plan,
        all_assets,
        expected_triggered_assets,
        expected_trigger_filter_attributes,
        expected_has_dependency,
        sfn_client_start_exec,
        has_valid_plan_item_and_workflow,
        expected_jit_event_status,
        _
    ) = setup_test_environment(mocker, test_case_name)

    # we want to test this handler on all jit event types, even tho we only run it on a subset for now
    mocker.patch('src.handlers.handle_jit_event.get_asset_in_scale_ff', return_value=True)

    validate_fetch_jit_event_resources_handler(jit_event)


def validate_fetch_jit_event_resources_handler(jit_event):
    with mock_eventbridge(bus_name=[TRIGGER_EXECUTION_BUS_NAME, JIT_EVENT_LIFE_CYCLE_EVENT_BUS_NAME]) as get_events:
        fetch_jit_event_resources_handler({"detail": jit_event.dict(), "detail-type": "handle-jit-event"}, {})  # noqa
        jit_life_cycle_events = get_events[JIT_EVENT_LIFE_CYCLE_EVENT_BUS_NAME]()
        send_resources_ready_events = get_events[TRIGGER_EXECUTION_BUS_NAME]()

        # verify
        assert len(jit_life_cycle_events) == 0
        assert len(send_resources_ready_events) == 0

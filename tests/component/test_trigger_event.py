import datetime
import json
import os
from typing import List, Callable, Optional

import freezegun
import pytest
import responses
from jit_utils.event_models import JitEvent, CodeRelatedJitEvent
from jit_utils.event_models.common import TriggerFilterAttributes
from jit_utils.jit_event_names import JitEventName
from jit_utils.models.asset.entities import Asset
from jit_utils.models.tenant.entities import Installation
from jit_utils.models.trigger.jit_event_life_cycle import JitEventStatus
from pydantic import BaseModel
from pytest_mock import MockerFixture
from test_utils.aws.mock_eventbridge import mock_eventbridge
from test_utils.aws.mock_stepfunction import mock_stepfunction

from src.handlers.handle_jit_event import handler
from src.lib.constants import (JIT_EVENT_LIFE_CYCLE_EVENT_BUS_NAME, STARTED_JIT_EVENT_LIFE_CYCLE_EVENT_DETAIL_TYPE,
                               GITLAB, REPO, GITHUB, COMPLETED_JIT_EVENT_LIFE_CYCLE_EVENT_DETAIL_TYPE)
from tests.common import InstallationFactory, LimitedAssetFactory, AssetFactory, CodeRelatedJitEventFactory, \
    JitEventLifeCycleEntityFactory, test_time
from tests.component.utils.mock_responses.mock_asset_service import mock_get_assets_api
from tests.component.utils.mock_responses.mock_authentication_service import mock_get_internal_token_api
from tests.component.utils.mock_responses.mock_github_service import mock_get_github_status_api, mock_get_pr_change_list
from tests.component.utils.mock_responses.mock_plan_service_api import mock_get_configuration_file_api, \
    mock_get_plan_api, mock_get_integration_file_api
from tests.component.utils.mock_responses.mock_tenant_service import mock_get_all_installations_api
from tests.component.utils.mocks.mock_plan import MOCK_PLAN

test_installation: Installation = InstallationFactory.build(
    vendor=GITHUB,
    is_active=True,
    centralized_repo_asset=LimitedAssetFactory.build()
)
test_asset: Asset = AssetFactory.build(
    vendor=GITHUB,
    asset_type=REPO,
    owner=test_installation.owner,
    is_active=True,
    is_covered=True,
    teams=[],
)
test_code_related_jit_event: CodeRelatedJitEvent = CodeRelatedJitEventFactory.build(
    jit_event_name=JitEventName.PullRequestCreated,
    asset_id=test_asset.asset_id,
    vendor='github',
    pull_request_number='1',
)


@freezegun.freeze_time(test_time)
class TestHandleJitEvent:
    class TestCase(BaseModel):
        plan: dict = MOCK_PLAN
        installation: Installation = test_installation
        asset: Asset = test_asset
        jit_event: JitEvent = test_code_related_jit_event

        # In case we need to mock more steps
        more_mock_steps: Optional[List[Callable[[MockerFixture], None]]] = []

        expected_jit_event_life_cycle_events: Optional[List[dict]] = []
        expected_executions_history: Optional[List[dict]] = []

    @pytest.mark.parametrize(
        'test_case',
        (
                pytest.param(TestCase(
                    expected_jit_event_life_cycle_events=[
                        {
                            'detail-type': STARTED_JIT_EVENT_LIFE_CYCLE_EVENT_DETAIL_TYPE,
                            'detail': json.loads(JitEventLifeCycleEntityFactory.build(
                                jit_event=test_code_related_jit_event,
                                status=JitEventStatus.STARTED,
                                jit_event_id=test_code_related_jit_event.jit_event_id,
                                jit_event_name=test_code_related_jit_event.jit_event_name,
                            ).json())
                        }
                    ],
                    expected_executions_history=[
                        {
                            'name': f"{test_code_related_jit_event.jit_event_name}-"
                                    f"{test_code_related_jit_event.jit_event_id}-"
                                    f"{test_time.replace(tzinfo=datetime.timezone.utc).timestamp()}",
                            'status': 'RUNNING',
                            'input': {
                                'jit_event': json.loads(test_code_related_jit_event.json()),
                                'asset': json.loads(json.dumps(test_asset.dict())),
                                'installations': [json.loads(test_installation.json())],
                                'should_enrich': True,
                                'enriched_data': {},
                                'trigger_filter_attributes': json.loads(TriggerFilterAttributes(
                                    asset_ids={test_asset.asset_id},
                                    triggers={test_code_related_jit_event.jit_event_name},
                                    create_trigger_event_from_jit_event=True
                                ).json())
                            }
                        }
                    ]
                ), id="Code related jit event should trigger jobs"),
                pytest.param(TestCase(
                    plan={"items": {}},
                    jit_event=test_code_related_jit_event,
                    expected_jit_event_life_cycle_events=[
                        {
                            'detail-type': STARTED_JIT_EVENT_LIFE_CYCLE_EVENT_DETAIL_TYPE,
                            'detail': json.loads(JitEventLifeCycleEntityFactory.build(
                                jit_event=test_code_related_jit_event,
                                jit_event_id=test_code_related_jit_event.jit_event_id,
                                jit_event_name=test_code_related_jit_event.jit_event_name,
                                status=JitEventStatus.STARTED,
                            ).json())
                        },
                        {
                            'detail-type': COMPLETED_JIT_EVENT_LIFE_CYCLE_EVENT_DETAIL_TYPE,
                            'detail': json.loads(JitEventLifeCycleEntityFactory.build(
                                jit_event=test_code_related_jit_event,
                                jit_event_id=test_code_related_jit_event.jit_event_id,
                                jit_event_name=test_code_related_jit_event.jit_event_name,
                                status=JitEventStatus.COMPLETED,
                                modified_at=test_time.isoformat()
                            ).json())
                        }
                    ],
                ), id="Empty plan should filter jobs and finish lifecycle"),
                pytest.param(TestCase(
                    jit_event=test_code_related_jit_event,
                    more_mock_steps=[
                        lambda mocker: mocker.patch(
                            "src.lib.cores.jit_event_handlers.job_filters.evaluate_feature_flag",
                            return_value=True),
                        lambda _: mock_get_github_status_api(status="outage")
                    ],
                    expected_jit_event_life_cycle_events=[
                        {
                            'detail-type': STARTED_JIT_EVENT_LIFE_CYCLE_EVENT_DETAIL_TYPE,
                            'detail': json.loads(JitEventLifeCycleEntityFactory.build(
                                jit_event=test_code_related_jit_event,
                                jit_event_id=test_code_related_jit_event.jit_event_id,
                                jit_event_name=test_code_related_jit_event.jit_event_name,
                                status=JitEventStatus.STARTED,
                            ).json())
                        },
                        {
                            'detail-type': COMPLETED_JIT_EVENT_LIFE_CYCLE_EVENT_DETAIL_TYPE,
                            'detail': json.loads(JitEventLifeCycleEntityFactory.build(
                                jit_event=test_code_related_jit_event,
                                jit_event_id=test_code_related_jit_event.jit_event_id,
                                jit_event_name=test_code_related_jit_event.jit_event_name,
                                status=JitEventStatus.COMPLETED,
                                modified_at=test_time.isoformat()
                            ).json())
                        }
                    ],
                ), id="Code related jit event with GitHub outage should filter jobs and finish lifecycle"),
                pytest.param(TestCase(
                    installation=test_installation.copy(
                        update={
                            "vendor": GITLAB,
                            "centralized_repo_asset": LimitedAssetFactory.build()
                        }
                    ),
                    asset=test_asset.copy(
                        update={
                            "vendor": GITLAB,
                        }
                    ),
                    jit_event=test_code_related_jit_event,
                    more_mock_steps=[
                        lambda mocker: mocker.patch(
                            "src.lib.cores.jit_event_handlers.job_filters.evaluate_feature_flag",
                            return_value=True),
                        lambda _: mock_get_github_status_api(status="outage")
                    ],
                    expected_jit_event_life_cycle_events=[
                        {
                            'detail-type': STARTED_JIT_EVENT_LIFE_CYCLE_EVENT_DETAIL_TYPE,
                            'detail': json.loads(JitEventLifeCycleEntityFactory.build(
                                jit_event=test_code_related_jit_event,
                                status=JitEventStatus.STARTED,
                                jit_event_id=test_code_related_jit_event.jit_event_id,
                                jit_event_name=test_code_related_jit_event.jit_event_name,
                            ).json())
                        }
                    ],
                    expected_executions_history=[
                        {
                            'name': f"{test_code_related_jit_event.jit_event_name}-"
                                    f"{test_code_related_jit_event.jit_event_id}-"
                                    f"{test_time.replace(tzinfo=datetime.timezone.utc).timestamp()}",
                            'status': 'RUNNING'
                        }
                    ]
                ), id="Code related jit event with GitHub outage without GitHub installation shouldn't filter jobs"),
        )
    )
    @responses.activate
    def test_handler(self,
                     test_case: TestCase,
                     monkeypatch,
                     dynamodb_table_mocks,
                     mocker: MockerFixture):
        mock_get_internal_token_api()
        mock_get_plan_api(plan=test_case.plan)
        mock_get_configuration_file_api(configuration_file={})
        mock_get_integration_file_api(integration_file={})

        for step in test_case.more_mock_steps:
            step(mocker)

        mock_get_all_installations_api(installations=[test_case.installation.dict()])

        mock_get_assets_api(assets=[test_case.asset.dict()])

        mock_get_pr_change_list(json_response=["file.json"])

        with mock_stepfunction('dummy-state-machine') as outputs:
            get_execution_history, state_machine_arn = outputs
            with mock_eventbridge([JIT_EVENT_LIFE_CYCLE_EVENT_BUS_NAME]) as get_events:
                os.environ['ENRICHMENT_STATE_MACHINE_ARN'] = state_machine_arn

                handler({
                    'detail': test_case.jit_event.dict()
                }, None)

                jit_event_life_cycle_events = get_events[JIT_EVENT_LIFE_CYCLE_EVENT_BUS_NAME]()
                for actual, expected in zip(jit_event_life_cycle_events,
                                            test_case.expected_jit_event_life_cycle_events):
                    assert actual['detail-type'] == expected['detail-type']
                    if 'ttl' in actual['detail']:
                        # This value exists only in the DB model
                        del actual['detail']['ttl']
                    assert actual['detail'] == expected['detail']

            executions_history = get_execution_history()
            for actual, expected in zip(executions_history, test_case.expected_executions_history):
                assert actual['name'] == expected['name']
                assert actual['status'] == expected['status']
                if 'input' in expected:
                    actual_input = json.loads(actual['input'])

                    # TODO add tests that validate also the content of those fields
                    del actual_input['depends_on_workflows_templates']
                    workflow_template_count = sum(
                        len(item.get("workflow_templates", [])) for item in test_case.plan["items"].values())
                    assert len(actual_input['filtered_jobs']) == workflow_template_count
                    del actual_input['filtered_jobs']

                    assert actual_input == expected['input']

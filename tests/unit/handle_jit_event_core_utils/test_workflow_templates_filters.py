import pytest
import yaml

from src.lib.constants import TAGS, LANGUAGES, TRIGGER, SLUG, ASSETS_TYPES_WITH_INSTALLATIONS, CONTENT
from src.lib.cores.handle_jit_event_core_utils.workflows_templates_filters import (
    filter_plan,
    filter_workflows,
    filter_jobs,
    filter_assets,
    group_active_assets_by_type,
    _should_filter_out_by_jit_event_based_on_triggers,
    _should_filter_out_job_by_jit_event_based_on_tags
)
from jit_utils.event_models.common import TriggerFilterAttributes

from tests.common import CodeRelatedJitEventFactory, JitEventFactory, InstallationFactory, AssetFactory

ASSETS = [
    AssetFactory.build(
        asset_id='id-1',
        asset_type='type-1',
        vendor='vendor-1',
        owner='owner-1',
        asset_name='name-1',
        is_active=True,
        is_covered=True,
        environment='env-1',
    ),
    AssetFactory.build(
        asset_id='id-1b',
        asset_type='type-1',
        vendor='vendor-1',
        owner='owner-2',
        asset_name='name-1b',
        is_active=True,
        is_covered=True,
        environment='env-2',
    ),
    AssetFactory.build(
        asset_id='id-2',
        asset_type='type-2',
        vendor='vendor-1',
        owner='owner-3',
        asset_name='name-2',
        is_active=True,
        is_covered=True,
        environment='env-2',
    ),
    AssetFactory.build(
        asset_id='id-3',
        asset_type='type-3',
        vendor='vendor-2',
        owner='owner-1',
        asset_name='name-3',
        is_active=True,
        is_covered=False,
        environment='env-3',
    ),
    AssetFactory.build(
        asset_id='id-4',
        asset_type='type-4',
        vendor='vendor-2',
        owner='owner-2',
        asset_name='name-4',
        is_active=False,
        is_covered=True,
        environment='env-4',
    )
]


@pytest.mark.parametrize('plan_item_slugs', [
    set(),
    {'plan-item-slug-2'},
    {'plan-item-slug-1', 'plan-item-slug-2'},
    {'plan-item-slug-1', 'plan-item-slug-2', 'plan-item-slug-3'},
])
def test_filter_plan(plan_item_slugs):
    plan = {
        'plan-item-slug-1': {
            'description': 'This is plan item 1',
        },
        'plan-item-slug-2': {
            'description': 'This is plan item 2',
        },
    }

    trigger_filter_attributes = TriggerFilterAttributes(
        asset_ids={'asset-id-1', 'asset-id-2'},
        asset_envs={'asset-env-1', 'asset-env-2'},
        plan_item_slugs=plan_item_slugs,
        triggers={'trigger_1'},
    )

    filtered_plan = filter_plan(plan, trigger_filter_attributes)

    intersection = set(plan).intersection(plan_item_slugs)
    assert set(filtered_plan) == intersection if plan_item_slugs else set(plan.keys())


def test_filter_assets_no_asset_filter_applied():
    trigger_filter_attributes = TriggerFilterAttributes(
        plan_item_slugs={'plan-item-slug-1', 'plan-item-slug-2'},
        triggers={'trigger_1'},
    )

    filtered_assets = filter_assets(ASSETS, trigger_filter_attributes, {}, '', '')
    assert filtered_assets == ASSETS


@pytest.mark.parametrize('requested_asset_ids,result_asset_ids', [
    (['id-1'], {'id-1'}),
    (['id-1', 'id-2'], {'id-1', 'id-2'}),
    (['id-1', 'id-2', 'id-4'], {'id-1', 'id-2', 'id-4'}),
    (['id-45', 'id-2', 'id-77'], {'id-2'})
])
def test_filter_assets_by_ids(requested_asset_ids, result_asset_ids):
    trigger_filter_attributes = TriggerFilterAttributes(
        asset_ids=set(requested_asset_ids),
    )

    filtered_assets = filter_assets(ASSETS, trigger_filter_attributes, {}, '', '')
    assert {asset.asset_id for asset in filtered_assets} == result_asset_ids


def test_filter_assets_by_ids_and_envs():
    trigger_filter_attributes = TriggerFilterAttributes()

    assets_with_installation = [
        AssetFactory.build(
            asset_id='asset-1',
            asset_type='type-1',
            vendor='vendor-7',
            owner='owner-17'
        ),
        AssetFactory.build(
            asset_id='asset-1',
            asset_type=list(ASSETS_TYPES_WITH_INSTALLATIONS)[0],
            vendor='vendor-1',
            owner='owner-3'
        ),
        AssetFactory.build(
            asset_id='asset-3',
            asset_type=list(ASSETS_TYPES_WITH_INSTALLATIONS)[1],
            vendor='vendor-1',
            owner='owner-1'
        ),
        AssetFactory.build(
            asset_id='asset-4',
            asset_type=list(ASSETS_TYPES_WITH_INSTALLATIONS)[1],
            vendor='vendor-50',
            owner='owner-70'
        ),
    ]

    installations = {
        ('vendor-1', 'owner-1'): InstallationFactory.build(),
        ('vendor-1', 'owner-2'): InstallationFactory.build(),
        ('vendor-2', 'owner-2'): InstallationFactory.build()
    }

    filtered_assets = filter_assets(assets_with_installation, trigger_filter_attributes, installations, '', '')
    assert {asset.asset_id for asset in filtered_assets} == {'asset-1', 'asset-3'}


def test_group_active_assets_by_type():
    grouped_assets = group_active_assets_by_type(ASSETS)
    assert len(grouped_assets) == 2
    assert len(grouped_assets['type-1']) == 2
    assert len(grouped_assets['type-2']) == 1


@pytest.mark.parametrize('tags,expected_answer', [
    ({}, False),
    ({TAGS: {}}, False),
    ({TAGS: {LANGUAGES: ['python']}}, False),
    ({TAGS: {LANGUAGES: ['javascript']}}, True),
    ({TAGS: {LANGUAGES: ['javascript', 'go']}}, True),
    ({TAGS: {LANGUAGES: ['javascript', 'python']}}, False),
])
def test__should_filter_out_jobs_based_on_tags(tags, expected_answer):
    jit_event = CodeRelatedJitEventFactory.build(languages=['python'])

    result = _should_filter_out_job_by_jit_event_based_on_tags(tags, jit_event)
    assert result == expected_answer


@pytest.mark.parametrize('jit_obj,triggers,result', [
    ({}, [], False),
    ({TRIGGER: {'on': ['blabla']}}, set(), False),
    ({TRIGGER: {'on': ['blabla']}}, {'blabla'}, False),
    ({TRIGGER: {'on': ['blabla', 'rababa']}}, {'blabla'}, False),
    ({TRIGGER: {'on': ['blabla', 'rababa']}}, {'dodo'}, True),
])
def test__should_filter_out_by_jit_event_based_on_triggers(jit_obj, triggers, result):
    trigger_filter_attributes = TriggerFilterAttributes(
        triggers=triggers,
    )
    nested_parsed_obj = {CONTENT: yaml.dump(jit_obj)}
    assert _should_filter_out_by_jit_event_based_on_triggers(jit_obj, trigger_filter_attributes) == result
    assert _should_filter_out_by_jit_event_based_on_triggers(nested_parsed_obj, trigger_filter_attributes) == result


@pytest.mark.parametrize('wf_filter,result_wf_slugs', [
    (
            TriggerFilterAttributes(),
            {'workflow-1', 'workflow-2', 'workflow-3'}
    ),
    (
            TriggerFilterAttributes(workflow_slugs={'workflow-1', 'workflow-2'}),
            {'workflow-1', 'workflow-2'}
    ),
    (
            TriggerFilterAttributes(triggers={'trigger-1'}, workflow_slugs={'workflow-1', 'workflow-3'}),
            {'workflow-1'}
    ),
    (
            TriggerFilterAttributes(triggers={'trigger-1'}),
            {'workflow-1', 'workflow-2'}
    ),
    (
            TriggerFilterAttributes(triggers={'trigger-3'}),
            set()
    ),
    (
            TriggerFilterAttributes(workflow_slugs={'workflow-77'}),
            set()
    ),
])
def test_filter_workflows(wf_filter, result_wf_slugs):
    workflows = [
        {
            SLUG: 'workflow-1',
            TRIGGER: {
                'on': ['trigger-1'],
            },
        },
        {
            SLUG: 'workflow-2',
            TRIGGER: {
                'on': ['trigger-1'],
            },
        },
        {
            SLUG: 'workflow-3',
            TRIGGER: {
                'on': ['trigger-2'],
            },
        }
    ]

    result = filter_workflows(workflows, wf_filter)
    assert {workflow[SLUG] for workflow in result} == result_wf_slugs


@pytest.mark.parametrize('jit_event,job_filter,result_jobs_names', [
    (
            JitEventFactory.build(),
            TriggerFilterAttributes(),
            {'job-1', 'job-2', 'job-3'}
    ),
    (
            JitEventFactory.build(),
            TriggerFilterAttributes(job_names={'job-1', 'job-2'}),
            {'job-1', 'job-2'}
    ),
    (
            JitEventFactory.build(),
            TriggerFilterAttributes(triggers={'trigger-1'}, job_names={'job-1', 'job-3'}),
            {'job-1'}
    ),
    (
            JitEventFactory.build(),
            TriggerFilterAttributes(triggers={'trigger-1'}),
            {'job-1', 'job-2'}
    ),
    (
            JitEventFactory.build(),
            TriggerFilterAttributes(triggers={'trigger-3'}),
            set()
    ),
    (
            JitEventFactory.build(),
            TriggerFilterAttributes(job_names={'job-77'}),
            set()
    ),
    (
            CodeRelatedJitEventFactory.build(languages=['python']),
            TriggerFilterAttributes(job_names={'job-3'}),
            {'job-3'}
    ),
    (
            CodeRelatedJitEventFactory.build(languages=['python']),
            TriggerFilterAttributes(job_names={'job-3'}),
            {'job-3'}
    ),
    (
            CodeRelatedJitEventFactory.build(languages=['js']),
            TriggerFilterAttributes(job_names={'job-3'}),
            {'job-3'}
    ),
])
def test_filter_jobs(jit_event, job_filter, result_jobs_names):
    jobs = {
        'job-1': {
            TRIGGER: {
                'on': ['trigger-1'],
            },
        },
        'job-2': {
            TRIGGER: {
                'on': ['trigger-1'],
            },
        },
        'job-3': {
            SLUG: 'workflow-3',
            TRIGGER: {
                'on': ['trigger-2'],
            },
            TAGS: {
                LANGUAGES: ['python'],
            },
        }
    }

    result = filter_jobs(jobs, job_filter, jit_event)
    assert set(result.keys()) == result_jobs_names

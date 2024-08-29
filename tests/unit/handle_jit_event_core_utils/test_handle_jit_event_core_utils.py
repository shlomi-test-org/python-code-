from typing import List, Dict
import pytest
from jit_utils.models.jit_files.jit_config import ResourcesGroup, ResourceManagement, ResourceManagementExcludeOptions
from jit_utils.models.trigger.requests import AssetTriggerFilters

from src.lib.constants import ASSET_TYPE
from src.lib.cores.handle_jit_event_core import _build_prepare_for_execution_event_for_asset, \
    _get_depends_on_slugs_of_jobs, _group_jobs_by_asset_type, _filter_jobs_based_on_exclusion
from src.lib.data.enrichment_results_db_models import EnrichmentResultsItemNotFoundError
from src.lib.models.asset import Asset
from jit_utils.event_models import JitEvent
from jit_utils.event_models.third_party.github import Installation
from jit_utils.event_models.common import TriggerFilterAttributes

from src.lib.models.trigger import JobTemplateWrapper, PrepareForExecutionEvent, WorkflowTemplate
from tests.common import AssetFactory, JitEventFactory, InstallationFactory, FilteredJobFactory


@pytest.mark.parametrize(
    "asset, trigger_filter_attributes, jit_event, filtered_jobs, installations, depends_on_workflows",
    [
        (AssetFactory.build(asset_type="repo"), TriggerFilterAttributes(), JitEventFactory.build(),
         FilteredJobFactory.batch(size=1, depends_on_slugs=["workflow_slug"]),
         InstallationFactory.batch(size=1), {"workflow_slug": WorkflowTemplate(slug="slug",
                                                                               name="name",
                                                                               content="jobs: []")},
         ),
        (AssetFactory.build(asset_type="repo"), TriggerFilterAttributes(), JitEventFactory.build(),
         FilteredJobFactory.batch(size=1, depends_on_slugs=[]),
         InstallationFactory.batch(size=1), {}),
    ])
def test_build_prepare_for_execution_event_for_asset(asset: Asset,
                                                     trigger_filter_attributes: TriggerFilterAttributes,
                                                     jit_event: JitEvent,
                                                     filtered_jobs: List[JobTemplateWrapper],
                                                     installations: List[Installation],
                                                     depends_on_workflows: Dict[str, Dict],
                                                     mocker):
    mocker.patch("src.lib.cores.handle_jit_event_core._get_depends_on_slugs_of_jobs",
                 return_value=["workflow_slug"])
    # assume the asset does not have Enrichment Results in Dynamo
    mocker.patch(
        "src.lib.cores.handle_jit_event_core.EnrichmentResultsManager.get_results_for_repository",
        side_effect=EnrichmentResultsItemNotFoundError,
    )
    res: PrepareForExecutionEvent = _build_prepare_for_execution_event_for_asset(asset, trigger_filter_attributes,
                                                                                 jit_event,
                                                                                 filtered_jobs,
                                                                                 installations,
                                                                                 depends_on_workflows)
    for key in depends_on_workflows.keys():
        assert depends_on_workflows[key] in res.depends_on_workflows_templates


@pytest.mark.parametrize("jobs, expected_slugs", [
    (FilteredJobFactory.batch(size=3, depends_on_slugs=["workflow_slug"]), ["workflow_slug"]),
    (FilteredJobFactory.batch(size=3, depends_on_slugs=[]), []),
    ([FilteredJobFactory.build(depends_on_slugs=["workflow_slug"]),
      FilteredJobFactory.build(depends_on_slugs=["workflow_slug_2"])], ["workflow_slug", "workflow_slug_2"]),
])
def test_get_depends_on_slugs_of_jobs(jobs: List[JobTemplateWrapper], expected_slugs: List[str]):
    depends_on_slugs = _get_depends_on_slugs_of_jobs(jobs)
    assert depends_on_slugs.sort() == expected_slugs.sort()


@pytest.mark.parametrize("jobs, expected_grouped_assets_length", [
    (FilteredJobFactory.batch(size=3, raw_job_template={ASSET_TYPE: "repo"}), {"repo": 3}),
    ((FilteredJobFactory.batch(size=3, raw_job_template={ASSET_TYPE: "repo"}) +
      FilteredJobFactory.batch(size=3, raw_job_template={ASSET_TYPE: "org"})),
     {"repo": 3, "org": 3}),
])
def test_group_jobs_by_asset_type(jobs: List[JobTemplateWrapper], expected_grouped_assets_length: Dict[str, int]):
    grouped_jobs_by_asset_type = _group_jobs_by_asset_type(jobs)
    for key in expected_grouped_assets_length.keys():
        assert len(grouped_jobs_by_asset_type[key]) == expected_grouped_assets_length[key]


JOB_1 = FilteredJobFactory.build(plan_item_slug="plan-item-1", job_name="job-1")
JOB_2 = FilteredJobFactory.build(plan_item_slug="plan-item-2", job_name="job-2")
JOB_3 = FilteredJobFactory.build(plan_item_slug="plan-item-3", job_name="job-3")


@pytest.mark.parametrize(
    "filtered_jobs, asset_name, exclude_plan_items_section, expected_result",
    [
        (
            [
                JOB_1,
                JOB_2,
                JOB_3,
            ],
            AssetFactory.build(asset_name="resource-2"),
            {
                "plan-item-1": ResourcesGroup(
                    resources=[
                        AssetTriggerFilters(name="resource-2"),  # Will filter out JOB_1
                    ]
                ),
            },
            [
                JOB_2,
                JOB_3,
            ],
        ),
        (
            [
                JOB_1,
                JOB_2,
                JOB_3,
            ],
            AssetFactory.build(asset_name="resource-3"),
            {
                "plan-item-2": ResourcesGroup(
                    resources=[
                        AssetTriggerFilters(name="resource-3"),  # Will filter out JOB_2
                    ]
                ),
                "plan-item-3": ResourcesGroup(
                    resources=[
                        AssetTriggerFilters(name="resource-3"),  # Will filter out JOB_3
                    ]
                ),
            },
            [
                JOB_1,
            ],
        ),
    ],
)
def test_filter_jobs_based_on_exclusion(filtered_jobs, asset_name, exclude_plan_items_section, expected_result):
    filtered_result = _filter_jobs_based_on_exclusion(
        filtered_jobs, asset_name, ResourceManagement(
            exclude=ResourceManagementExcludeOptions(plan_items=exclude_plan_items_section)
        )
    )
    assert filtered_result == expected_result

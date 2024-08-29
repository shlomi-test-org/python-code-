from typing import Set
from unittest.mock import MagicMock

import pytest
import yaml
from jit_utils.event_models.common import TriggerFilterAttributes
from pytest_mock import MockerFixture

import src.lib.cores.handle_jit_event_core
from src.lib.constants import (
    PARSED_CONTENT,
    JOBS,
    GITHUB, CONTENT,
)
from src.lib.cores.handle_jit_event_core import _get_tenant_installations_grouped_by_vendor_and_owner
from src.lib.cores.enrich_core import _get_filtered_jobs_from_filtered_workflows
from src.lib.models.trigger import (
    JobTemplateWrapper,
)
from tests.common import (
    InstallationFactory,
    JitEventFactory,
    FilteredWorkflowFactory,
)


@pytest.mark.parametrize("vendors", [{"some-vendor"}, {"aws"}, {"aws", GITHUB}, {"some-vendor-2", GITHUB}])
def test__get_tenant_installations_grouped_by_vendor_and_owner(mocker: MockerFixture, vendors: Set[str]) -> None:
    installations = {
        "aws": [
            InstallationFactory.build(installation_id="id-1", owner="owner_1", vendor="aws"),
            InstallationFactory.build(installation_id="id-2", owner="owner_2", vendor="aws"),
        ],
        GITHUB: [
            InstallationFactory.build(installation_id="id-3", owner="owner_3", vendor=GITHUB),
            InstallationFactory.build(installation_id="id-4", owner="owner_4", vendor=GITHUB),
        ],
    }

    mocker.patch.object(
        src.lib.cores.handle_jit_event_core.TenantService,
        "get_installations_by_vendor",
        side_effect=lambda *args, **kwargs: installations.get(kwargs["vendor"], []),
    )

    result = _get_tenant_installations_grouped_by_vendor_and_owner("tenant", "id123", vendors)
    possible_vendors = vendors.intersection(installations.keys())
    assert {key[0] for key in result} == set(possible_vendors)
    for vendor in possible_vendors:
        for installation in installations[vendor]:
            assert result[(vendor, installation.owner)] == installation


def test__get_filtered_jobs_from_filtered_workflows(mocker: MockerFixture) -> None:
    filtered_workflows = [
        FilteredWorkflowFactory.build(
            workflow_slug="slug-1", raw_workflow_template={PARSED_CONTENT: {JOBS: {"job-1-1": {}, "job-1-2": {}}},
                                                           CONTENT: yaml.dump({JOBS: {"job-1-1": {}, "job-1-2": {}}})}
        ),
        FilteredWorkflowFactory.build(
            workflow_slug="slug-2",
            raw_workflow_template={PARSED_CONTENT: {JOBS: {"job-2-1": {}}},
                                   CONTENT: yaml.dump({JOBS: {"job-2-1": {}}})}
        ),
        FilteredWorkflowFactory.build(
            workflow_slug="slug-3",
            raw_workflow_template={PARSED_CONTENT: {JOBS: {"job-3-1": {}, "job-3-2": {}, "job-3-3": {}}},
                                   CONTENT: yaml.dump({JOBS: {"job-3-1": {}, "job-3-2": {}, "job-3-3": {}}})}
        ),
    ]

    mock_get_filtered_jobs: MagicMock = mocker.patch(
        "src.lib.cores.enrich_core.filter_jobs",
        side_effect=lambda *args: args[0] if set(args[0]).intersection({"job-1-1", "job-1-2", "job-2-1"}) else {},
    )

    result = _get_filtered_jobs_from_filtered_workflows(
        filtered_workflows, JitEventFactory.build(), TriggerFilterAttributes()
    )

    assert mock_get_filtered_jobs.called
    assert mock_get_filtered_jobs.call_count == 3

    assert len(result) == 3
    for job in result:
        assert isinstance(job, JobTemplateWrapper)

    assert {job.job_name for job in result} == {"job-1-1", "job-1-2", "job-2-1"}

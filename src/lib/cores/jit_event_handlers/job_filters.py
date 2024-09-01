from typing import List

from jit_utils.event_models import JitEvent
from jit_utils.lambda_decorators.feature_flags import evaluate_feature_flag
from jit_utils.logger import logger
from jit_utils.models.execution_context import CI_RUNNERS
from jit_utils.models.github.github_status import GithubStatus
from jit_utils.models.tenant.entities import Installation

from src.lib.clients import GithubServiceClient
from src.lib.constants import FEATURE_FLAG_STOP_EXECUTIONS_ON_GH_OUTAGE, GITHUB
from src.lib.cores.jit_event_handlers.trigger_filter import TriggerFilter
from src.lib.models.trigger import JobTemplateWrapper, WorkflowTemplateWrapper


class JobNamesTriggerFilter(TriggerFilter[JobTemplateWrapper]):
    def filter(self, elements: List[JobTemplateWrapper]) -> List[JobTemplateWrapper]:
        # If no specific job names to filter, return all elements
        if not self.trigger_filters.job_names:
            return elements

        # Filter and return only those jobs whose names are in the specified job names
        return [job for job in elements if job.job_name in self.trigger_filters.job_names]


class JobGitHubOutageTriggerFilter(TriggerFilter[JobTemplateWrapper]):
    def filter(self, jobs: List[JobTemplateWrapper]) -> List[JobTemplateWrapper]:
        """
            Filter out jobs that are not GitHub runner jobs if we are in outage mode

            :param jobs: The jobs to filter

            :return: The filtered jobs
        """
        logger.info("Filtering out github runner jobs if we are in outage mode")
        should_stop_github_runner_executions_on_outage: bool = evaluate_feature_flag(
            feature_flag_key=FEATURE_FLAG_STOP_EXECUTIONS_ON_GH_OUTAGE,
            payload={"key": self.tenant_id},
            local_test_value=False,
            raise_exception=False,
            default_value=False,
        )
        if not should_stop_github_runner_executions_on_outage:
            logger.info("Feature flag is off, not filtering out github runner jobs")
            return jobs

        github_status = GithubServiceClient().get_latest_github_status_alert(self.tenant_id).status
        logger.info(f"Github status: {github_status=}")
        if github_status == GithubStatus.Outage:
            logger.info("Github is down, filtering out github runner jobs")
            filtered_jobs = [job for job in jobs if job.get_runner() not in CI_RUNNERS]
        else:
            logger.info("Github is up, not filtering out github runner jobs")
            filtered_jobs = jobs

        return filtered_jobs


class JobsProcessor:
    def __init__(self, jit_event: JitEvent, installations: List[Installation]):
        self.jit_event = jit_event
        self.filters: List[TriggerFilter] = [
            JobNamesTriggerFilter(jit_event)
        ]

        # Add the GitHub outage filter if there is an active GitHub installation
        for installation in installations:
            if installation.vendor == GITHUB and installation.is_active:
                self.filters.append(JobGitHubOutageTriggerFilter(jit_event))
                break

    def process_and_filter_jobs(self, workflows: List[WorkflowTemplateWrapper]) -> List[JobTemplateWrapper]:
        filtered_jobs = []
        for workflow in workflows:
            for job_name, job_dict in workflow.jobs.items():
                """
                Sanitizes the workflow content from the workflows templates.
                Content is the yml file content which is not needed for the step function and is very large.
                """
                if "content" in workflow.raw_workflow_template:
                    del workflow.raw_workflow_template["content"]
                if "parsed_content" in workflow.raw_workflow_template:
                    del workflow.raw_workflow_template["parsed_content"]

                job_wrapper = JobTemplateWrapper(
                    plan_item_slug=workflow.plan_item_slug,
                    workflow_slug=workflow.workflow_slug,
                    workflow_name=workflow.workflow_name,
                    job_name=job_name,
                    depends_on_slugs=workflow.depends_on_slugs,
                    workflow_template=workflow.raw_workflow_template,
                    raw_job_template=job_dict,
                )

                if self.is_job_relevant(job_wrapper):
                    filtered_jobs.append(job_wrapper)

        logger.info(f"After processing and filtering, remained with: {len(filtered_jobs)} jobs")
        return filtered_jobs

    def is_job_relevant(self, job: JobTemplateWrapper) -> bool:
        # Apply each filter to the job. If any filter fails, the job is not relevant.
        for job_filter in self.filters:
            if not job_filter.filter([job]):
                return False

        # If all filters pass, the job is relevant
        return True

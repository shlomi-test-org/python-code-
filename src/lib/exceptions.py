from http import HTTPStatus
from typing import List

from jit_utils.lambda_decorators.status_code_wrapper import StatusCodeException
from jit_utils.models.common.responses import ErrorResponse

from src.lib.models.trigger import JobTemplateWrapper


class HandleJitEventException(Exception):
    def __init__(self, *, message: str):
        self.message = message
        super().__init__(self.message)


class NoValidGithubInstallationException(Exception):
    def __init__(self, *, message: str):
        self.message = message
        super().__init__(self.message)


class JitEventLifeCycleDBEntityNotFoundException(StatusCodeException):
    def __init__(self, *, tenant_id: str, jit_event_id: str):
        self.status_code = HTTPStatus.NOT_FOUND
        self.error_response = ErrorResponse(
            error="NOT_FOUND",
            message=f"Jit Event not found for {tenant_id=}, {jit_event_id=}"
        )


class JitEventLifeCycleNonFinalStatusCompleteAttempt(Exception):
    def __init__(self, *, status: str):
        self.message = f"Cannot complete Jit event life cycle with non final status: {status}"
        super().__init__(self.message)


class JitEventIDNotProvidedException(StatusCodeException):
    def __init__(self) -> None:
        self.status_code = HTTPStatus.BAD_REQUEST
        self.error_response = ErrorResponse(
            error="BAD_REQUEST",
            message="jit_event_id is required in path parameters"
        )


class WorkflowJobNotInFilteredJobsException(StatusCodeException):
    def __init__(self, filtered_jobs: List[JobTemplateWrapper], workflow_slug: str, job_name: str) -> None:
        self.message = f"Could not find {workflow_slug}, {job_name} in {filtered_jobs}"


class FailedPRJitEventWatchdogException(Exception):
    pass

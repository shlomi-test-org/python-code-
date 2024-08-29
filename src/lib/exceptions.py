from enum import Enum
from typing import Dict
from typing import List

from jit_utils.event_models.trigger_event import TriggerExecutionEvent

from src.lib.models.execution_models import FailedTriggersEvent, GetExecutionsFilters


class DBException(Exception):
    """
    Raise if DB exception occurred.
    """

    def __init__(self, *, status, message):
        self.status = status
        self.message = message
        super().__init__(self.message)


class ExecutionNotExistException(Exception):
    """Execution not exist in the DB"""

    def __init__(
            self,
            *,
            tenant_id: str,
            jit_event_id: str,
            execution_id: str,
            message: str = None,
    ):
        self.tenant_id = tenant_id
        self.jit_event_id = jit_event_id
        self.execution_id = execution_id
        self.message = message or f"Execution not exist in the DB. {tenant_id=} {jit_event_id=} {execution_id=}"

        super().__init__(self.message)


class ExecutionDataNotFoundException(Exception):
    def __init__(
            self,
            *,
            tenant_id: str,
            jit_event_id: str,
            execution_id: str,
            message: str = None,
    ):
        self.tenant_id = tenant_id
        self.jit_event_id = jit_event_id
        self.execution_id = execution_id
        self.message = message or f"Execution data not found in the DB. {tenant_id=} {jit_event_id=} {execution_id=}"

        super().__init__(self.message)


class ExecutionUpdateException(Exception):
    def __init__(
            self,
            *,
            tenant_id: str,
            jit_event_id: str,
            execution_id: str,
            message: str = None,
    ):
        self.tenant_id = tenant_id
        self.jit_event_id = jit_event_id
        self.execution_id = execution_id
        self.message = message or (f"Exception occurred during updating execution in the DB. "
                                   f"{tenant_id=} {jit_event_id=} {execution_id=}")

        super().__init__(self.message)


class StatusTransitionException(Exception):
    """
    Raise if the error occurred due to misuse of the service.
    Misuse of the service could be for example - trying to "register" a completed execution.
    """

    def __init__(self, *, message: str, error_body: Dict):
        self.message = message
        self.error_body = error_body
        super().__init__(self.message)


class MultipleCompletesExceptions(Exception):
    """
    Raise if we tried to update a completed execution to another completed status
    """

    def __init__(self, *, message: str):
        self.message = message
        super().__init__(self.message)


class NonJitTaskError(Exception):
    """
    Raise if couldn't find pricing in AWS
    """

    def __init__(self, *, event, extra_msg):
        self.event = event
        self.extra_msg = extra_msg
        super().__init__()


class EventMissingStartOrFinish(Exception):
    """
    Raise if couldn't find pricing in AWS
    """

    def __init__(self, *, event):
        self.event = event
        super().__init__()


class UploadOutputFilesTooManyFiles(Exception):
    pass


class StatusErrors(Enum):
    TOO_MANY_FILES_TO_UPLOAD = "Too many files to upload"
    NO_ARTIFACTS = "No artifacts"


class FailedTriggersExceptions(Exception):
    """
    Raised if we failed to trigger executions during the trigger-execution lambda
    """

    def __init__(self, failed_trigger_execution_events: List[TriggerExecutionEvent]):
        self.failed_trigger_execution_events = failed_trigger_execution_events
        super().__init__(
            FailedTriggersEvent(
                failure_message="Failed to trigger executions",
                failed_triggers=failed_trigger_execution_events,
            ).json()
        )


class InvalidTokenException(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class InvalidExecutionStatusException(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class InvalidGetExecutionDataRequest(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class ExecutionDataAlreadyRetrievedError(Exception):
    """Raised when trying to update an execution data retrieved_at that already has retrieved_at attribute"""
    pass


class BadAccessPatternException(Exception):
    """Raised when we are using bad filters to get executions"""

    def __init__(self, *, tenant_id: str, filters: GetExecutionsFilters):
        self.tenant_id = tenant_id
        self.filters = filters
        self.message = f"filters={self.filters} are not supported by any access pattern"

        super().__init__(self.message)

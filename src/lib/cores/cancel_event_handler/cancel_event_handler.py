from abc import ABC
from abc import abstractmethod
from typing import Dict
from typing import Generic
from typing import List
from typing import TypeVar

from jit_utils.models.execution import ExecutionStatus
from pydantic import BaseModel

from src.lib.cores.execution_events import send_task_completion_event
from jit_utils.models.execution import Execution

T = TypeVar("T", bound=BaseModel)


class CancelEventHandler(ABC, Generic[T]):
    """
    This class is an interface for handling a cancel event that might affect executions in the system
    """
    def __init__(self, event_body: Dict):
        self._event_body: T = self.parse_event_body(event_body)

    def handle(self) -> None:
        to_cancel = self.get_executions_to_cancel()
        self.cancel_executions(to_cancel)

    @abstractmethod
    def parse_event_body(self, event_body: Dict) -> T:
        raise NotImplementedError

    @property
    def tenant_id(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def get_executions_to_cancel(self) -> List[Execution]:
        raise NotImplementedError

    def get_error_message(self) -> str:
        raise NotImplementedError

    def cancel_executions(self, executions: List[Execution]) -> None:
        for execution in executions:
            send_task_completion_event(
                completion_status=ExecutionStatus.CANCELED,
                tenant_id=execution.tenant_id,
                execution_id=execution.execution_id,
                jit_event_id=execution.jit_event_id,
                error_message=self.get_error_message(),
            )

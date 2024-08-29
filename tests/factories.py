from jit_utils.event_models import CodeRelatedJitEvent
from jit_utils.models.execution_context import ExecutionContextWorkflow
from jit_utils.models.execution_context import RunnerConfig
from jit_utils.models.execution_context import WorkflowJob
from pydantic_factories import ModelFactory

from jit_utils.models.execution import Execution
from src.lib.models.execution_models import ExecutionData
from src.lib.models.execution_models import ExecutionDispatchUpdateEvent


class ExecutionFactory(ModelFactory):
    __model__ = Execution


class ExecutionDispatchUpdateEventFactory(ModelFactory):
    __model__ = ExecutionDispatchUpdateEvent


class WorkflowJobFactory(ModelFactory):
    __model__ = WorkflowJob


class ExecutionContextWorkflowFactory(ModelFactory):
    __model__ = ExecutionContextWorkflow


class RunnerConfigFactory(ModelFactory):
    __model__ = RunnerConfig


class CodeRelatedJitEventFactory(ModelFactory):
    __model__ = CodeRelatedJitEvent


class ExecutionDataFactory(ModelFactory):
    __model__ = ExecutionData

from uuid import uuid4

from jit_utils.models.execution import Execution, ExecutionStatus
from pydantic_factories import ModelFactory


class ExecutionFactory(ModelFactory):
    __model__ = Execution
    tenant_id = str(uuid4())
    context = None


def build_execution(status: ExecutionStatus, has_findings: bool = False) -> Execution:
    return ExecutionFactory.build(control_name='control_name', status=status, has_findings=has_findings)

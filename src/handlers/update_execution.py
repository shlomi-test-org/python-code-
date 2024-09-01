import json
from http import HTTPStatus
from datetime import datetime
from typing import cast, Dict, Union

from dateutil.parser import parse
from aws_lambda_typing.context import Context
from py_api import api_documentation, Method, Request, Response
from jit_utils.models.execution import ExecutionStatus, Execution
from aws_lambda_typing.events import APIGatewayProxyEventV2 as APIEvent
from jit_utils.logger import custom_labels, CustomLabel, logger, logger_customer_id
from jit_utils.models.common.responses import InternalErrorResponse, ErrorCode, EmptyResponse
from jit_utils.lambda_decorators import (dynamodb_tenant_isolation, status_code_wrapper, DynamodbIsolationRule,
                                         exception_handler, feature_flags_init_client, general_tenant_isolation,
                                         lambda_warmup_handler, request_headers_keys, response_wrapper)

from src.lib.models.workflow_models import WorkflowStatus
from src.lib.constants import EXECUTION_TABLE_NAME, RESOURCES_TABLE_NAME
from src.lib.exceptions import StatusTransitionException, ExecutionUpdateException
from src.lib.cores.executions_core import register_execution, update_control_status, update_execution_run_id
from src.lib.models.execution_models import StatusUpdateConflictError, UpdateRequest, VendorJobIDUpdateRequest


@exception_handler()
@lambda_warmup_handler
@request_headers_keys
@response_wrapper
@dynamodb_tenant_isolation(
    rules=[
        DynamodbIsolationRule(
            table_name=EXECUTION_TABLE_NAME,
            actions=["dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:UpdateItem"],
        )
    ]
)
@status_code_wrapper(
    error_to_response={
        ExecutionUpdateException: (
                HTTPStatus.INTERNAL_SERVER_ERROR,
                InternalErrorResponse(
                    error=ErrorCode.INTERNAL_SERVER_ERROR.value,
                    message="Failed to update execution"
                )),
    }
)
@logger_customer_id(auto=True)
@custom_labels([CustomLabel(field_name='execution_id', label_name='execution_id', auto=True),
                CustomLabel(field_name='jit_event_id', label_name='jit_event_id', auto=True)])
@api_documentation(
    post=Method(
        description="When a job is created, this function is called to register the job",
        path_parameters=[],
        request_body=Request(
            description="Register handler request body",
            schema=UpdateRequest,
        ),
        method_responses={
            HTTPStatus.OK: Response(
                schema=Union[Execution, Dict],
                title="RegisterHandlerResponse",
                description="Patch action finding successfully",
            ),
            HTTPStatus.CONFLICT: Response(
                title='STATUS_UPDATE_CONFLICT',
                schema=StatusUpdateConflictError,
                description="Invalid parameters passed",
            )
        },
    )
)
def register_handler(event: APIEvent, _: Context):
    """
    This function is called when a job is created.
    """
    logger.info(f"Registering job {event=}")
    tenant_id = cast(str, event['requestContext']['authorizer']['tenant_id'])

    payload = json.loads(event["body"])
    now = datetime.utcnow()
    register_request = UpdateRequest(**{**payload,
                                        "original_request": payload,
                                        "registered_at": now.isoformat(timespec='microseconds'),
                                        "registered_at_ts": int(now.timestamp())
                                        })

    if register_request.tenant_id != tenant_id:
        raise Exception(f'Tenant ID from request body ({register_request.tenant_id}) '
                        f'does not match tenant ID from authorizer ({tenant_id})')
    try:
        updated_execution = register_execution(register_request)
    except StatusTransitionException as ex:
        logger.warning(f"Got StatusTransitionException={ex}, skipping operation")
        return HTTPStatus.CONFLICT, ex.error_body
    return HTTPStatus.OK, updated_execution or {}


@exception_handler()
@lambda_warmup_handler
@request_headers_keys
@response_wrapper
@dynamodb_tenant_isolation(
    rules=[
        DynamodbIsolationRule(
            table_name=EXECUTION_TABLE_NAME,
            actions=["dynamodb:UpdateItem", "dynamodb:GetItem"]
        ),
        DynamodbIsolationRule(
            table_name=RESOURCES_TABLE_NAME,
            actions=["dynamodb:UpdateItem", "dynamodb:DeleteItem"]
        ),
    ]
)
@feature_flags_init_client()
@logger_customer_id(auto=True)
@custom_labels([CustomLabel(field_name='execution_id', label_name='execution_id', auto=True),
                CustomLabel(field_name='jit_event_id', label_name='jit_event_id', auto=True)])
@api_documentation(
    post=Method(
        description="When a job is completed, this function is called to update the job status",
        path_parameters=[],
        request_body=Request(
            description="Update handler request body",
            schema=UpdateRequest,
        ),
        method_responses={
            HTTPStatus.OK: Response(
                schema=Union[Execution, Dict],
                title="UpdateControlStatusResponse",
                description="Execution status updated successfully",
            ),
            HTTPStatus.BAD_REQUEST: Response(
                title='UPDATE_CONTROL_STATUS_BAD_REQUEST',
                schema=EmptyResponse,
                description="Invalid parameters passed",
            )
        },
    )
)
def update_control_status_handler(event: APIEvent, _: Context):
    """
    This function is called when a job is completed.
    """
    logger.info(f"Completing job {event=}")
    tenant_id = cast(str, event['requestContext']['authorizer']['tenant_id'])

    payload = json.loads(event["body"])

    if payload["status"] == WorkflowStatus.EXECUTION_FAILURE.value:
        payload["status"] = ExecutionStatus.FAILED

    now = payload.get("completed_at") or datetime.utcnow().isoformat()
    request = UpdateRequest(**{**payload,
                               "tenant_id": tenant_id,
                               "completed_at": now,
                               "completed_at_ts": int(parse(now).timestamp()),
                               "original_request": payload})
    logger.info(f"Update control status: {request}")
    updated_execution = update_control_status(request)
    return HTTPStatus.OK, updated_execution or None


@exception_handler()
@lambda_warmup_handler
@request_headers_keys
@response_wrapper
@status_code_wrapper(
    catch_input_validation=True,
    error_to_response={
        ExecutionUpdateException: (
                HTTPStatus.INTERNAL_SERVER_ERROR,
                InternalErrorResponse(
                    error=ErrorCode.INTERNAL_SERVER_ERROR.value,
                    message="Failed to update execution"
                )),
    }
)
@general_tenant_isolation(
    rules=[
        DynamodbIsolationRule(
            table_name=EXECUTION_TABLE_NAME,
            actions=["dynamodb:UpdateItem", "dynamodb:GetItem"],
        )
    ]
)
@logger_customer_id(auto=True)
@custom_labels([CustomLabel(field_name='execution_id', label_name='execution_id', auto=True),
                CustomLabel(field_name='jit_event_id', label_name='jit_event_id', auto=True)])
@api_documentation(
    post=Method(
        description="Link vendor job ID to existing execution when the vendor job starts running",
        path_parameters=[],
        request_body=Request(
            description="Vendor job start handler request body",
            schema=VendorJobIDUpdateRequest,
        ),
        method_responses={
            HTTPStatus.OK: Response(
                schema=EmptyResponse,
                title="StartHandlerResponse",
                description="Execution run_id updated successfully",
            )
        },
    )
)
def vendor_job_start_handler(event: APIEvent, _: Context):
    """
    Link vendor job ID to existing execution when the vendor job starts running.
    """
    logger.info(f'Got vendor job started event {event=}')
    tenant_id = event["requestContext"]["authorizer"]["tenant_id"]
    payload = json.loads(event["body"])
    request = VendorJobIDUpdateRequest(**{**payload, "tenant_id": tenant_id})
    logger.info(f"Update execution run_id: {request}")
    update_execution_run_id(request)
    return HTTPStatus.OK, {}

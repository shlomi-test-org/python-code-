import datetime
from typing import Any, Dict, List, Optional, Tuple

from pydantic import parse_obj_as

from jit_utils.logger import logger, alert
from jit_utils.logger.logger import add_label
from jit_utils.models.execution import (BaseExecutionIdentifiers,
                                        BackgroundJobOutput,
                                        ResourceType,
                                        ExecutionStatus,
                                        Execution, ExecutionError)
from jit_utils.models.execution_context import Runner, CI_RUNNERS
from jit_utils.models.findings.events import UploadFindingsStatus
from jit_utils.utils.casting import convert_floats_to_decimals

from src.lib import constants as c
from src.lib.constants import EXECUTION_NOT_FOUND_ERROR_ALERT, MAX_BATCH_GET_SIZE, PK
from src.lib.constants import SK
from src.lib.data.db_table import DbTable
from src.lib.exceptions import ExecutionDataAlreadyRetrievedError, ExecutionUpdateException
from src.lib.exceptions import ExecutionDataNotFoundException
from src.lib.exceptions import ExecutionNotExistException
from src.lib.exceptions import MultipleCompletesExceptions
from src.lib.exceptions import StatusTransitionException
from src.lib.models.execution_models import ExecutionData, MultipleExecutionsIdentifiers
from src.lib.models.execution_models import ExecutionDataEntity
from src.lib.models.execution_models import ExecutionEntity
from src.lib.models.execution_models import STATUSES_WITH_TIMEOUT
from src.lib.models.execution_models import StatusUpdateConflictError
from src.lib.models.execution_models import UpdateAttributes
from src.lib.models.execution_models import UpdateRequest


class ExecutionsManager(DbTable):
    TABLE_NAME = c.EXECUTION_TABLE_NAME

    def __init__(self):
        super().__init__(self.TABLE_NAME)

    def create_execution(self, execution: Execution) -> Execution:
        """
        Creates an execution in the database.
        """

        logger.info(f"Creating execution in database: {execution}")
        # Partitions
        pk = gsi9pk_tenant_id_jit_event_id = gsi7pk_tenant_jit_event_id = self.get_key(
            tenant=execution.tenant_id, jit_event=execution.jit_event_id
        )  # high cardinality
        gsi2pk = gsi8pk_tenant_id_status = self.get_key(
            tenant=execution.tenant_id, status=execution.status
        )  # medium cardinality
        gsi3pk = self.get_key(tenant=execution.tenant_id, plan_item=execution.plan_item_slug)  # medium cardinality
        gsi4pk = self.get_key(
            tenant=execution.tenant_id, plan_item=execution.plan_item_slug, status=execution.status
        )  # medium-high cardinality
        gsi5pk = self.get_key(
            tenant=execution.tenant_id,
            runner=execution.job_runner,
            status=execution.status,
        )  # medium-high cardinality

        # sort keys
        sk = self.get_key(execution=execution.execution_id)
        gsi2sk = gsi3sk = gsi4sk = gsi7sk_created_at = execution.created_at
        gsi5sk = self.get_key(priority=execution.priority, created_at=execution.created_at)
        gsi8sk_asset_id_created_at = self.get_key(asset_id=execution.asset_id, created_at=execution.created_at)
        gsi9sk_job_name_created_at = self.get_key(job_name=execution.job_name, created_at=execution.created_at)

        executions_record = ExecutionEntity(
            PK=pk,
            SK=sk,
            GSI2PK=gsi2pk,
            GSI2SK=gsi2sk,
            GSI3PK=gsi3pk,
            GSI3SK=gsi3sk,
            GSI4PK=gsi4pk,
            GSI4SK=gsi4sk,
            GSI5PK=gsi5pk,
            GSI5SK=gsi5sk,
            GSI7PK_TENANT_JIT_EVENT_ID=gsi7pk_tenant_jit_event_id,
            GSI7SK_CREATED_AT=gsi7sk_created_at,
            GSI8PK_TENANT_ID_STATUS=gsi8pk_tenant_id_status,
            GSI8SK_ASSET_ID_CREATED_AT=gsi8sk_asset_id_created_at,
            GSI9PK_TENANT_ID=gsi9pk_tenant_id_jit_event_id,
            GSI9SK_JIT_EVENT_ID_JOB_NAME_CREATED_AT=gsi9sk_job_name_created_at,
            **execution.dict(exclude_none=True),
            ttl=int(datetime.datetime.utcnow().timestamp()) + c.EXECUTION_TTL
        )

        # Prepare a list of GSI keys to be logged
        gsi_keys = [attr for attr in dir(executions_record) if attr.startswith('GSI') or attr in ['PK', 'SK']]
        # Construct a log message dynamically
        log_message = ', '.join([f'{key}={getattr(executions_record, key)}' for key in gsi_keys])
        # Log the message
        logger.info(f"Execution entity GSIs: {log_message}")

        response = self.table.put_item(Item=convert_floats_to_decimals(executions_record.dict(exclude_none=True)))
        self._verify_response(response)

        return execution

    def update_execution(
            self,
            update_request: UpdateRequest,
            plan_item_slug: str,
            job_runner: Runner,
    ) -> UpdateAttributes:
        """
        Updates an execution in the database.
        This method will be called on register and complete events.
        For now, until the event service will be implemented, the execution will be updated only on completed
        """
        logger.info(f"Updating execution in database: {update_request}")
        update_kwargs = self._generate_update_kwargs(job_runner, plan_item_slug, update_request)
        item = self._update_execution_from_request(update_kwargs, update_request)
        return UpdateAttributes(**item)

    def _update_execution_from_request(self, update_kwargs: dict, update_request: UpdateRequest) -> Dict:
        # Prevents Race condition of allocate-runner-resources.
        if update_request.status in (ExecutionStatus.RUNNING, ExecutionStatus.RETRY):
            condition_expression: str = "#status IN (:status_dispatched, :status_dispatching)"
            update_kwargs["ExpressionAttributeValues"][":status_dispatched"] = ExecutionStatus.DISPATCHED.value
            update_kwargs["ExpressionAttributeValues"][":status_dispatching"] = ExecutionStatus.DISPATCHING.value
            update_kwargs["ConditionExpression"] = condition_expression
        elif update_request.status == ExecutionStatus.DISPATCHED:  # Support Dispatched status
            condition_expression = "#status = :dispatching_status"
            update_kwargs["ExpressionAttributeValues"][":dispatching_status"] = ExecutionStatus.DISPATCHING.value
            update_kwargs["ConditionExpression"] = condition_expression
        elif update_request.status == ExecutionStatus.CANCELED:
            condition_expression: str = "#status = :status_pending"
            update_kwargs["ExpressionAttributeValues"][":status_pending"] = ExecutionStatus.PENDING.value
            update_kwargs["ConditionExpression"] = condition_expression
        elif update_request.status == ExecutionStatus.COMPLETED:
            condition_expression: str = "#status IN (:status_running, :status_dispatched, :status_dispatching)"
            update_kwargs["ExpressionAttributeValues"][":status_running"] = ExecutionStatus.RUNNING.value
            update_kwargs["ExpressionAttributeValues"][":status_dispatched"] = ExecutionStatus.DISPATCHED.value
            update_kwargs["ExpressionAttributeValues"][":status_dispatching"] = ExecutionStatus.DISPATCHING.value
            update_kwargs["ConditionExpression"] = condition_expression
        elif update_request.status == ExecutionStatus.WATCHDOG_TIMEOUT:
            condition_expression: str = "#status IN (:status_dispatched, :status_dispatching, :status_running)"
            update_kwargs["ExpressionAttributeValues"][":status_dispatched"] = ExecutionStatus.DISPATCHED.value
            update_kwargs["ExpressionAttributeValues"][":status_dispatching"] = ExecutionStatus.DISPATCHING.value
            update_kwargs["ExpressionAttributeValues"][":status_running"] = ExecutionStatus.RUNNING.value
            update_kwargs["ConditionExpression"] = condition_expression

        try:
            response = self.table.update_item(**update_kwargs)
        except self.client.exceptions.ConditionalCheckFailedException as ex:
            logger.warning(f"Failed to update due to condition failure, check current execution object. {ex=}")
            self._handle_update_status_condition_check_failed(
                update_request.tenant_id,
                update_request.jit_event_id,
                update_request.execution_id,
                update_request.status,
            )
        else:
            self._verify_response(response)
            logger.info(f"{response=}")
            item = response.get("Attributes", None)
            logger.info(f"{item=}")
            if not item:
                raise Exception(f"Failed to parse updated execution: {response}")
            return item

    @staticmethod
    def _is_valid_status_transition(from_status: ExecutionStatus, to_status: ExecutionStatus) -> bool:
        """
        this function will determine weather or not a transition from one execution status to another is valid,
        based on the rule that an execution can't go back in status lifecycle.
        PENDING->DISPATCHING->DISPATCHED->RUNNING->COMPLETED/FAILED/CONTROL_TIMEOUT/WATCHDOG_TIMEOUT
        """
        return ExecutionStatus(from_status) < ExecutionStatus(to_status)

    def _handle_update_status_condition_check_failed(
            self,
            tenant_id: str,
            jit_event_id: str,
            execution_id: str,
            new_status: ExecutionStatus,
    ) -> None:
        execution = self.get_execution_by_jit_event_id_and_execution_id(
            tenant_id=tenant_id,
            jit_event_id=jit_event_id,
            execution_id=execution_id,
        )
        message = f"Tried to update '{execution.status}' execution to {new_status=}"
        logger.warning(message)
        if (
                ExecutionStatus(execution.status).get_value() ==
                ExecutionStatus(new_status).get_value() ==
                ExecutionStatus.COMPLETED.get_value()
        ):
            logger.warning(f"Tried complete the execution more than once. {message}")
            raise MultipleCompletesExceptions(message=message)
        if not self._is_valid_status_transition(
                from_status=ExecutionStatus(execution.status),
                to_status=ExecutionStatus(new_status),
        ):
            # Sometimes the execution is already in the target status or even ahead, callers should catch this
            # exception, if they want to handle it.
            raise StatusTransitionException(
                message=message,
                error_body=StatusUpdateConflictError(
                    message=message,
                    from_status=execution.status,
                    to_status=new_status,
                ).dict()
            )

        # This is an unexpected scope to enter, as the target status is valid for the current status, raising loudly
        add_label("UNEXPECTED_CONDITIONAL_CHECK_FAILED", "True")
        raise

    def _generate_update_kwargs(
            self, job_runner: Runner, plan_item_slug: str, update_request: UpdateRequest
    ) -> Dict:
        pk, sk = self._get_execution_keys(
            update_request.tenant_id, update_request.jit_event_id, update_request.execution_id
        )
        gsi2pk = self.get_key(tenant=update_request.tenant_id, status=update_request.status)
        gsi4pk = self.get_key(
            tenant=update_request.tenant_id, plan_item=plan_item_slug, status=update_request.status
        )
        gsi5pk = self.get_key(
            tenant=update_request.tenant_id, runner=job_runner, status=update_request.status
        )
        attributes_to_update = UpdateAttributes(**update_request.dict())
        attributes_to_update_dict = attributes_to_update.dict(exclude_none=True)
        # Updating the GSI2, GSI4, GSI5 because they contain `status`, which until the complete event was None
        attributes_to_update_dict[c.GSI2PK] = gsi2pk
        attributes_to_update_dict[c.GSI4PK] = gsi4pk
        attributes_to_update_dict[c.GSI5PK] = gsi5pk
        attributes_to_update_dict[c.GSI8PK_TENANT_ID_STATUS] = self.get_key(
            tenant_id=update_request.tenant_id, status=update_request.status
        )

        attributes_to_remove = []
        # updating the timeout GSI should happen only if we are updating the status
        # we should remove the timeout GSI only if we change the status and the status shouldn't have timeout value
        if update_request.status not in STATUSES_WITH_TIMEOUT:
            attributes_to_remove = [c.GSI6PK, c.GSI6SK, 'execution_timeout']
        # the status should have timeout value - we need to save it to the timeout GSI
        elif update_request.execution_timeout:
            attributes_to_update_dict[c.GSI6PK] = c.GSI6PK_VALUE
            attributes_to_update_dict[c.GSI6SK] = update_request.execution_timeout
        # the status should have timeout value, but it wasn't passed to this function
        else:
            raise ValueError('Trying to update status with no compatible execution_timeout value')

        set_expression = (
            f"SET {', '.join([f'#{attribute} = :{attribute}' for attribute in attributes_to_update_dict])}"
        )
        remove_expression = f"REMOVE {', '.join(attributes_to_remove)}" if attributes_to_remove else None
        update_expression = f"{set_expression} {remove_expression}" if remove_expression else set_expression

        expression_attribute_names = {f"#{attribute}": attribute for attribute in attributes_to_update_dict}
        expression_attribute_values = {f":{attribute}": value for attribute, value in attributes_to_update_dict.items()}

        return {
            'Key': {c.PK: pk, c.SK: sk},
            'UpdateExpression': update_expression,
            'ExpressionAttributeNames': expression_attribute_names,
            'ExpressionAttributeValues': expression_attribute_values,
            'ReturnValues': 'ALL_NEW',
        }

    def update_findings_upload_status(
            self,
            tenant_id: str,
            jit_event_id: str,
            execution_id: str,
            upload_findings_status: UploadFindingsStatus,
            plan_items_with_findings: List[str],
            has_findings: bool,
    ) -> Optional[Execution]:
        """
        Updates an execution's upload findings status.
        """
        logger.info(f"Updating upload findings status for execution in database: {upload_findings_status=}")
        pk, sk = self._get_execution_keys(tenant_id, jit_event_id, execution_id)

        response = self.table.update_item(
            Key={c.PK: pk, c.SK: sk},
            UpdateExpression=(
                "SET #upload_findings_status = :upload_findings_status, "
                "#plan_items_with_findings = :plan_items_with_findings, "
                "#has_findings = :has_findings"
            ),
            ExpressionAttributeNames={
                "#upload_findings_status": "upload_findings_status",
                "#plan_items_with_findings": "plan_items_with_findings",
                "#status": "status",
                "#has_findings": "has_findings",
            },
            ExpressionAttributeValues={
                ":upload_findings_status": upload_findings_status,
                ":plan_items_with_findings": plan_items_with_findings,
                ":status": ExecutionStatus.RUNNING,
                ":has_findings": has_findings,
            },
            ConditionExpression="attribute_exists(PK) and attribute_exists(SK) and #status = :status",
            ReturnValues="ALL_NEW",
        )
        self._verify_response(response)
        logger.info(f"{response=}")

        return Execution(**response.get("Attributes"))

    def _get_execution_keys(self, tenant_id: str, jit_event_id: str, execution_id: str) -> Tuple[str, str]:
        pk = self.get_key(tenant=tenant_id, jit_event=jit_event_id)
        sk = self.get_key(execution=execution_id)
        return pk, sk

    def _get_execution_data_keys(self, tenant_id: str, jit_event_id: str, execution_id: str) -> Tuple[str, str]:
        pk = self.get_key(tenant=tenant_id, jit_event=jit_event_id)
        sk = self.get_key(execution=execution_id, entity="execution_data")
        return pk, sk

    def update_execution_run_id(self, tenant_id: str, jit_event_id: str, execution_id: str, run_id: str) -> None:
        """
        Updates an execution's run id.
        """
        logger.info(f"Updating run_id for execution in database: {run_id=}")
        pk, sk = self._get_execution_keys(tenant_id, jit_event_id, execution_id)

        try:
            response = self.table.update_item(
                Key={c.PK: pk, c.SK: sk},
                UpdateExpression="SET #run_id = :run_id",
                ExpressionAttributeNames={"#run_id": "run_id"},
                ExpressionAttributeValues={":run_id": run_id},
                ConditionExpression="attribute_exists(PK) and attribute_exists(SK)",
                ReturnValues="ALL_NEW",
            )
        except self.client.exceptions.ConditionalCheckFailedException as e:
            raise ExecutionUpdateException(
                tenant_id=tenant_id,
                jit_event_id=jit_event_id,
                execution_id=execution_id,
                message=f"Failed to update run_id for execution: {e}",
            )

        self._verify_response(response)
        logger.info(f"DB response after update: {response=}")

    @staticmethod
    def _create_update_expression(fields_to_update: dict) -> str:
        return f"SET {', '.join([f'#{key} = :{key}' for key in fields_to_update.keys()])}"

    @staticmethod
    def _create_expression_attribute_names_dict(fields_to_update: dict) -> Dict[str, str]:
        return {f"#{key}": key for key in fields_to_update.keys()}

    @staticmethod
    def _create_expression_attribute_values_dict(fields_to_update: Dict[str, Any]) -> Dict[str, Dict]:
        expression_attribute_values: Dict[str, Dict] = {}
        for field in fields_to_update:
            update_value = fields_to_update[field]
            expression_attribute_values[f":{field}"] = update_value
        return expression_attribute_values

    def partially_update_execution(
            self, tenant_id: str, jit_event_id: str, execution_id: str, update_attributes: UpdateAttributes
    ) -> Optional[Execution]:
        """
        Updates an execution's specific fields as in the update_attributes.
        """
        logger.info(f"Updating execution in database: {update_attributes=}")
        pk, sk = self._get_execution_keys(tenant_id, jit_event_id, execution_id)

        fields_to_update = update_attributes.dict(exclude_none=True)
        if fields_to_update:
            logger.info(f"Going to update {execution_id=} with fields={fields_to_update}")
            response = self.table.update_item(
                Key={c.PK: pk, c.SK: sk},
                UpdateExpression=ExecutionsManager._create_update_expression(fields_to_update),
                ExpressionAttributeNames=ExecutionsManager._create_expression_attribute_names_dict(fields_to_update),
                ExpressionAttributeValues=ExecutionsManager._create_expression_attribute_values_dict(fields_to_update),
                ConditionExpression="attribute_exists(PK) and attribute_exists(SK)",
                ReturnValues="ALL_NEW",
            )
            self._verify_response(response)
            logger.info(f"DB response after update: {response=}")
            return Execution(**response.get("Attributes"))

    def update_control_completed_data(
            self,
            tenant_id: str,
            jit_event_id: str,
            execution_id: str,
            control_status: ExecutionStatus,
            has_findings: bool,
            error_body: Optional[str] = None,
            job_output: Optional[BackgroundJobOutput] = None,
            stderr: Optional[str] = None,
            errors: List[ExecutionError] = None,
    ) -> Execution:
        """
        Updates an execution's control status.
        """
        if errors is None:
            errors = []

        logger.info(
            f"Updating control status and has_findings attributes for execution in database: "
            f"{control_status=}, {has_findings=}, {error_body=}, {job_output=}, {errors=}")

        if errors:
            errors = [error.dict() for error in errors]

        update_expression, expression_attribute_names, expression_attribute_values, condition_expression = \
            self._build_control_completed_update_expressions(
                control_status=control_status,
                job_output=job_output,
                stderr=stderr,
                errors=errors,
                error_body=error_body
            )

        response = self._conditionally_update_according_to_has_findings(
            tenant_id=tenant_id,
            execution_id=execution_id,
            jit_event_id=jit_event_id,
            update_expression=update_expression,
            expression_attribute_names=expression_attribute_names,
            expression_attribute_values=expression_attribute_values,
            condition_expression=condition_expression,
            has_findings=has_findings)

        logger.info(f"{response=}")
        self._verify_response(response)

        return Execution(**response.get("Attributes"))

    def _build_control_completed_update_expressions(
            self,
            control_status: ExecutionStatus,
            job_output: Optional[BackgroundJobOutput],
            stderr: Optional[str],
            errors: List[ExecutionError],
            error_body: Optional[str]
    ) -> Tuple[str, Dict[str, str], Dict[str, Any], str]:
        update_expression = (
            'SET #control_status = :control_status, '
            '#job_output = :job_output, '
            '#stderr = :stderr, '
            '#errors = :errors'
        )
        expression_attribute_names = {
            '#control_status': 'control_status',
            '#status': 'status',
            '#job_output': 'job_output',
            '#stderr': 'stderr',
            '#errors': 'errors',
        }
        expression_attribute_values = {
            ':control_status': control_status,
            ':status_running': ExecutionStatus.RUNNING,
            ':status_dispatched': ExecutionStatus.DISPATCHED,
            ':status_dispatching': ExecutionStatus.DISPATCHING,
            ':job_output': job_output,
            ':stderr': stderr,
            ':errors': errors,
        }

        if error_body:
            update_expression += ', #error_body = :error_body'
            expression_attribute_names['#error_body'] = 'error_body'
            expression_attribute_values[':error_body'] = error_body

        # for some cases where control had an error during it's run, we might be missing the "register" operation
        # and the control status would not change to "running". In such cases we would still like to update the
        # control status, and make the execution completed
        condition_expression = (
            "attribute_exists(PK) and attribute_exists(SK)"
            "and #status IN (:status_running, :status_dispatched, :status_dispatching)"
        )

        return update_expression, expression_attribute_names, expression_attribute_values, condition_expression

    def _conditionally_update_according_to_has_findings(
            self,
            tenant_id: str,
            jit_event_id: str,
            execution_id: str,
            update_expression: str,
            expression_attribute_names: dict,
            expression_attribute_values: dict,
            condition_expression: str,
            has_findings: bool
    ):
        """
        Conditionally updates an execution according to the has_findings attribute.
        If the has_findings attribute exists ConditionCheckFailedException will be raised.
        The ConditionCheckFailedException will be caught and the update will be executed without the has_findings
        """
        logger.info("Conditionally updating execution")
        pk, sk = self._get_execution_keys(tenant_id, jit_event_id, execution_id)
        update_attempt_count = 0
        try:
            logger.info(f"Trying to update with has_findings={has_findings}")
            has_findings_update_expression = update_expression + ', #has_findings = :has_findings'
            has_findings_expression_attribute_names = {**expression_attribute_names, '#has_findings': 'has_findings'}
            has_findings_expression_attribute_values = {**expression_attribute_values, ':has_findings': has_findings}

            update_attempt_count += 1
            response = self.table.update_item(
                Key={c.PK: pk, c.SK: sk},
                UpdateExpression=has_findings_update_expression,
                ExpressionAttributeNames=has_findings_expression_attribute_names,
                ExpressionAttributeValues=has_findings_expression_attribute_values,
                ConditionExpression=condition_expression + " and attribute_not_exists(#has_findings)",
                ReturnValues="ALL_NEW",
            )
        except self.table.meta.client.exceptions.ConditionalCheckFailedException:
            # If the condition fails, it means has_findings already exists, so update other attributes
            logger.info("ConditionCheckFailedException was raised, updating without has_findings")
            update_attempt_count += 1
            response = self.table.update_item(
                Key={c.PK: pk, c.SK: sk},
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values,
                ConditionExpression=condition_expression,
                ReturnValues="ALL_NEW",
            )

        add_label("update_execution_attempts", str(update_attempt_count))
        return response

    def generate_update_execution_query(
            self,
            update_request: UpdateRequest,
            plan_item_slug: str,
            resource_type: ResourceType,
    ) -> Dict[str, Any]:
        """
        Generates an update query for the execution table.
        Using it on a migration
        """
        update_kwargs = self._generate_update_kwargs(
            resource_type, plan_item_slug, update_request
        )

        update_execution_query = {
            'Update': {
                'TableName': self.TABLE_NAME,
                'Key': self.convert_python_dict_to_dynamodb_object(update_kwargs['Key']),
                'UpdateExpression': update_kwargs['UpdateExpression'],
                'ExpressionAttributeNames': update_kwargs['ExpressionAttributeNames'],
                'ExpressionAttributeValues': self.convert_python_dict_to_dynamodb_object(
                    update_kwargs['ExpressionAttributeValues']
                ),
            }
        }

        # When allocating a resource, update only an execution that is currently pending
        if update_request.status == ExecutionStatus.DISPATCHING:
            update_execution_query["Update"]["ConditionExpression"] = "#status = :status_pending"
            update_kwargs["ExpressionAttributeValues"][":status_pending"] = ExecutionStatus.PENDING.value
            update_execution_query["Update"]["ExpressionAttributeValues"] = self.convert_python_dict_to_dynamodb_object(
                update_kwargs["ExpressionAttributeValues"]
            )

        return update_execution_query

    def get_execution_by_jit_event_id_and_execution_id(
            self,
            tenant_id: str,
            jit_event_id: str,
            execution_id: str,
            raise_: bool = False,  # TODO: Remove this parameter, and raise an exception by default (better practice)
    ) -> Optional[Execution]:
        """Retrieves an execution from the database by tenant ID, JIT event ID and execution ID.

        If `raise_` is set to `True`, raises an ExecutionNotExistException if the execution is not found.
        """
        logger.info(f"Retrieving execution from database by JIT event ID and run ID: {jit_event_id} and {execution_id}")
        pk, sk = self._get_execution_keys(tenant_id, jit_event_id, execution_id)

        # We do consistent read because we must have this execution available if dispatched.
        response = self.table.get_item(Key={c.PK: pk, c.SK: sk}, ConsistentRead=True)
        self._verify_response(response)

        if 'Item' not in response:
            if raise_ is False:
                return None

            raise ExecutionNotExistException(
                tenant_id=tenant_id,
                jit_event_id=jit_event_id,
                execution_id=execution_id,
            )

        return Execution(**response['Item'])

    def execute_query(self, query_kwargs: Dict, start_key: Dict) -> Tuple[List[Execution], Dict]:
        if start_key:
            query_kwargs["ExclusiveStartKey"] = start_key

        response = self.table.query(**query_kwargs)
        self._verify_response(response)

        items = response.get("Items", [])
        logger.info(f"Retrieved {len(items)} executions from database")
        executions = parse_obj_as(List[Execution], items)

        logger.info(f"LastEvaluationKey: {response.get(c.LAST_EVALUATED_KEY)}")
        return executions, response.get(c.LAST_EVALUATED_KEY, {})

    def get_executions_by_tenant_id_and_jit_event(self, tenant_id: str, jit_event_id: str, limit: int,
                                                  start_key: Optional[Dict]) -> Tuple[List[Execution], Dict]:
        """
        Retrieves all executions from the database by its tenant ID and JIT event ID.
        """
        logger.info(f"Retrieving executions from database by tenant ID: {tenant_id} and JIT event ID: {jit_event_id}")
        gsi7pk_tenant_jit_event_id = self.get_key(tenant=tenant_id, jit_event=jit_event_id)
        query_kwargs = {
            "KeyConditionExpression": "#gsi7pk_tenant_jit_event_id = :gsi7pk_tenant_jit_event_id",
            "ExpressionAttributeNames": {"#gsi7pk_tenant_jit_event_id": c.GSI7PK_TENANT_JIT_EVENT_ID},
            "ExpressionAttributeValues": {":gsi7pk_tenant_jit_event_id": gsi7pk_tenant_jit_event_id},
            "Limit": limit,
            "IndexName": c.GSI7,
            "ScanIndexForward": False
        }

        return self.execute_query(query_kwargs, start_key)

    def get_executions_by_tenant_id_and_jit_event_id_and_job_name(
            self, tenant_id: str, jit_event_id: str, job_name: str, limit: int, start_key: Optional[Dict]
    ) -> Tuple[List[Execution], Dict]:
        """
        Retrieves all executions from the database by its tenant ID and JIT event ID and job name.
        """
        logger.info(f"Retrieving executions {tenant_id=} and {jit_event_id=} and {job_name=}")
        gsi9pk = self.get_key(tenant=tenant_id, jit_event=jit_event_id)
        gsi9sk = self.get_key(job_name=job_name)
        query_kwargs = {
            "KeyConditionExpression": "#gsi9pk = :gsi9pk and begins_with(#gsi9sk, :gsi9sk)",
            "ExpressionAttributeNames": {
                "#gsi9pk": c.GSI9PK_TENANT_ID,
                "#gsi9sk": c.GSI9SK_JIT_EVENT_ID_JOB_NAME_CREATED_AT,
            },
            "ExpressionAttributeValues": {":gsi9pk": gsi9pk, ":gsi9sk": gsi9sk},
            "Limit": limit,
            "IndexName": c.GSI9,
        }

        return self.execute_query(query_kwargs, start_key)

    def get_executions_by_tenant_id_and_status(
            self, tenant_id: str, status: str, limit: int,
            start_key: str
    ) -> Tuple[List[Execution], Dict]:
        """
        Retrieves all executions from the database by its tenant ID and status.
        """
        logger.info(f"Retrieving executions from database by tenant ID and status: {tenant_id} and {status}")
        gsi2pk = self.get_key(tenant=tenant_id, status=status)
        query_kwargs = {
            "KeyConditionExpression": "#gsi2pk = :gsi2pk",
            "ExpressionAttributeNames": {
                "#gsi2pk": c.GSI2PK,
            },
            "ExpressionAttributeValues": {
                ":gsi2pk": gsi2pk,
            },
            "Limit": limit,
            "IndexName": c.GSI2,
            "ScanIndexForward": False
        }

        if start_key:
            query_kwargs["ExclusiveStartKey"] = start_key

        response = self.table.query(**query_kwargs)
        self._verify_response(response)

        items = response.get("Items", [])
        logger.info(
            f"Retrieved {len(items)} executions from database by tenant ID and status: {tenant_id} and {status}")
        executions = parse_obj_as(List[Execution], items)
        logger.info(f"LastEvaluationKey: {response.get(c.LAST_EVALUATED_KEY)}")
        return executions, response.get(c.LAST_EVALUATED_KEY, "")

    def get_executions_by_tenant_id_and_plan_item_slug(
            self, tenant_id: str, plan_item_slug: str, limit: int,
            start_key: str
    ) -> Tuple[List[Execution], Dict]:
        """
        Retrieves all executions from the database by its tenant ID and plan item slug.
        """
        logger.info(
            f"Retrieving executions from database by tenant ID and plan item slug: {tenant_id} and {plan_item_slug}")
        gsi3pk = self.get_key(tenant=tenant_id, plan_item=plan_item_slug)
        query_kwargs = {
            "KeyConditionExpression": "#gsi3pk = :gsi3pk",
            "ExpressionAttributeNames": {
                "#gsi3pk": c.GSI3PK,
            },
            "ExpressionAttributeValues": {
                ":gsi3pk": gsi3pk,
            },
            "Limit": limit,
            "IndexName": c.GSI3,
            "ScanIndexForward": False
        }

        if start_key:
            query_kwargs["ExclusiveStartKey"] = start_key

        logger.info(f"Query kwargs: {query_kwargs}")
        response = self.table.query(**query_kwargs)
        self._verify_response(response)

        items = response.get("Items", [])
        logger.info(
            f"Retrieved {len(items)} executions from database by tenant ID and plan item "
            f"slug: {tenant_id} and {plan_item_slug}")
        executions = parse_obj_as(List[Execution], items)

        logger.info(f"LastEvaluationKey: {response.get(c.LAST_EVALUATED_KEY)}")
        return executions, response.get(c.LAST_EVALUATED_KEY, "")

    def get_executions_by_tenant_id_and_asset_id_and_status(
            self, tenant_id: str, asset_id: str, status: str, start_key: Optional[str], limit: int
    ) -> Tuple[List[Execution], Dict]:
        """
        Retrieves all executions from the database by its tenant ID, asset ID and status.
        """
        logger.info(
            f"Retrieving executions from database by tenant ID, plan item slug and "
            f"status: {tenant_id} and {asset_id} and {status}")
        gsi8pk_tenant_id_status = self.get_key(tenant=tenant_id, status=status)
        gsi8sk_asset_id_prefix = self.get_key(asset_id=asset_id)
        query_kwargs = {
            "KeyConditionExpression": "#gsi8pk = :gsi8pk AND begins_with(#gsi8sk, :gsi8sk)",
            "ExpressionAttributeNames": {
                "#gsi8pk": c.GSI8PK_TENANT_ID_STATUS,
                "#gsi8sk": c.GSI8SK_ASSET_ID_CREATED_AT,
            },
            "ExpressionAttributeValues": {
                ":gsi8pk": gsi8pk_tenant_id_status,
                ":gsi8sk": gsi8sk_asset_id_prefix,
            },
            "Limit": limit,
            "IndexName": c.GSI8,
        }

        logger.info(f"Query kwargs: {query_kwargs}")
        if start_key:
            query_kwargs["ExclusiveStartKey"] = start_key

        response = self.table.query(**query_kwargs)
        self._verify_response(response)

        items = response.get("Items", [])
        logger.info(
            f"Retrieved {len(items)} executions from database by {tenant_id=} and {asset_id=} and {status=}")
        executions = parse_obj_as(List[Execution], items)

        logger.info(f"LastEvaluationKey: {response.get(c.LAST_EVALUATED_KEY)}")
        return executions, response.get(c.LAST_EVALUATED_KEY, "")

    def get_executions_by_tenant_id_and_plan_item_slug_and_status(
            self, tenant_id: str, plan_item_slug: str,
            status: str, limit: int,
            start_key: str
    ) -> Tuple[List[Execution], Dict]:
        """
        Retrieves all executions from the database by its tenant ID, plan item slug and status.
        """
        logger.info(
            f"Retrieving executions from database by tenant ID, plan item slug and "
            f"status: {tenant_id} and {plan_item_slug} and {status}")
        gsi4pk = self.get_key(tenant=tenant_id, plan_item=plan_item_slug, status=status)
        query_kwargs = {
            "KeyConditionExpression": "#gsi4pk = :gsi4pk",
            "ExpressionAttributeNames": {
                "#gsi4pk": c.GSI4PK,
            },
            "ExpressionAttributeValues": {
                ":gsi4pk": gsi4pk,
            },
            "Limit": limit,
            "IndexName": c.GSI4,
            "ScanIndexForward": False
        }
        if start_key:
            query_kwargs["ExclusiveStartKey"] = start_key

        logger.info(f"Query kwargs: {query_kwargs}")
        response = self.table.query(**query_kwargs)
        self._verify_response(response)

        items = response.get("Items", [])
        logger.info(
            f"Retrieved {len(items)} executions from database by tenant ID, plan item "
            f"slug and status: {tenant_id} and {plan_item_slug} and {status}")
        executions = parse_obj_as(List[Execution], items)

        logger.info(f"LastEvaluationKey: {response.get(c.LAST_EVALUATED_KEY)}")
        return executions, response.get(c.LAST_EVALUATED_KEY, "")

    def _get_next_execution_to_run(self, tenant_id: str, runner: Runner) -> Optional[Execution]:
        """
        Retrieves the oldest execution from the database by its tenant ID, runner and status.
        The execution that will be returned is the one with the highest priority and then the oldest.
        """
        logger.info(
            f"Retrieving oldest pending execution from database by tenant ID, "
            f"runner: {tenant_id} and {runner}")
        gsi5pk = self.get_key(tenant=tenant_id, runner=str(runner), status=ExecutionStatus.PENDING.value)
        query_kwargs = {
            "KeyConditionExpression": "#gsi5pk = :gsi5pk",
            "ExpressionAttributeNames": {
                "#gsi5pk": c.GSI5PK,
            },
            "ExpressionAttributeValues": {
                ":gsi5pk": gsi5pk,
            },
            "Limit": 1,
            "IndexName": c.GSI5
        }

        response = self.table.query(**query_kwargs)
        self._verify_response(response)

        items = response.get("Items", [])
        if not items:
            return None

        return Execution(**items[0])

    def get_next_execution_to_run(self,
                                  tenant_id: str,
                                  runner: Runner) -> Optional[Execution]:
        """
        Retrieves the next execution to run from the database by its tenant ID, runner and status.
        The execution that will be returned is the one with the highest priority and then the oldest.
        If the runner is CI or GitHub Actions, we will try to get the next execution to run with the matching opposite
        runner for supporting GitHub Actions and CI runners from plans.

        Args:
            tenant_id: str: The tenant ID.
            runner: Runner: The runner to filter by.

        Returns:
            Optional[Execution]: The next execution to run. If there is no execution to run, returns None.
        """
        next_execution = self._get_next_execution_to_run(tenant_id, runner)

        # In case we don't have any execution to run with the current runner,
        # We will try to get the next execution to run with the matching opposite runner for supporting
        # GitHub Actions and CI runners from plans.
        # This support is temporary until we will remove the GitHub Actions runner.
        if next_execution is None and runner in CI_RUNNERS:
            same_runner = Runner.CI if runner == Runner.GITHUB_ACTIONS else Runner.GITHUB_ACTIONS
            next_execution = self._get_next_execution_to_run(tenant_id, same_runner)

        return next_execution

    def get_executions_to_terminate(self, start_key=None, limit=None) -> Tuple[List[Execution], str]:
        """
        Retrieves all executions from the database that exceeds the execution_timeout time.
        """
        logger.info("Retrieving resources in use that exceeded the execution_timeout time")
        gsi6sk = datetime.datetime.utcnow().isoformat()
        query_kwargs = {
            "KeyConditionExpression": "#gsi6pk = :gsi6pk AND #gsi6sk < :gsi6sk",
            "ExpressionAttributeNames": {"#gsi6pk": c.GSI6PK, "#gsi6sk": c.GSI6SK},
            "ExpressionAttributeValues": {":gsi6pk": c.GSI6PK_VALUE, ":gsi6sk": gsi6sk},
            "IndexName": c.GSI6,
        }

        if start_key:
            query_kwargs["ExclusiveStartKey"] = start_key

        if limit:
            query_kwargs["Limit"] = limit

        response = self.table.query(**query_kwargs)
        self._verify_response(response)
        items = response.get("Items", [])
        logger.info(f"Retrieved {len(items)} executions that exceeded the execution_timeout time")
        logger.info(f"Execution ids retrieved from db: {', '.join([item['execution_id'] for item in items])}")
        executions = parse_obj_as(List[Execution], items)
        return executions, response.get(c.LAST_EVALUATED_KEY, "")

    #  Execution Data Management:
    def insert_execution_data(self, execution_data: ExecutionData) -> ExecutionData:
        """
        Inserts an execution data into the database.
        """
        logger.info(f"Inserting execution data into database: {execution_data}")
        pk = self.get_key(tenant=execution_data.tenant_id, jit_event=execution_data.jit_event_id)
        sk = self.get_key(execution=execution_data.execution_id, entity="execution_data")
        execution_data = ExecutionDataEntity(PK=pk, SK=sk, **execution_data.dict())
        response = self.table.put_item(Item=execution_data.dict(exclude_none=True))

        self._verify_response(response)
        logger.info(f"Inserted execution data into database: {execution_data}")

        return execution_data

    def update_execution_data_as_retrieved(
            self,
            identifiers: BaseExecutionIdentifiers,
            force: bool = False,
    ) -> ExecutionData:
        """Updates the retrieved_at field of an execution data to the current time and returns the updated data.

        If force is False, an ExecutionDataAlreadyRetrievedError will be raised if the data was already retrieved.
        """
        pk, sk = self._get_execution_data_keys(
            identifiers.tenant_id, identifiers.jit_event_id, identifiers.execution_id
        )
        params = dict(
            Key={PK: pk, SK: sk},
            UpdateExpression="SET #retrieved_at = :retrieved_at",
            ExpressionAttributeNames={"#retrieved_at": "retrieved_at"},
            ExpressionAttributeValues={":retrieved_at": int(datetime.datetime.utcnow().timestamp())},
            ReturnValues="ALL_NEW",
        )
        if not force:
            params["ConditionExpression"] = "attribute_not_exists(#retrieved_at)"

        try:
            response = self.table.update_item(**params)
        except self.client.exceptions.ConditionalCheckFailedException as e:
            logger.error(f"Failed to update execution data as retrieved, already retrieved: {identifiers}")
            raise ExecutionDataAlreadyRetrievedError from e

        self._verify_response(response)
        return ExecutionData(**response["Attributes"])

    def get_execution_data(self, tenant_id: str, jit_event_id: str, execution_id: str) -> ExecutionData:
        """
        Retrieves an execution data from the database by its tenant ID, JIT event ID and execution ID.
        """
        logger.info(
            f"Retrieving execution data from database by tenant ID, JIT event ID and execution ID: "
            f"{tenant_id} and {jit_event_id} and {execution_id}"
        )
        pk, sk = self._get_execution_data_keys(tenant_id, jit_event_id, execution_id)
        response = self.table.get_item(Key={PK: pk, SK: sk})

        self._verify_response(response)

        execution_data = response.get('Item')
        if not execution_data:
            raise ExecutionDataNotFoundException(
                tenant_id=tenant_id,
                jit_event_id=jit_event_id,
                execution_id=execution_id,
            )
        logger.info(f"Retrieved execution data from database: {execution_data}")
        return ExecutionData(**execution_data)

    def get_executions_for_multiple_identifiers(
            self,
            execution_identifiers: MultipleExecutionsIdentifiers,
    ) -> List[Execution]:
        """
        Retrieves execution details for multiple identifiers from the database instead of querying one by one.

        Args:
            execution_identifiers (MultipleExecutionsIdentifiers): Identifiers to query executions.

        Returns:
            List[Execution]: List of Execution objects.
        """
        logger.info(f"Batch getting executions from database for {execution_identifiers=}")
        executions: List[Execution] = []
        queried_execution_ids = set(execution_identifiers.execution_ids)

        keys_for_query = self._get_keys_for_multiple_executions(execution_identifiers)
        unprocessed_keys = keys_for_query[:]
        processed_keys = []

        logger.info(f"Retrieving executions for {len(unprocessed_keys)} keys...")
        while unprocessed_keys:
            for i in range(0, len(unprocessed_keys), MAX_BATCH_GET_SIZE):
                batch_keys = unprocessed_keys[i:i + MAX_BATCH_GET_SIZE]

                response = self.client.batch_get_item(
                    RequestItems={
                        self.TABLE_NAME: {
                            "Keys": batch_keys,
                        }
                    },
                    ReturnConsumedCapacity='NONE'
                )
                self._verify_response(response)
                executions_from_response = response.get('Responses', {}).get(self.TABLE_NAME, [])

                for execution in executions_from_response:
                    parsed_execution = self.parse_dynamodb_item_to_python_dict(execution)
                    executions.append(Execution(**parsed_execution))

                processed_keys.extend(batch_keys)

            unprocessed_keys = [key for key in keys_for_query if key not in processed_keys]

        # Alert about executions that were not found in the database
        found_execution_ids: set = {execution.execution_id for execution in executions}
        not_found_execution_ids: set = queried_execution_ids - found_execution_ids
        for execution_id in not_found_execution_ids:
            alert(
                f'Failed to fetch execution {execution_id} from the database as it was not found.',
                alert_type=EXECUTION_NOT_FOUND_ERROR_ALERT
            )

        logger.info(f"Retrieved {len(executions)} executions from database.")
        return executions

    def _get_keys_for_multiple_executions(self, execution_identifiers: MultipleExecutionsIdentifiers) -> List[Dict]:
        """
        Returns a list of keys for multiple executions based on the provided identifiers.
        """
        keys_for_query = []
        for execution_id in execution_identifiers.execution_ids:
            pk, sk = self._get_execution_keys(
                tenant_id=execution_identifiers.tenant_id,
                jit_event_id=execution_identifiers.jit_event_id,
                execution_id=execution_id,
            )
            keys_for_query.append({'PK': {'S': pk}, 'SK': {'S': sk}})

        return keys_for_query

    def write_multiple_execution_data(self, execution_data_list: List[ExecutionData]) -> None:
        """
        Writes multiple execution data to the database.

        This function uses a batch writer to write execution data to the database in batches.
        Batch writer handles buffering and sending items in batches, as well as retrying any unprocessed items.
        """
        logger.info(f"Writing {len(execution_data_list)} executions to the database")

        with self.table.batch_writer() as batch:
            for execution_data in execution_data_list:
                pk = self.get_key(tenant=execution_data.tenant_id, jit_event=execution_data.jit_event_id)
                sk = self.get_key(execution=execution_data.execution_id, entity="execution_data")
                item_dict = execution_data.dict(exclude_none=True)
                item_dict.update({'PK': pk, 'SK': sk})
                batch.put_item(Item=item_dict)

        logger.info("Write completed successfully")

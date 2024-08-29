import json
from datetime import datetime, timedelta
from random import randint
from typing import Dict, Optional, List

from botocore.exceptions import ClientError
from jit_utils.jit_event_names import JitEventName
from jit_utils.logger import logger, alert
from jit_utils.event_models import JitEvent
from jit_utils.models.trigger.jit_event_life_cycle import JitEventStatus
from pydantic import parse_obj_as

from src.lib.constants import (JIT_EVENT_LIFE_CYCLE_TABLE_NAME, GSI1PK_TENANT_ID, GSI1SK_CREATED_AT,
                               GSI2PK_TTL_BUCKET, GSI2SK_CREATED_AT, BUCKETS_AMOUNTS_FOR_TTL_INDEX,
                               PR_JIT_EVENTS_START_WATCHDOG_TTL_SECONDS, PR_JIT_EVENTS_END_WATCHDOG_TTL_SECONDS)
from src.lib.data.db_table import DbTable
from src.lib.exceptions import JitEventLifeCycleDBEntityNotFoundException
from src.lib.models.jit_event_life_cycle import JitEventDBEntity, JitEventAssetDBEntity


class JitEventLifeCycleManager(DbTable):
    TABLE_NAME = JIT_EVENT_LIFE_CYCLE_TABLE_NAME

    def __init__(self) -> None:
        super().__init__(self.TABLE_NAME)

    def remove_gsi2_from_record(self, jit_life_cycle_event: JitEventDBEntity) -> None:
        """
        Removes the GSI2 from the Jit event record
        """
        logger.info(f"Removing GSI2 from Jit event with ID (SK): {jit_life_cycle_event.jit_event_id}")
        pk = self.get_key(tenant=jit_life_cycle_event.tenant_id)
        sk = self.get_key(jit_event=jit_life_cycle_event.jit_event_id)

        response = self.table.update_item(
            Key={'PK': pk, 'SK': sk},
            AttributeUpdates={
                GSI2PK_TTL_BUCKET: {'Action': 'DELETE'},
                GSI2SK_CREATED_AT: {'Action': 'DELETE'},
                'modified_at': {'Value': datetime.utcnow().isoformat(), 'Action': 'PUT'}
            },
            ReturnValues='ALL_NEW'
        )
        self._verify_response(dict(response))
        logger.info("Successfully removed GSI2 from Jit event")

    def get_ttl_jit_events(self, bucket_index: int) -> List[JitEventDBEntity]:
        """
        Returns all Jit events from the given bucket index
        """
        logger.info(f"Getting TTL Jit events from bucket index: {bucket_index}")
        gsi2pk = self.get_key(ttl_bucket=bucket_index)
        now = datetime.utcnow()
        max_created_at_for_ttl = now - timedelta(seconds=PR_JIT_EVENTS_START_WATCHDOG_TTL_SECONDS)
        max_gsi2sk = self.get_key(created_at=max_created_at_for_ttl.isoformat())

        min_created_at_for_ttl = now - timedelta(seconds=PR_JIT_EVENTS_END_WATCHDOG_TTL_SECONDS)
        min_gsi2sk = self.get_key(created_at=min_created_at_for_ttl.isoformat())

        items = []
        next_page_key = None
        while True:
            query_kwargs = {
                'IndexName': 'GSI2',
                # 'created_at' should be between 15 min to 1 hour ago
                'KeyConditionExpression': f'{GSI2PK_TTL_BUCKET} = :gsi2pk'
                                          f' AND {GSI2SK_CREATED_AT} BETWEEN :min_gsi2sk AND :max_gsi2sk',
                'ExpressionAttributeValues': {
                    ':gsi2pk': gsi2pk,
                    ':max_gsi2sk': max_gsi2sk,
                    ':min_gsi2sk': min_gsi2sk,
                }
            }
            if next_page_key:
                query_kwargs['ExclusiveStartKey'] = next_page_key  # type: ignore

            response = self.table.query(**query_kwargs)  # type: ignore
            items.extend(response.get('Items', []))
            next_page_key = response.get('LastEvaluatedKey')
            if not next_page_key:
                break

        jit_events = parse_obj_as(List[JitEventDBEntity], items)
        logger.info(f"Found {len(jit_events)} TTL Jit events")
        return jit_events

    def _to_db_record(self, jit_event_db_entity: JitEventDBEntity) -> Dict:
        logger.info(f"Converting Jit event with ID (SK): {jit_event_db_entity.jit_event_id} to DynamoDB record")
        pk = gsi1pk_tenant_id = self.get_key(tenant=jit_event_db_entity.tenant_id)
        sk = self.get_key(jit_event=jit_event_db_entity.jit_event_id)
        rand_bucket = randint(0, BUCKETS_AMOUNTS_FOR_TTL_INDEX - 1)
        gsi2pk = self.get_key(ttl_bucket=rand_bucket)
        gsi1sk_created_at = gsi2sk_created_at = self.get_key(created_at=jit_event_db_entity.created_at)

        jit_event_entity: Dict = {
            'PK': pk,
            'SK': sk,
            GSI1PK_TENANT_ID: gsi1pk_tenant_id,
            GSI1SK_CREATED_AT: gsi1sk_created_at,
            # Serialize to primitive dict
            **json.loads(jit_event_db_entity.json(exclude_none=True, exclude={'status'}))
        }
        pr_related_jit_events = [JitEventName.PullRequestCreated, JitEventName.PullRequestUpdated]
        is_pr_related_jit_event = jit_event_db_entity.jit_event_name in pr_related_jit_events
        if is_pr_related_jit_event:
            jit_event_entity[GSI2PK_TTL_BUCKET] = gsi2pk
            jit_event_entity[GSI2SK_CREATED_AT] = gsi2sk_created_at

        if jit_event_db_entity.status:
            # DynamoDB does not support enums, use string value
            jit_event_entity['status'] = jit_event_db_entity.status.value

        logger.info("Converted Jit event to DynamoDB record")
        return jit_event_entity

    def put_jit_event(self, jit_event: JitEvent, status: Optional[JitEventStatus]) -> JitEventDBEntity:
        """
        Puts a new Jit event in the Jit event life cycle table.
        """
        logger.info(f"Putting a new Jit event with ID (SK): {jit_event.jit_event_id} and status: {status}")
        jit_event_db_entity = JitEventDBEntity.from_jit_event(jit_event, status)
        jit_event_entity = self._to_db_record(jit_event_db_entity)

        response = self.table.put_item(Item=jit_event_entity)
        self._verify_response(dict(response))
        logger.info("Successfully put a new Jit event")
        return jit_event_db_entity

    def get_jit_event(self, tenant_id: str, jit_event_id: str) -> JitEventDBEntity:
        """
        Retrieves a JIT event from the JIT event life cycle table.
        """
        logger.info(f"Getting a Jit event with ID (SK): {jit_event_id}")
        pk = self.get_key(tenant=tenant_id)
        sk = self.get_key(jit_event=jit_event_id)

        response = self.table.get_item(Key={'PK': pk, 'SK': sk})

        if 'Item' in response:
            logger.info("Jit event found")
            return JitEventDBEntity(**response['Item'])

        raise JitEventLifeCycleDBEntityNotFoundException(tenant_id=tenant_id, jit_event_id=jit_event_id)

    def update_jit_event_assets_count(self, tenant_id: str, jit_event_id: str, total_assets: int) -> JitEventDBEntity:
        """
        Updates the total_assets & remaining_assets attributes of an existing Jit event
        """
        logger.info(f"Updating {total_assets=} for Jit event with ID (SK): {jit_event_id}")
        pk = self.get_key(tenant=tenant_id)
        sk = self.get_key(jit_event=jit_event_id)

        response = self.table.update_item(
            Key={'PK': pk, 'SK': sk},
            AttributeUpdates={
                'total_assets': {'Value': total_assets, 'Action': 'PUT'},
                'remaining_assets': {'Value': total_assets, 'Action': 'PUT'},
                'modified_at': {'Value': datetime.utcnow().isoformat(), 'Action': 'PUT'}
            },
            ReturnValues='ALL_NEW'
        )
        self._verify_response(dict(response))
        logger.info("Successfully updated total_assets for Jit event")
        return JitEventDBEntity(**response['Attributes'])

    def create_jit_event_asset(
            self,
            tenant_id: str,
            jit_event_id: str,
            asset_id: str,
            total_jobs: int,
    ) -> JitEventAssetDBEntity:
        """
        Adds a new Jit event asset to the Jit event table if it does not exist.
        """
        logger.info(f"Adding a new Jit event asset with event ID: {jit_event_id} and asset ID: {asset_id}")
        pk = self.get_key(tenant=tenant_id)
        sk = self.get_key(jit_event=jit_event_id, asset=asset_id)

        jit_event_asset = JitEventAssetDBEntity(  # type: ignore
            tenant_id=tenant_id,
            jit_event_id=jit_event_id,
            asset_id=asset_id,
            total_jobs=total_jobs,
            remaining_jobs=total_jobs
        )

        jit_event_asset_entity: Dict = {
            'PK': pk,
            'SK': sk,
            **jit_event_asset.dict(exclude_none=True)
        }

        try:
            response = self.table.put_item(
                Item=jit_event_asset_entity,
                ConditionExpression='attribute_not_exists(PK) AND attribute_not_exists(SK)'
            )
            self._verify_response(dict(response))
            logger.info("Successfully added a new Jit event asset")
            return jit_event_asset
        except self.dynamodb.meta.client.exceptions.ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                # There is no need to raise an exception here, since lambda retry won't solve it,
                # and it's not critical for the rest of the flow, but we want to be aware of it
                alert("Jit event asset already exists with the same ID")
                return jit_event_asset
            raise

    def decrement_jit_event_asset_remaining_jobs(self, tenant_id: str, jit_event_id: str, asset_id: str) -> int:
        """
        Wrapper function to decrement remaining jobs counter for an asset in the Jit event life cycle.
        """
        logger.info(f"Decrementing remaining jobs for {tenant_id=} {jit_event_id=} {asset_id=}")
        pk = self.get_key(tenant=tenant_id)
        sk = self.get_key(jit_event=jit_event_id, asset=asset_id)

        try:
            response = self.table.update_item(
                Key={'PK': pk, 'SK': sk},
                UpdateExpression='ADD #remaining_jobs :dec',
                ConditionExpression='#remaining_jobs > :zero',
                ExpressionAttributeNames={
                    "#remaining_jobs": "remaining_jobs",
                },
                ExpressionAttributeValues={
                    ':dec': -1,
                    ':zero': 0,
                },
                ReturnValues='ALL_NEW'
            )
            self._verify_response(dict(response))
            logger.info("Successfully decremented remaining_jobs")
            updated_item = JitEventAssetDBEntity(**response['Attributes'])
            return updated_item.remaining_jobs
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                # might happen when the lambda retries due to failure like, the flow should continue
                logger.info("remaining_jobs is already 0 or less")
                return 0
            else:
                raise

    def decrement_jit_event_remaining_asset(self, tenant_id: str, jit_event_id: str) -> int:
        """
        Wrapper function to decrement remaining assets counter for an asset in the Jit event life cycle.
        """
        logger.info(f"Decrementing remaining assets for {tenant_id=} {jit_event_id=}")
        pk = self.get_key(tenant=tenant_id)
        sk = self.get_key(jit_event=jit_event_id)

        try:
            response = self.table.update_item(
                Key={'PK': pk, 'SK': sk},
                UpdateExpression='ADD #remaining_assets :dec',
                ConditionExpression='#remaining_assets > :zero',
                ExpressionAttributeNames={
                    "#remaining_assets": "remaining_assets",
                },
                ExpressionAttributeValues={
                    ':dec': -1,
                    ':zero': 0,
                },
                ReturnValues='ALL_NEW'
            )
            self._verify_response(dict(response))
            logger.info("Successfully decremented remaining_assets")
            updated_item = JitEventDBEntity(**response['Attributes'])
            return updated_item.remaining_assets  # type: ignore # will return int or exception
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                # might happen when the lambda retries due to failure like, the flow should continue
                logger.info("remaining_assets is already 0 or less")
                return 0
            else:
                raise

    def update_jit_event_life_cycle_status(
            self,
            tenant_id: str,
            jit_event_id: str,
            status: JitEventStatus,
    ) -> JitEventDBEntity:
        """
        Updates an existing Jit event with a new status
        """
        logger.info(f"Updating {tenant_id=} {jit_event_id=} with status {status=}")
        pk = self.get_key(tenant=tenant_id)
        sk = self.get_key(jit_event=jit_event_id)

        response = self.table.update_item(
            Key={'PK': pk, 'SK': sk},
            AttributeUpdates={
                'status': {'Value': status, 'Action': 'PUT'},
                'modified_at': {'Value': datetime.utcnow().isoformat(), 'Action': 'PUT'}
            },
            ReturnValues='ALL_NEW'
        )
        self._verify_response(dict(response))
        logger.info("Successfully updated Jit event status")
        return JitEventDBEntity(**response['Attributes'])

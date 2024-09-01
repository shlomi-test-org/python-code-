from jit_utils.event_models import JitEvent
from jit_utils.logger import logger
from jit_utils.models.trigger.jit_event_life_cycle import JitEventStatus, JitEventLifeCycleEntity

from src.lib.clients.event_bridge_client import send_jit_event_life_cycle_event
from src.lib.constants import (COMPLETED_JIT_EVENT_LIFE_CYCLE_EVENT_DETAIL_TYPE,
                               STARTED_JIT_EVENT_LIFE_CYCLE_EVENT_DETAIL_TYPE)
from src.lib.data.jit_event_life_cycle_table import JitEventLifeCycleManager
from src.lib.exceptions import JitEventLifeCycleNonFinalStatusCompleteAttempt


class JitEventLifeCycleHandler:
    def __init__(self) -> None:
        self._lifecycle_manager = JitEventLifeCycleManager()

    def start(self, jit_event: JitEvent) -> None:
        """
        Creates a Jit event life cycle in DB with start status, or updates an existing one.
        """
        logger.info(f"Starting Jit event with ID: {jit_event.jit_event_id}")
        jit_db_event = self._lifecycle_manager.put_jit_event(jit_event, JitEventStatus.STARTED)
        send_jit_event_life_cycle_event(STARTED_JIT_EVENT_LIFE_CYCLE_EVENT_DETAIL_TYPE, jit_db_event.json())

    def filtered_assets_to_scan(self, tenant_id: str, jit_event_id: str, total_assets: int) -> None:
        """
        Updates the total_assets to scan for an existing Jit event
        """
        if total_assets == 0:
            # nothing to run on after all filters, complete the jit event
            logger.info(f"No assets to run on {total_assets=} for Jit event with ID: {jit_event_id},"
                        " completing event")
            self.jit_event_completed(
                tenant_id=tenant_id,
                jit_event_id=jit_event_id,
                status=JitEventStatus.COMPLETED,
            )

        logger.info(f"Updating {total_assets=} for Jit event with ID: {jit_event_id}")
        self._lifecycle_manager.update_jit_event_assets_count(
            tenant_id=tenant_id,
            jit_event_id=jit_event_id,
            total_assets=total_assets,
        )

    def filtered_jobs_to_execute(self, tenant_id: str, jit_event_id: str, asset_id: str, total_jobs: int) -> None:
        """
        Creates a new asset in the Jit event life cycle table with the total_jobs to execute.
        """
        logger.info(f"Creating a new asset with {total_jobs=} for Jit event with ID: {jit_event_id}")
        self._lifecycle_manager.create_jit_event_asset(
            tenant_id=tenant_id,
            jit_event_id=jit_event_id,
            asset_id=asset_id,
            total_jobs=total_jobs,
        )
        if total_jobs == 0:
            # nothing to run on after all filters, complete the asset
            logger.info(f"No {total_jobs=} to run on for asset: {asset_id}, completing asset")
            self.asset_completed(
                tenant_id=tenant_id,
                jit_event_id=jit_event_id,
            )

    def job_completed(self, tenant_id: str, jit_event_id: str, asset_id: str) -> int:
        """
        Decrements the remaining jobs counter for an asset in the Jit event life cycle
        """
        logger.info(f"Decrementing remaining jobs for asset: {asset_id} in Jit event with ID: {jit_event_id}")
        asset_jobs_remaining = self._lifecycle_manager.decrement_jit_event_asset_remaining_jobs(
            tenant_id=tenant_id,
            jit_event_id=jit_event_id,
            asset_id=asset_id,
        )
        if asset_jobs_remaining == 0:
            logger.info(f"All jobs completed for asset: {asset_id}, completing asset")
            self.asset_completed(tenant_id=tenant_id, jit_event_id=jit_event_id)
        return asset_jobs_remaining

    def asset_completed(self, tenant_id: str, jit_event_id: str) -> int:
        """
        Decrements the remaining assets counter for a jit event in the Jit event life cycle
        """
        logger.info(f"Decrementing remaining assets for Jit event with ID: {jit_event_id}")
        jit_event_assets_remaining = self._lifecycle_manager.decrement_jit_event_remaining_asset(
            tenant_id=tenant_id,
            jit_event_id=jit_event_id,
        )
        if jit_event_assets_remaining == 0:
            logger.info(f"All assets completed for Jit event with ID: {jit_event_id}, completing event")
            self.jit_event_completed(
                tenant_id=tenant_id,
                jit_event_id=jit_event_id,
                status=JitEventStatus.COMPLETED,
            )
        return jit_event_assets_remaining

    def jit_event_completed(self,
                            tenant_id: str,
                            jit_event_id: str,
                            status: JitEventStatus = JitEventStatus.COMPLETED) -> None:
        """
        Updates the Jit event status to COMPLETED
        """
        if not status.is_final_status():
            raise JitEventLifeCycleNonFinalStatusCompleteAttempt(status=status)
        logger.info(f"Updating {jit_event_id=} to {status=}")
        jit_event_db = self._lifecycle_manager.update_jit_event_life_cycle_status(
            tenant_id=tenant_id,
            jit_event_id=jit_event_id,
            status=status,
        )
        jit_event = JitEventLifeCycleEntity(**jit_event_db.dict())
        send_jit_event_life_cycle_event(COMPLETED_JIT_EVENT_LIFE_CYCLE_EVENT_DETAIL_TYPE, jit_event.json())

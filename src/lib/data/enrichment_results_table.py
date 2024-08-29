from datetime import datetime
from typing import List, Dict

from botocore.exceptions import ClientError
from jit_utils.logger import logger
from pydantic.tools import parse_obj_as

from src.lib.constants import ENRICHMENT_RESULTS_TABLE_NAME
from src.lib.data.db_table import DbTable
from src.lib.data.enrichment_results_db_models import (
    EnrichmentResultsItem, EnrichmentResultsItemNotFoundError, LatestEnrichmentResultsItem
)
from src.lib.models.asset import Asset
from src.lib.models.enrichment_results import BaseEnrichmentResultsItem, PrEnrichmentResultsItem


class EnrichmentResultsManager(DbTable):
    TABLE_NAME = ENRICHMENT_RESULTS_TABLE_NAME

    def __init__(self) -> None:
        super().__init__(self.TABLE_NAME)

    def create_results_for_repository(self, item: BaseEnrichmentResultsItem) -> EnrichmentResultsItem:
        """
        Creates an item that represents the results (languages, frameworks)
        of the Enrichment control, for a given repository's default branch.
        We are creating 2 entities:
            1. entity with created_at in the SK - to manage history of the results
            2. entity representing the latest result (no created_at in the SK)
        """
        logger.info(f"Creating a new Enrichment result item for repository. {item=}")
        pk = self.get_key(tenant=item.tenant_id)
        current_time = datetime.utcnow().isoformat()
        latest_entity_sk = self.get_key(vendor=item.vendor, owner=item.owner, repo=item.repo)
        history_entity_sk = f"{latest_entity_sk}#CREATED_AT#{current_time}"

        history_enrichment_record = EnrichmentResultsItem(
            PK=pk,
            SK=history_entity_sk,
            created_at=current_time,
            **item.dict(exclude_none=True),
        )
        latest_enrichment_record = LatestEnrichmentResultsItem(
            PK=pk,
            SK=latest_entity_sk,
            modified_at=current_time,
            **item.dict(exclude_none=True),
        )

        try:
            self.table.put_item(Item=history_enrichment_record.dict())
            self.table.put_item(Item=latest_enrichment_record.dict())
            logger.info(f"Successfully created enrichment result for repository: {item.repo}")
        except ClientError as e:
            logger.error(f"Failed to create enrichment result: {e}")
            raise e

        return history_enrichment_record

    def get_results_for_repositories_batch(self, assets: List[Asset]) -> Dict[str, BaseEnrichmentResultsItem]:
        """
        Fetches the latest Enrichment scan results for a given list of repositories' default branches.
        Returns a list of BaseEnrichmentResultsItem if found, otherwise raises EnrichmentResultsItemNotFoundError.
        """
        logger.info(f'Fetching Enrichment results for len(assets)={len(assets)}')
        pk = self.get_key(tenant=assets[0].tenant_id)
        asset_id_to_latest_enrichment_result = {}

        try:
            for i in range(0, len(assets), 100):
                batch_assets = assets[i:i + 100]
                response = self.client.batch_get_item(
                    RequestItems={
                        self.TABLE_NAME: dict(
                            Keys=[
                                dict(
                                    PK=pk,
                                    SK=self.get_key(vendor=asset.vendor, owner=asset.owner, repo=asset.asset_name),
                                )
                                for asset in batch_assets
                            ]
                        )
                    }
                )
                items = response.get('Responses', {}).get(self.TABLE_NAME, [])
                for item in items:
                    result = BaseEnrichmentResultsItem(**item)
                    asset_id_to_latest_enrichment_result[result.repo] = result
        except ClientError as e:
            logger.error(f'Failed to fetch enrichment results: {e}')
            raise e

        return asset_id_to_latest_enrichment_result

    def get_results_for_repository(
            self,
            tenant_id: str,
            vendor: str,
            owner: str,
            repo: str,
    ) -> BaseEnrichmentResultsItem:
        """
        Fetches the latest Enrichment scan results for a given repository's default branch.
        Returns a BaseEnrichmentResultsItem if found, otherwise raises EnrichmentResultsItemNotFoundError.
        """
        logger.info(f'Fetching Enrichment results for {tenant_id=} {owner=} {vendor=} {repo=}')
        pk = self.get_key(tenant=tenant_id)
        sk = self.get_key(vendor=vendor, owner=owner, repo=repo)

        try:
            response = self.table.get_item(Key=dict(PK=pk, SK=sk))
            item = response.get('Item', None)
            if item:
                return BaseEnrichmentResultsItem(**item)
            else:
                raise EnrichmentResultsItemNotFoundError
        except ClientError as e:
            logger.error(f'Failed to fetch enrichment results: {e}')
            raise e

    def create_results_for_pr(self, item: PrEnrichmentResultsItem) -> None:
        """
        Creates an item that represents the results (languages, frameworks) of the Enrichment, for a given Pull Request.
        """
        logger.info(f"Creating a new Enrichment result item for Pull Request. {item=}")
        pk = self.get_key(tenant=item.tenant_id)
        sk = self.get_key(
            vendor=item.vendor,
            owner=item.owner,
            repo=item.repo,
            pr_number=item.pr_number,
            head_sha=item.head_sha,
        )

        self.table.put_item(Item={
            "PK": pk,
            "SK": sk,
            "created_at": datetime.utcnow().isoformat(),
            **item.dict(exclude_none=True),
        })
        logger.info(f"Successfully created enrichment result for Pull Request: {item.pr_number}")

    # This method will be in use in a future Ticket, and was commented to avoid low coverage of the tests.
    # sc-26561 + sc-26559 should uncomment this method, use it, and with component tests, add coverage to it.
    # def get_results_for_pr(
    #         self,
    #         tenant_id: str,
    #         vendor: str,
    #         owner: str,
    #         repo: str,
    #         pr_number: int,
    #         head_sha: str,
    # ) -> PrEnrichmentResultsItem:
    #     """
    #     Fetches the Enrichment scan results for a given Pull Request.
    #     Returns a PrEnrichmentResultsItem if found, otherwise raises EnrichmentResultsItemNotFoundError.
    #     """
    #     logger.info(f"Fetching Enrichment results for {tenant_id=} {owner=} {vendor=} {repo=} {pr_number=}")
    #     response = self.table.get_item(Key={
    #         "PK": self.get_key(tenant=tenant_id),
    #         "SK": self.get_key(vendor=vendor, owner=owner, repo=repo, pr_number=pr_number, head_sha=head_sha),
    #     })
    #     if not (item := response.get('Item', None)):
    #         raise EnrichmentResultsItemNotFoundError
    #
    #     return PrEnrichmentResultsItem(**item)

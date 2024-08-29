from src.lib.models.enrichment_results import BaseEnrichmentResultsItem


class EnrichmentResultsItem(BaseEnrichmentResultsItem):
    PK: str
    SK: str
    created_at: str


class LatestEnrichmentResultsItem(BaseEnrichmentResultsItem):
    PK: str
    SK: str
    modified_at: str


class EnrichmentResultsItemNotFoundError(Exception):
    pass

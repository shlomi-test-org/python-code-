from pydantic import BaseModel
from src.lib.models.trigger import EnrichedData
from jit_utils.jit_event_names import JitEventName


class BaseEnrichmentResultsItem(BaseModel):
    """
    Model representing the core attributes of an Enrichment results entity for a repository.

    :tenant_id: ID of the tenant to which the repository belongs
    :vendor: The SCM vendor of the repository ('github', 'gitlab', etc.)
    :owner: The repository's organization name (asset.owner)
    :repo: The repository name (asset.asset_name)
    :enrichment_results: Dictionary of the Enrichment control results (languages, frameworks..)
    :jit_event_id: ID of the Jit Event in which the Enrichment control performed the scan
    :jit_event_name: The name of the Jit Event the scan was performed in (e.g. 'ResourceAdded')
    """
    tenant_id: str
    vendor: str
    owner: str
    repo: str
    enrichment_results: EnrichedData
    jit_event_id: str
    jit_event_name: JitEventName


class PrEnrichmentResultsItem(BaseEnrichmentResultsItem):
    """
    Model representing the Enrichment results entity for a Pull Request.

    :pr_number: The Pull Request number
    """
    pr_number: int
    head_sha: str

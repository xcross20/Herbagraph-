"""ChEBI ontology lookup for compound normalization."""

from __future__ import annotations

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

_EBI_SEARCH = "https://www.ebi.ac.uk/webservices/chebi/rest/search"


_retry_transient = retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, max=4),
    retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
)


@_retry_transient
async def lookup_chebi_id(compound_name: str, client: httpx.AsyncClient) -> str | None:
    """Return ChEBI ID (e.g. CHEBI:12345) for a compound name, or None."""
    response = await client.get(
        _EBI_SEARCH,
        params={"search": compound_name, "searchCategory": "ALL", "maximumResults": 1},
        headers={"Accept": "application/json"},
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    payload = response.json()
    hits = payload.get("listElement") or []
    if not hits:
        return None
    chebi_accession = hits[0].get("chebiAccession")
    return str(chebi_accession) if chebi_accession else None
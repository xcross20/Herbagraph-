"""PubChem PUG-REST integration for compound identifier/property lookups."""

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

_BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

_retry_transient = retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, max=4),
    retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
)


@_retry_transient
async def get_compound_cid(compound_name: str, client: httpx.AsyncClient) -> int | None:
    """Look up a compound's PubChem CID by name. Returns None if not found."""
    response = await client.get(f"{_BASE_URL}/compound/name/{compound_name}/cids/JSON")
    if response.status_code == 404:
        return None
    response.raise_for_status()
    cids = response.json().get("IdentifierList", {}).get("CID", [])
    return cids[0] if cids else None


@_retry_transient
async def get_compound_properties(cid: int, client: httpx.AsyncClient) -> dict | None:
    """Fetch basic properties (molecular formula/weight, IUPAC name) for a PubChem CID."""
    response = await client.get(
        f"{_BASE_URL}/compound/cid/{cid}/property/MolecularFormula,MolecularWeight,IUPACName/JSON"
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    properties = response.json().get("PropertyTable", {}).get("Properties", [])
    return properties[0] if properties else None

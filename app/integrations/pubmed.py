"""NCBs Entrez PubMed integration (ESearch + ESummary)."""

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import settings
from app.integrations.quality import classify_study_type, quality_score_for
from app.models.enums import StudySource
from app.schemas.pipeline import EvidenceSnippet

_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

_retry_transient = retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, max=4),
    retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
)


def _common_params() -> dict:
    params = {"retmode": "json", "email": settings.ncbi_email}
    if settings.ncbi_api_key:
        params["api_key"] = settings.ncbi_api_key
    return params


@_retry_transient
async def _esearch(query: str, client: httpx.AsyncClient, max_results: int) -> list[str]:
    response = await client.get(
        f"{_BASE_URL}/esearch.fcgi",
        params={**_common_params(), "db": "pubmed", "term": query, "retmax": max_results},
    )
    response.raise_for_status()
    return response.json().get("esearchresult", {}).get("idlist", [])


@_retry_transient
async def _esummary(pmids: list[str], client: httpx.AsyncClient) -> dict:
    if not pmids:
        return {}
    response = await client.get(
        f"{_BASE_URL}/esummary.fcgi",
        params={**_common_params(), "db": "pubmed", "id": ",".join(pmids)},
    )
    response.raise_for_status()
    return response.json().get("result", {})


async def search_pubmed(
    query: str, client: httpx.AsyncClient, intervention_name: str, max_results: int = 5
) -> list[EvidenceSnippet]:
    """Search PubMed via ESearch, then hydrate metadata via ESummary."""
    pmids = await _esearch(query, client, max_results)
    if not pmids:
        return []

    summaries = await _esummary(pmids, client)

    snippets: list[EvidenceSnippet] = []
    for pmid in pmids:
        doc = summaries.get(pmid)
        if not doc:
            continue
        title = doc.get("title", "").strip() or "Untitled"
        pub_types = doc.get("pubtype", [])
        study_type = classify_study_type(title, pub_types)
        pub_date = doc.get("pubdate", "")
        year = None
        for token in pub_date.split():
            if token.isdigit() and len(token) == 4:
                year = int(token)
                break
        snippets.append(
            EvidenceSnippet(
                source=StudySource.PUBMED,
                external_id=f"PMID:{pmid}",
                title=title,
                year=year,
                study_type=study_type,
                quality_score=quality_score_for(study_type),
                url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                abstract_snippet=None,
                intervention_name=intervention_name,
            )
        )
    return snippets

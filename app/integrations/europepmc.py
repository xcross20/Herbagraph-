"""Europe PMC REST API integration."""

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.integrations.quality import classify_study_type, quality_score_for
from app.models.enums import StudySource
from app.schemas.pipeline import EvidenceSnippet

_BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

_retry_transient = retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, max=4),
    retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
)


@_retry_transient
async def search_europepmc(
    query: str, client: httpx.AsyncClient, intervention_name: str, max_results: int = 5
) -> list[EvidenceSnippet]:
    """Search Europe PMC for articles matching the query."""
    response = await client.get(
        _BASE_URL,
        params={"query": query, "format": "json", "pageSize": max_results},
    )
    response.raise_for_status()
    payload = response.json()

    snippets: list[EvidenceSnippet] = []
    for result in payload.get("resultList", {}).get("result", []):
        external_id = result.get("id")
        if not external_id:
            continue
        title = result.get("title", "").strip() or "Untitled"
        pub_type = result.get("pubType", "")
        study_type = classify_study_type(title, [pub_type] if pub_type else None)
        year_raw = result.get("pubYear")
        year = int(year_raw) if str(year_raw).isdigit() else None
        doi = result.get("doi")

        snippets.append(
            EvidenceSnippet(
                source=StudySource.EUROPEPMC,
                external_id=f"EPMC:{external_id}",
                title=title,
                year=year,
                study_type=study_type,
                quality_score=quality_score_for(study_type),
                url=(f"https://doi.org/{doi}" if doi else f"https://europepmc.org/article/MED/{external_id}"),
                abstract_snippet=result.get("abstractText"),
                intervention_name=intervention_name,
            )
        )
    return snippets

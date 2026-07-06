"""ClinicalTrials.gov API v2 integration."""

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.integrations.quality import quality_score_for
from app.models.enums import StudySource, StudyType
from app.schemas.pipeline import EvidenceSnippet

_BASE_URL = "https://clinicaltrials.gov/api/v2/studies"

_retry_transient = retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, max=4),
    retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
)


def _classify(study_type_raw: str | None) -> StudyType:
    if (study_type_raw or "").upper() == "OBSERVATIONAL":
        return StudyType.COHORT
    return StudyType.RCT


@_retry_transient
async def search_clinicaltrials(
    query: str, client: httpx.AsyncClient, intervention_name: str, max_results: int = 5
) -> list[EvidenceSnippet]:
    """Search ClinicalTrials.gov for interventional/observational studies matching the query."""
    response = await client.get(
        _BASE_URL,
        params={"query.term": query, "pageSize": max_results, "format": "json"},
    )
    response.raise_for_status()
    payload = response.json()

    snippets: list[EvidenceSnippet] = []
    for study in payload.get("studies", []):
        protocol = study.get("protocolSection", {})
        identification = protocol.get("identificationModule", {})
        design = protocol.get("designModule", {})
        status = protocol.get("statusModule", {})

        nct_id = identification.get("nctId")
        title = identification.get("briefTitle", "").strip() or "Untitled"
        if not nct_id:
            continue

        study_type = _classify(design.get("studyType"))
        year = None
        start_date = status.get("startDateStruct", {}).get("date", "")
        if start_date[:4].isdigit():
            year = int(start_date[:4])

        snippets.append(
            EvidenceSnippet(
                source=StudySource.CLINICALTRIALS,
                external_id=nct_id,
                title=title,
                year=year,
                study_type=study_type,
                quality_score=quality_score_for(study_type),
                url=f"https://clinicaltrials.gov/study/{nct_id}",
                abstract_snippet=None,
                intervention_name=intervention_name,
            )
        )
    return snippets

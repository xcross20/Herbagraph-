"""Discovery literature. PMIDs come only from NCBI via the existing PubMed client."""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


def wants_evidence(text: str) -> bool:
    blob = (text or "").lower()
    return any(token in blob for token in ("why", "evidence", "pubmed", "paper", "citation", "show me the research"))


async def retrieve_citations(query: str, *, limit: int = 3) -> list[dict]:
    from app.integrations.pubmed import search_pubmed

    q = (query or "").strip()
    if len(q) < 4:
        return []
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            snippets = await search_pubmed(q, client, intervention_name="Discovery", max_results=limit)
    except Exception:
        logger.info("PubMed retrieval skipped")
        return []
    rows: list[dict] = []
    for snippet in snippets:
        pmid = (snippet.external_id or "").replace("PMID:", "").strip()
        if not pmid.isdigit():
            continue
        rows.append(
            {
                "pmid": pmid,
                "title": snippet.title,
                "year": snippet.year,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            }
        )
    return rows

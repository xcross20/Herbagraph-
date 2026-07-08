"""Single source of truth for which studies support a recommendation."""

from __future__ import annotations

from app.schemas.explainability import SupportingLiteratureEntry
from app.schemas.pipeline import EvidenceSnippet, LLMRecommendation

_STUDY_TYPE_LABELS: dict[str, str] = {
    "meta_analysis": "Meta-analysis",
    "systematic_review": "Systematic review",
    "rct": "RCT",
    "cohort": "Cohort study",
    "case_control": "Case-control study",
    "mechanistic": "Mechanistic study",
    "preclinical": "Preclinical study",
    "animal": "Animal study",
    "in_vitro": "In vitro study",
    "traditional_use": "Traditional use",
}


def literature_label(study_type: str | None, year: int | None) -> str:
    label = _STUDY_TYPE_LABELS.get(study_type or "", "Study")
    return f"{label} ({year})" if year else label


def resolve_study_url(
    external_id: str,
    *,
    source: str | None = None,
    url: str | None = None,
) -> str | None:
    """Return a clickable URL for a study — never fabricate, but resolve known ID patterns."""
    if url:
        return url
    study_id = external_id.strip()
    if study_id.startswith("PMID:"):
        pmid = study_id.removeprefix("PMID:")
        if pmid.isdigit():
            return f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
    if study_id.isdigit():
        return f"https://pubmed.ncbi.nlm.nih.gov/{study_id}/"
    upper = study_id.upper()
    if upper.startswith("NCT"):
        return f"https://clinicaltrials.gov/study/{upper}"
    if study_id.startswith("EPMC:"):
        return f"https://europepmc.org/article/MED/{study_id.removeprefix('EPMC:')}"
    if source == "pubmed" and study_id.isdigit():
        return f"https://pubmed.ncbi.nlm.nih.gov/{study_id}/"
    return None


def _id_aliases(external_id: str) -> set[str]:
    """Allow citation index lookup across PMID / NCT formatting variants."""
    aliases = {external_id}
    if external_id.startswith("PMID:"):
        aliases.add(external_id.removeprefix("PMID:"))
    elif external_id.isdigit():
        aliases.add(f"PMID:{external_id}")
    if external_id.startswith("NCT"):
        aliases.add(external_id.upper())
    return aliases


def resolve_cited_studies(
    recommendation: LLMRecommendation,
    evidence_snippets: list[EvidenceSnippet],
    *,
    max_studies: int = 8,
) -> list[EvidenceSnippet]:
    """Merge LLM-cited IDs with intervention-matched retrieved evidence (deterministic)."""
    by_id: dict[str, EvidenceSnippet] = {}
    for snippet in evidence_snippets:
        for alias in _id_aliases(snippet.external_id):
            by_id[alias] = snippet

    cited: list[EvidenceSnippet] = []
    seen_ids: set[str] = set()

    for raw_id in recommendation.cited_study_ids:
        snippet = by_id.get(raw_id)
        if snippet is None:
            for alias in _id_aliases(raw_id):
                snippet = by_id.get(alias)
                if snippet:
                    break
        if snippet and snippet.external_id not in seen_ids:
            cited.append(snippet)
            seen_ids.add(snippet.external_id)

    if len(cited) < max_studies:
        intervention_matches = sorted(
            [e for e in evidence_snippets if e.intervention_name == recommendation.intervention_name],
            key=lambda s: s.quality_score,
            reverse=True,
        )
        for snippet in intervention_matches:
            if snippet.external_id in seen_ids:
                continue
            cited.append(snippet)
            seen_ids.add(snippet.external_id)
            if len(cited) >= max_studies:
                break

    return cited


def build_citations_index(citations: list[dict]) -> dict[str, dict]:
    """Map citation rows by external_id and common alias variants."""
    index: dict[str, dict] = {}
    for citation in citations:
        external_id = citation["id"]
        for alias in _id_aliases(external_id):
            index.setdefault(alias, citation)
    return index


def lookup_citation(citations_by_id: dict[str, dict], study_id: str) -> dict | None:
    for alias in _id_aliases(study_id):
        citation = citations_by_id.get(alias)
        if citation:
            return citation
    return None


def hydrate_citation_url(citation: dict) -> str | None:
    """Resolve a clickable URL for a stored citation row (backfills legacy null urls)."""
    return resolve_study_url(
        citation["id"],
        source=citation.get("source"),
        url=citation.get("url"),
    )


def hydrate_supporting_literature(
    cited_study_ids: list[str],
    citations_by_id: dict[str, dict],
    *,
    cited_urls: list[str] | None = None,
) -> list[SupportingLiteratureEntry]:
    """Build supporting_literature for legacy reports missing explainability payloads."""
    entries: list[SupportingLiteratureEntry] = []
    for index, study_id in enumerate(cited_study_ids):
        citation = lookup_citation(citations_by_id, study_id)
        paired_url = cited_urls[index] if cited_urls and index < len(cited_urls) else None
        url = paired_url or (hydrate_citation_url(citation) if citation else resolve_study_url(study_id))
        study_type = citation.get("study_type") if citation else None
        year = citation.get("year") if citation else None
        title = (citation or {}).get("title") or study_id
        entries.append(
            SupportingLiteratureEntry(
                study_id=study_id,
                label=literature_label(study_type, year),
                title=title,
                year=year,
                study_type=study_type,
                url=url,
            )
        )
    return entries


def build_supporting_literature(cited: list[EvidenceSnippet]) -> list[SupportingLiteratureEntry]:
    entries: list[SupportingLiteratureEntry] = []
    for snippet in cited:
        study_type = snippet.study_type.value if snippet.study_type else None
        source_val = snippet.source.value if hasattr(snippet.source, "value") else str(snippet.source)
        entries.append(
            SupportingLiteratureEntry(
                study_id=snippet.external_id,
                label=literature_label(study_type, snippet.year),
                title=snippet.title,
                year=snippet.year,
                study_type=study_type,
                url=resolve_study_url(
                    snippet.external_id,
                    source=source_val,
                    url=snippet.url,
                ),
            )
        )
    return entries
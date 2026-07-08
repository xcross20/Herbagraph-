"""Citation resolution — passport, literature links, and report table must agree."""

import pytest

from app.evidence_confidence.citations import (
    build_supporting_literature,
    hydrate_citation_url,
    hydrate_supporting_literature,
    resolve_cited_studies,
    resolve_study_url,
)
from app.models.enums import EvidenceLevel, InterventionCategory, StudySource, StudyType
from app.schemas.pipeline import EvidenceSnippet, LLMRecommendation

pytestmark = pytest.mark.unit


def _snippet(eid, intervention, study_type=StudyType.RCT, year=2024):
    return EvidenceSnippet(
        source=StudySource.PUBMED,
        external_id=eid,
        title=f"Study {eid}",
        year=year,
        study_type=study_type,
        quality_score=0.7,
        intervention_name=intervention,
        url=f"https://pubmed.ncbi.nlm.nih.gov/{eid.removeprefix('PMID:')}/",
    )


def test_resolve_merges_llm_cites_and_intervention_fallback():
    rec = LLMRecommendation(
        intervention_name="Iron",
        category=InterventionCategory.SUPPLEMENT,
        mechanism="Repletion",
        evidence_level=EvidenceLevel.MODERATE,
        cited_study_ids=["PMID:111"],
    )
    snippets = [
        _snippet("PMID:111", "Iron"),
        _snippet("PMID:222", "Iron", study_type=StudyType.META_ANALYSIS, year=2025),
    ]
    cited = resolve_cited_studies(rec, snippets)
    ids = [s.external_id for s in cited]
    assert "PMID:111" in ids
    assert "PMID:222" in ids


def test_resolve_study_url_from_pmid_and_nct():
    assert resolve_study_url("PMID:41601662") == "https://pubmed.ncbi.nlm.nih.gov/41601662/"
    assert resolve_study_url("NCT01234567") == "https://clinicaltrials.gov/study/NCT01234567"


def test_supporting_literature_labels_match_study_type():
    cited = [_snippet("PMID:222", "Iron", study_type=StudyType.META_ANALYSIS, year=2025)]
    lit = build_supporting_literature(cited)
    assert lit[0].label == "Meta-analysis (2025)"
    assert lit[0].study_id == "PMID:222"
    assert lit[0].url == "https://pubmed.ncbi.nlm.nih.gov/222/"


def test_hydrate_citation_url_backfills_epmc_and_pmid():
    assert hydrate_citation_url({"id": "EPMC:39343737", "source": "europepmc", "url": None}) == (
        "https://europepmc.org/article/MED/39343737"
    )
    assert hydrate_citation_url({"id": "PMID:40770379", "source": "pubmed", "url": None}) == (
        "https://pubmed.ncbi.nlm.nih.gov/40770379/"
    )


def test_hydrate_supporting_literature_uses_cited_urls_for_legacy_reports():
    citations = {
        "EPMC:39343737": {
            "id": "EPMC:39343737",
            "source": "europepmc",
            "title": "Garlic for dyslipidemia",
            "year": 2024,
            "study_type": "meta_analysis",
            "url": None,
        }
    }
    lit = hydrate_supporting_literature(
        ["EPMC:39343737", "PMID:40770379"],
        citations,
        cited_urls=["https://doi.org/10.1002/ptr.8350", "https://pubmed.ncbi.nlm.nih.gov/40770379/"],
    )
    assert lit[0].url == "https://doi.org/10.1002/ptr.8350"
    assert lit[1].url == "https://pubmed.ncbi.nlm.nih.gov/40770379/"
    assert lit[0].label == "Meta-analysis (2024)"
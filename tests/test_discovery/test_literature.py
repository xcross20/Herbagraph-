"""PubMed citations are retrieved, never invented. Non-digit PMIDs are dropped."""

from types import SimpleNamespace

import pytest

from app.discovery.literature import retrieve_citations, wants_evidence
from app.discovery.orchestrator import orchestrate


def test_wants_evidence_from_why_language():
    assert wants_evidence("Why is this the next question?")
    assert wants_evidence("Show me the research")
    assert wants_evidence("Any PubMed papers?")
    assert not wants_evidence("Both feet, mostly at night.")


def test_why_selects_retrieve_evidence_when_not_urgent():
    result = orchestrate(
        "Why? Show me the evidence.",
        prior_facts={
            "burning sensation": "reported",
            "location": "feet",
            "laterality": "bilateral",
        },
        asked=["q_laterality"],
        answered={"laterality"},
    )
    assert result.action.type == "retrieve_evidence"
    assert result.stage == "evidence_collection"


def test_urgent_safety_overrides_evidence_request():
    result = orchestrate(
        "Why? It started this morning and now I can't lift my right foot.",
        prior_facts={},
        asked=[],
        answered=set(),
    )
    assert result.action.type == "show_safety_message"
    assert result.stage == "safety_triage"


@pytest.mark.asyncio
async def test_retrieve_citations_keeps_digit_pmids_only(monkeypatch):
    async def fake_search(query, client, intervention_name, max_results=5):
        assert "burn" in query.lower() or query
        return [
            SimpleNamespace(external_id="PMID:12345678", title="A real paper", year=2020),
            SimpleNamespace(external_id="PMID:invented-id", title="Not a PMID", year=2021),
            SimpleNamespace(external_id="PMID:999", title="Also real", year=2019),
        ]

    monkeypatch.setattr("app.integrations.pubmed.search_pubmed", fake_search)
    rows = await retrieve_citations("burning feet small fiber")
    pmids = [row["pmid"] for row in rows]
    assert pmids == ["12345678", "999"]
    assert all(row["pmid"].isdigit() for row in rows)
    assert rows[0]["url"] == "https://pubmed.ncbi.nlm.nih.gov/12345678/"


@pytest.mark.asyncio
async def test_retrieve_citations_empty_on_short_query():
    assert await retrieve_citations("why") == []

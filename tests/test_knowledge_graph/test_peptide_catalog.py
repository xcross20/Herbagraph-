"""Validation for clinically evidenced peptide catalog."""

import pytest

from app.knowledge_graph.peptide_catalog import PEPTIDE_EVIDENCE_CLAIMS, PEPTIDE_INTERVENTIONS
from app.knowledge_graph.seed_data import BIOMARKERS, PATHWAYS

pytestmark = pytest.mark.unit

REGULATED_INVESTIGATIONAL = {"BPC-157", "TB-500"}


def test_peptide_interventions_all_have_clinical_evidence_claims():
    claim_names = {c["intervention_name"] for c in PEPTIDE_EVIDENCE_CLAIMS}
    for peptide in PEPTIDE_INTERVENTIONS:
        assert peptide["name"] in claim_names, f"{peptide['name']} missing evidence claim"
        assert peptide["category"] == "peptide"


def test_peptide_evidence_claims_have_pmids_and_summaries():
    for claim in PEPTIDE_EVIDENCE_CLAIMS:
        assert claim["pmid"], f"missing pmid for {claim['intervention_name']}"
        assert claim["summary"], f"missing summary for {claim['intervention_name']}"
        assert claim["evidence_level"] in {"high", "moderate", "low", "preclinical"}


def test_investigational_peptides_surfaced_as_regulated_context_only():
    by_name = {p["name"]: p for p in PEPTIDE_INTERVENTIONS}
    for name in REGULATED_INVESTIGATIONAL:
        assert name in by_name
        assert by_name[name]["is_regulated"] is True
        assert by_name[name].get("regulation_note")


def test_peptide_evidence_claims_referential_integrity():
    peptide_names = {p["name"] for p in PEPTIDE_INTERVENTIONS}
    pathway_codes = {p["code"] for p in PATHWAYS}
    biomarker_names = {b["canonical_name"] for b in BIOMARKERS}
    for claim in PEPTIDE_EVIDENCE_CLAIMS:
        assert claim["intervention_name"] in peptide_names
        if claim["pathway_code"]:
            assert claim["pathway_code"] in pathway_codes
        if claim["biomarker_name"]:
            assert claim["biomarker_name"] in biomarker_names


def test_regulated_glp1_peptides_flagged():
    regulated = {p["name"] for p in PEPTIDE_INTERVENTIONS if p.get("is_regulated")}
    assert {"Semaglutide", "Tirzepatide", "Liraglutide"}.issubset(regulated)
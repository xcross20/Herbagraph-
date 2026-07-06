"""Pure-data validation tests for app.knowledge_graph.seed_data.

No database or async fixtures needed -- these just assert on the literal
BIOMARKERS / PATHWAYS / INTERVENTIONS / EVIDENCE_CLAIMS lists.
"""

import pytest

from app.knowledge_graph.seed_data import BIOMARKERS, EVIDENCE_CLAIMS, INTERVENTIONS, PATHWAYS

pytestmark = pytest.mark.unit

VALID_INTERVENTION_CATEGORIES = {"herb", "supplement", "exercise", "behavior", "stress_reduction", "sleep"}

DOCUMENTED_PATHWAY_CODES = {
    "NF_KB",
    "IL6_JAK_STAT3",
    "AMPK",
    "INSULIN_PI3K_AKT",
    "NRF2",
    "MTOR_AUTOPHAGY",
    "HPA_AXIS",
    "THYROID_HPT",
    "HEPATIC_LIPID",
    "ONE_CARBON_METHYLATION",
    "GLP1_INCRETINS",
    "MITOCHONDRIAL_NAD",
    "IRON_HEPCIDIN",
    "PURINE_URIC_ACID",
    "VITAMIN_D_RECEPTOR",
    "RENAL_FILTRATION",
}

REQUIRED_BIOMARKER_KEYS = {
    "canonical_name",
    "category",
    "description",
    "default_unit",
    "reference_low",
    "reference_high",
    "optimal_low",
    "optimal_high",
}

REQUIRED_INTERVENTION_KEYS = {
    "name",
    "category",
    "description",
    "mechanism",
    "is_regulated",
    "compounds",
    "safety_flags",
    "drug_interactions",
}

REQUIRED_EVIDENCE_CLAIM_KEYS = {
    "intervention_name",
    "biomarker_name",
    "pathway_code",
    "effect",
    "evidence_level",
    "pmid",
    "summary",
}


# ---------------------------------------------------------------------------
# BIOMARKERS
# ---------------------------------------------------------------------------


def test_biomarkers_count():
    assert len(BIOMARKERS) == 17


def test_biomarkers_unique_canonical_names():
    names = [b["canonical_name"] for b in BIOMARKERS]
    assert len(names) == len(set(names))


def test_biomarkers_required_keys_present():
    for biomarker in BIOMARKERS:
        missing = REQUIRED_BIOMARKER_KEYS - biomarker.keys()
        assert not missing, f"{biomarker.get('canonical_name')} missing keys: {missing}"


def test_biomarkers_field_types():
    for biomarker in BIOMARKERS:
        assert isinstance(biomarker["canonical_name"], str) and biomarker["canonical_name"]
        assert isinstance(biomarker["category"], str) and biomarker["category"]
        assert biomarker["description"] is None or isinstance(biomarker["description"], str)
        assert biomarker["default_unit"] is None or isinstance(biomarker["default_unit"], str)
        for key in ("reference_low", "reference_high", "optimal_low", "optimal_high"):
            value = biomarker[key]
            assert value is None or isinstance(value, (int, float))


def test_biomarkers_reference_range_ordering():
    for biomarker in BIOMARKERS:
        low, high = biomarker["reference_low"], biomarker["reference_high"]
        if low is not None and high is not None:
            assert low < high, f"{biomarker['canonical_name']}: reference_low >= reference_high"


def test_biomarkers_optimal_range_ordering():
    for biomarker in BIOMARKERS:
        low, high = biomarker["optimal_low"], biomarker["optimal_high"]
        if low is not None and high is not None:
            assert low <= high, f"{biomarker['canonical_name']}: optimal_low > optimal_high"


# ---------------------------------------------------------------------------
# PATHWAYS
# ---------------------------------------------------------------------------


def test_pathways_count():
    assert len(PATHWAYS) == 16


def test_pathways_unique_codes():
    codes = [p["code"] for p in PATHWAYS]
    assert len(codes) == len(set(codes))


def test_pathways_codes_match_documented_set():
    codes = {p["code"] for p in PATHWAYS}
    assert codes == DOCUMENTED_PATHWAY_CODES


def test_pathways_required_keys_present():
    for pathway in PATHWAYS:
        assert {"code", "name", "description"} <= pathway.keys()
        assert isinstance(pathway["code"], str) and pathway["code"]
        assert isinstance(pathway["name"], str) and pathway["name"]


# ---------------------------------------------------------------------------
# INTERVENTIONS
# ---------------------------------------------------------------------------


def test_interventions_count():
    assert len(INTERVENTIONS) == 15


def test_interventions_unique_names():
    names = [i["name"] for i in INTERVENTIONS]
    assert len(names) == len(set(names))


def test_interventions_required_keys_present():
    for intervention in INTERVENTIONS:
        missing = REQUIRED_INTERVENTION_KEYS - intervention.keys()
        assert not missing, f"{intervention.get('name')} missing keys: {missing}"


def test_interventions_valid_categories():
    for intervention in INTERVENTIONS:
        assert intervention["category"] in VALID_INTERVENTION_CATEGORIES, (
            f"{intervention['name']} has invalid category {intervention['category']!r}"
        )


def test_interventions_safety_flags_and_drug_interactions_shape():
    for intervention in INTERVENTIONS:
        for flag in intervention["safety_flags"]:
            assert {"condition", "severity"} <= flag.keys()
        for interaction in intervention["drug_interactions"]:
            assert {"drug_name", "severity"} <= interaction.keys()


# ---------------------------------------------------------------------------
# EVIDENCE_CLAIMS
# ---------------------------------------------------------------------------


def test_evidence_claims_required_keys_present():
    for claim in EVIDENCE_CLAIMS:
        missing = REQUIRED_EVIDENCE_CLAIM_KEYS - claim.keys()
        assert not missing, f"{claim} missing keys: {missing}"


def test_evidence_claims_intervention_names_exist():
    intervention_names = {i["name"] for i in INTERVENTIONS}
    for claim in EVIDENCE_CLAIMS:
        assert claim["intervention_name"] in intervention_names, (
            f"unknown intervention_name {claim['intervention_name']!r} in evidence claim"
        )


def test_evidence_claims_pathway_codes_exist():
    pathway_codes = {p["code"] for p in PATHWAYS}
    for claim in EVIDENCE_CLAIMS:
        if claim["pathway_code"] is not None:
            assert claim["pathway_code"] in pathway_codes, (
                f"unknown pathway_code {claim['pathway_code']!r} in evidence claim"
            )


def test_evidence_claims_biomarker_names_exist_when_set():
    biomarker_names = {b["canonical_name"] for b in BIOMARKERS}
    for claim in EVIDENCE_CLAIMS:
        if claim["biomarker_name"] is not None:
            assert claim["biomarker_name"] in biomarker_names, (
                f"unknown biomarker_name {claim['biomarker_name']!r} in evidence claim"
            )


def test_evidence_claims_have_pmid_and_summary():
    for claim in EVIDENCE_CLAIMS:
        assert claim["pmid"], f"evidence claim missing pmid: {claim}"
        assert claim["summary"], f"evidence claim missing summary: {claim}"


def test_evidence_claims_valid_evidence_levels():
    valid_levels = {"high", "moderate", "low", "preclinical"}
    for claim in EVIDENCE_CLAIMS:
        assert claim["evidence_level"] in valid_levels

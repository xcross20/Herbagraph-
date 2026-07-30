"""Evidence expansion sprint claims are well-formed."""

from app.knowledge_graph.tier_a_evidence import TIER_A_EVIDENCE_CLAIMS

REQUIRED = {"intervention_name", "effect", "evidence_level", "pmid", "recommendation_intent", "summary"}


def test_all_claims_have_required_fields():
    for claim in TIER_A_EVIDENCE_CLAIMS:
        missing = REQUIRED - set(claim.keys())
        assert not missing, f"{claim.get('intervention_name')}: missing {missing}"
        assert claim["pmid"]
        assert claim["recommendation_intent"] in {
            "primary",
            "collateral",
            "context_only",
            "nutritional_repletion",
        }


def test_imp_054_serum_iron_claim_exists():
    hits = [
        c
        for c in TIER_A_EVIDENCE_CLAIMS
        if c["intervention_name"] == "Iron" and c.get("biomarker_name") == "Iron"
    ]
    assert hits, "Expected biomarker-direct Iron claim for serum Iron"
    assert any(c["pathway_code"] == "IRON_HEPCIDIN" for c in hits)


def test_missing_tier_a_herbs_now_have_claims():
    claimed = {c["intervention_name"] for c in TIER_A_EVIDENCE_CLAIMS}
    for name in (
        "Andrographis",
        "Rhodiola rosea",
        "Olive Leaf",
        "Chamomile",
        "Peppermint",
        "Holy Basil",
        "Slippery Elm",
        "Goldenseal",
        "Licorice Root",
    ):
        assert name in claimed, f"{name} still lacks evidence claims"

"""Conversational biomarker→pathway→intervention narratives with per-tree templates."""

from __future__ import annotations

from app.knowledge_graph.lifestyle_methods_catalog import LIFESTYLE_CATEGORIES, METHODOLOGY_BY_NAME
from app.models.enums import RecommendationIntent, RecommendationTree
from app.pipeline.test_type_router import RecommendationRoutingContext
from app.schemas.evidence import FoodSourceRead
from app.schemas.pipeline import NormalizedLabResult, PathwayActivation

_PATHWAY_NAMES = {
    "NF_KB": "NF-κB inflammatory signaling",
    "IL6_JAK_STAT3": "IL-6/JAK-STAT3 signaling",
    "AMPK": "AMPK energy sensing",
    "INSULIN_PI3K_AKT": "insulin/PI3K-Akt signaling",
    "NRF2": "Nrf2 antioxidant response",
    "MTOR_AUTOPHAGY": "mTOR/autophagy balance",
    "HPA_AXIS": "HPA stress-response axis",
    "THYROID_HPT": "thyroid/HPT axis",
    "HEPATIC_LIPID": "hepatic lipid metabolism",
    "ONE_CARBON_METHYLATION": "one-carbon/methylation cycle",
    "GLP1_INCRETINS": "GLP-1/incretin signaling",
    "MITOCHONDRIAL_NAD": "mitochondrial NAD+ metabolism",
    "IRON_HEPCIDIN": "iron/hepcidin regulation",
    "PURINE_URIC_ACID": "purine/uric acid metabolism",
    "VITAMIN_D_RECEPTOR": "vitamin D receptor signaling",
    "RENAL_FILTRATION": "renal filtration function",
    "GASTRIC_COLONIZATION": "gastric pathogen colonization",
    "GI_MUCOSAL_BARRIER": "GI mucosal barrier integrity",
    "PATHOGEN_BURDEN": "active pathogen burden",
    "BIOFILM_ADHESION": "biofilm and microbial adhesion",
    "FOOD_ANTIGEN_EXPOSURE": "food antigen exposure",
    "IGE_SENSITIZATION": "IgE-mediated sensitization",
    "AUTOIMMUNE_TARGETING": "autoimmune targeting",
    "HEPATOTROPIC_VIRAL": "hepatotropic viral infection",
    "DRUG_METABOLISM_VARIANT": "drug metabolism variant",
    "NUTRIENT_DEFICIENCY": "nutrient deficiency",
    "URINARY_PATHOGEN": "urinary tract pathogen colonization",
    "RESPIRATORY_PATHOGEN": "respiratory pathogen burden",
}

_INTENT_FRAMING = {
    RecommendationIntent.PRIMARY.value: "has been studied as a primary intervention for",
    RecommendationIntent.COLLATERAL.value: "has been studied as supportive context for",
    RecommendationIntent.CONTEXT_ONLY.value: "is surfaced only as interaction or exposure context for",
    RecommendationIntent.NUTRITIONAL_REPLETION.value: "is studied for repleting measured deficiency in",
}

_TREE_FRAMING = {
    RecommendationTree.ETIOLOGICAL: "At the root-cause layer (what your test detects, not just downstream inflammation), ",
    RecommendationTree.CELIAC: "For celiac-related serology, ",
    RecommendationTree.ALLERGY: "For allergen sensitization, ",
    RecommendationTree.CULTURE: "For culture-positive infection markers, ",
    RecommendationTree.EXPOSURE: "This serology suggests prior exposure rather than confirmed active infection — ",
    RecommendationTree.PGX_CONTEXT: "For pharmacogenomic context (not a treatment recommendation), ",
    RecommendationTree.NUTRITIONAL_REPLETION: "For measured nutrient deficiency, ",
    RecommendationTree.SIGNALING: "",
}

_RICHNESS_WORDS = {"high": "rich", "moderate": "moderate", "low": "modest"}


def _abnormal_biomarker_phrase(normalized_labs: list[NormalizedLabResult]) -> str:
    abnormal = [lab for lab in normalized_labs if lab.status.value not in ("normal", "optimal")]
    if not abnormal:
        return "your abnormal biomarker pattern"
    if len(abnormal) == 1:
        lab = abnormal[0]
        if lab.qualitative_label:
            return f"your {lab.biomarker_name} result ({lab.qualitative_label})"
        return f"your {lab.biomarker_name} ({lab.status.value})"
    names = [lab.biomarker_name for lab in abnormal[:3]]
    return "your " + ", ".join(names)


def _pathway_phrase(
    intervention_name: str,
    pathway_activations: list[PathwayActivation],
    intervention_pathways: dict[str, list[str]],
) -> str:
    codes = set(intervention_pathways.get(intervention_name, []))
    relevant = [a for a in pathway_activations if a.pathway_code in codes]
    if not relevant:
        codes_list = list(codes)[:2]
        if not codes_list:
            return "relevant biological pathways"
        labels = [_PATHWAY_NAMES.get(c, c.replace("_", " ").lower()) for c in codes_list]
        return " and ".join(labels)

    top = sorted(relevant, key=lambda a: a.activation_score, reverse=True)[0]
    label = _PATHWAY_NAMES.get(top.pathway_code, top.pathway_name.lower())
    drivers = ", ".join(top.contributing_biomarkers[:2])
    if drivers:
        return f"{label} (driven in part by {drivers})"
    return label


def _food_sources_sentence(food_sources: list[FoodSourceRead]) -> str:
    if not food_sources:
        return ""

    parts: list[str] = []
    for src in food_sources[:4]:
        richness = _RICHNESS_WORDS.get(
            src.richness.value if hasattr(src.richness, "value") else str(src.richness),
            "dietary",
        )
        serving = f", typical serving: {src.typical_serving}" if src.typical_serving else ""
        note = f" ({src.note})" if src.note else ""
        parts.append(f"{src.food} — a {richness} source{serving}{note}")

    if len(parts) == 1:
        return f"In whole foods, the literature most often discusses {parts[0]}."
    joined = "; ".join(parts[:-1]) + f"; and {parts[-1]}"
    return (
        "In whole foods, the literature discusses dietary sources such as "
        f"{joined}. HerbaGraph names the compound because that is what trials measure — not a specific product or protocol."
    )


def build_intervention_narrative(
    intervention_name: str,
    category: str,
    mechanism: str | None,
    pathway_activations: list[PathwayActivation],
    intervention_pathways: dict[str, list[str]],
    normalized_labs: list[NormalizedLabResult],
    food_sources: list[FoodSourceRead] | None,
    *,
    linked_compound: str | None = None,
    recommendation_intent: str = RecommendationIntent.COLLATERAL.value,
    routing: RecommendationRoutingContext | None = None,
) -> str:
    """Plain-language chain: biomarker → pathway/etiology → intervention → foods."""
    biomarker_phrase = _abnormal_biomarker_phrase(normalized_labs)
    pathway_phrase = _pathway_phrase(intervention_name, pathway_activations, intervention_pathways)

    tree_prefix = ""
    if routing and routing.primary_tree:
        tree_prefix = _TREE_FRAMING.get(routing.primary_tree, "")

    intent_phrase = _INTENT_FRAMING.get(recommendation_intent, "has been studied in connection with")

    intro = (
        f"{tree_prefix}Based on {biomarker_phrase}, {pathway_phrase} showed a signal in your panel. "
        f"{intervention_name} {intent_phrase} this context. "
    )

    if category == "phytochemical":
        intro += "It is a phytochemical — an active compound found in whole foods. "
    elif category == "food":
        if linked_compound and linked_compound != intervention_name:
            intro += f"It is a whole food rich in {linked_compound}. "
        else:
            intro += "It is a whole food providing bioactive compounds from the literature. "
    elif category == "herb":
        if linked_compound and food_sources:
            intro += (
                f"As a botanical, much of the literature measures {linked_compound} rather than culinary amounts. "
            )
        else:
            intro += "As a botanical, trials typically use standardized extracts rather than culinary amounts. "
    elif category == "behavior":
        intro += "This is a behavioral dietary intervention rather than a supplement. "
    elif category == "exercise":
        intro += "This is a structured exercise protocol rather than a supplement. "
    elif category == "sleep":
        intro += "This is a sleep-focused behavioral protocol rather than a supplement. "
    elif category == "stress_reduction":
        intro += "This is a structured stress-reduction practice rather than a supplement. "
    elif category == "environmental":
        intro += "This is an environmental exposure modification rather than a supplement. "
    elif category == "medication":
        intro += "This references a prescription medication for evidence context only. "
    elif category == "hormone":
        intro += "This references a regulated hormone therapy class for evidence context only. "
    elif category == "peptide":
        intro += "This is a peptide with published clinical trial literature. "

    if recommendation_intent == RecommendationIntent.CONTEXT_ONLY.value:
        intro += "This is context for discussion with your clinician, not a directive to start or change therapy. "
    elif recommendation_intent == RecommendationIntent.COLLATERAL.value:
        intro += "It addresses collateral or supportive biology — not necessarily the root cause your test names directly. "

    if mechanism:
        intro += f"Proposed mechanism from the literature: {mechanism}. "

    methodology = METHODOLOGY_BY_NAME.get(intervention_name)
    if methodology and category in LIFESTYLE_CATEGORIES:
        intro += f"The studied protocol specifies: {methodology} "

    food_part = _food_sources_sentence(food_sources or [])
    if food_part:
        return intro + food_part

    return (
        intro
        + "This references what trials studied, not a directive to self-treat. Discuss applicability with a qualified clinician."
    )
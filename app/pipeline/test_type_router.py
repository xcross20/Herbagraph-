"""Route abnormal labs to recommendation trees by result_kind and biomarker category."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.enums import RecommendationTree
from app.pipeline.biomarker_normalizer import get_reference_data
from app.schemas.pipeline import NormalizedLabResult, PathwayActivation

_ABNORMAL = frozenset({"critical_low", "low", "high", "critical_high"})

# Active infection / colonization tests (not serology exposure).
_ACTIVE_INFECTIOUS: frozenset[str] = frozenset({
    "H. pylori Urea Breath Test",
    "H. pylori Stool Antigen",
    "Hepatitis B Surface Antigen",
    "Hepatitis C Antibody",
    "HIV Ag/Ab 4th Gen",
    "Chlamydia trachomatis RNA",
    "Neisseria gonorrhoeae RNA",
    "RPR Syphilis Screen",
    "C. difficile Toxin",
    "TB Quantiferon",
    "Hepatitis A IgM",
    "Monospot",
    "Lyme Disease Antibody",
    "COVID-19 PCR",
    "Influenza A/B PCR",
    "RSV PCR",
    "Strep A Rapid Antigen",
})

_EXPOSURE_SERLOGY: frozenset[str] = frozenset({
    "H. pylori IgG Antibody",
})

_CULTURE_BIOMARKERS: frozenset[str] = frozenset({
    "Urine Culture",
    "Blood Culture",
    "Stool Culture",
    "Throat Culture",
    "Wound Culture",
    "Sputum Culture",
    "Vaginal Culture",
    "Cervical Culture",
})

_CELIAC_BIOMARKERS: frozenset[str] = frozenset({
    "tTG IgA",
    "tTG IgG",
    "EMA IgA",
    "Deamidated Gliadin IgA",
    "Deamidated Gliadin IgG",
})

_ALLERGY_IGE_MARKERS: frozenset[str] = frozenset({
    "Peanut IgE",
    "Milk IgE",
    "Egg IgE",
    "Wheat IgE",
    "Soy IgE",
    "Tree Nut IgE",
    "Shellfish IgE",
    "Fish IgE",
    "Dust Mite IgE",
    "Cat Dander IgE",
    "Dog Dander IgE",
    "Grass Pollen IgE",
    "Ragweed IgE",
    "Birch Pollen IgE",
    "Latex IgE",
    "Total IgE",
})

_PGX_MARKERS: frozenset[str] = frozenset({
    "CYP2D6 Genotype",
    "CYP2C19 Genotype",
    "CYP3A4 Genotype",
    "CYP2C9 Genotype",
    "VKORC1 Genotype",
    "SLCO1B1 Genotype",
    "TPMT Genotype",
    "DPYD Genotype",
    "HLA-B*5701",
    "MTHFR C677T",
    "Factor V Leiden",
    "Prothrombin G20210A",
})

# Nutritional markers where HIGH (not LOW) indicates functional deficiency.
_NUTRITIONAL_HIGH_MARKERS: frozenset[str] = frozenset({
    "Methylmalonic Acid",
    "Homocysteine",
    "Soluble Transferrin Receptor",
    "TIBC",
    "UIBC",
})

_NUTRITIONAL_MARKERS: frozenset[str] = frozenset({
    "Vitamin D",
    "B12",
    "Folate",
    "Ferritin",
    "Iron",
    "Magnesium",
    "Calcium",
    "Potassium",
    "Zinc",
    "Copper",
    "Selenium",
    "Transferrin Saturation",
    "Methylmalonic Acid",
    "Vitamin C",
    "Prealbumin",
    "Vitamin B6",
    "Vitamin B1",
    "Vitamin B2",
    "Vitamin A",
    "Vitamin E",
    "Vitamin K",
})

# CBC indices that often reflect B12/folate/iron patterns when abnormal.
_CBC_NUTRITIONAL_INDICATORS: frozenset[str] = frozenset({
    "MCV",
    "MCH",
    "RDW",
    "Hemoglobin",
})

_GI_EXOCRINE_MARKERS: frozenset[str] = frozenset({
    "Pancreatic Elastase",
})

_GI_INFLAMMATION_MARKERS: frozenset[str] = frozenset({
    "Fecal Calprotectin",
    "Fecal Lactoferrin",
})

_AUTOIMMUNE_MARKERS: frozenset[str] = frozenset({
    "ANA",
    "Anti-CCP",
    "Rheumatoid Factor",
    "TPO Antibody",
    "Thyroglobulin Antibody",
    "Anti-dsDNA",
    "Anti-Smith",
    "SSA/Ro Antibody",
    "SSB/La Antibody",
})


@dataclass
class RecommendationRoutingContext:
    """Output of the test-type router — drives intervention catalog and narratives."""

    trees: list[RecommendationTree] = field(default_factory=list)
    biomarkers_by_tree: dict[RecommendationTree, list[str]] = field(default_factory=dict)
    primary_tree: RecommendationTree | None = None


def _ref(lab: NormalizedLabResult) -> dict | None:
    return get_reference_data(lab.biomarker_name)


def _trees_for_lab(lab: NormalizedLabResult) -> list[RecommendationTree]:
    name = lab.biomarker_name
    ref = _ref(lab)
    result_kind = (ref or {}).get("result_kind", "numeric")
    category = lab.category or (ref or {}).get("category", "")

    if name in _PGX_MARKERS or category == "pharmacogenomics" or result_kind == "genotype":
        return [RecommendationTree.PGX_CONTEXT]

    if name in _EXPOSURE_SERLOGY:
        return [RecommendationTree.EXPOSURE, RecommendationTree.SIGNALING]

    if name in _ACTIVE_INFECTIOUS or (
        result_kind == "qualitative" and category == "infectious_disease" and name not in _EXPOSURE_SERLOGY
    ):
        return [RecommendationTree.ETIOLOGICAL, RecommendationTree.SIGNALING]

    if name in _CULTURE_BIOMARKERS or result_kind == "culture":
        return [RecommendationTree.CULTURE, RecommendationTree.ETIOLOGICAL, RecommendationTree.SIGNALING]

    if name in _GI_EXOCRINE_MARKERS and lab.status.value in ("low", "critical_low"):
        return [RecommendationTree.NUTRITIONAL_REPLETION, RecommendationTree.SIGNALING]

    if name in _GI_INFLAMMATION_MARKERS or category == "gi_stool":
        return [RecommendationTree.ETIOLOGICAL, RecommendationTree.SIGNALING]

    if name in _CELIAC_BIOMARKERS or category == "celiac_serology":
        return [RecommendationTree.CELIAC, RecommendationTree.NUTRITIONAL_REPLETION]

    if name in _ALLERGY_IGE_MARKERS or category == "allergy":
        return [RecommendationTree.ALLERGY]

    if name in _AUTOIMMUNE_MARKERS or category == "autoimmune":
        return [RecommendationTree.AUTOIMMUNE, RecommendationTree.SIGNALING]

    if name in _NUTRITIONAL_MARKERS and lab.status.value in ("low", "critical_low"):
        return [RecommendationTree.NUTRITIONAL_REPLETION, RecommendationTree.SIGNALING]

    if name in _NUTRITIONAL_HIGH_MARKERS and lab.status.value in ("high", "critical_high"):
        return [RecommendationTree.NUTRITIONAL_REPLETION, RecommendationTree.SIGNALING]

    if name in _CBC_NUTRITIONAL_INDICATORS and lab.status.value in _ABNORMAL:
        return [RecommendationTree.NUTRITIONAL_REPLETION, RecommendationTree.SIGNALING]

    return [RecommendationTree.SIGNALING]


def route_recommendation_trees(
    normalized_labs: list[NormalizedLabResult],
    pathway_activations: list[PathwayActivation] | None = None,
) -> RecommendationRoutingContext:
    """Select recommendation trees for all abnormal labs in the panel."""
    abnormal = [lab for lab in normalized_labs if lab.status.value in _ABNORMAL]
    if not abnormal:
        return RecommendationRoutingContext(trees=[RecommendationTree.SIGNALING], primary_tree=RecommendationTree.SIGNALING)

    tree_set: set[RecommendationTree] = set()
    biomarkers_by_tree: dict[RecommendationTree, list[str]] = {}

    for lab in abnormal:
        for tree in _trees_for_lab(lab):
            tree_set.add(tree)
            biomarkers_by_tree.setdefault(tree, [])
            if lab.biomarker_name not in biomarkers_by_tree[tree]:
                biomarkers_by_tree[tree].append(lab.biomarker_name)

    # Mixed inflammatory/metabolic panels: defer nutritional_repletion only when it was
    # triggered solely by high-only deficiency markers (Homocysteine, MMA) and signaling
    # has more abnormal contributors.
    if (
        RecommendationTree.SIGNALING in tree_set
        and RecommendationTree.NUTRITIONAL_REPLETION in tree_set
    ):
        nutritional_biomarkers = set(biomarkers_by_tree.get(RecommendationTree.NUTRITIONAL_REPLETION, []))
        if nutritional_biomarkers and nutritional_biomarkers <= _NUTRITIONAL_HIGH_MARKERS:
            signaling_count = len(biomarkers_by_tree.get(RecommendationTree.SIGNALING, []))
            nutritional_count = len(nutritional_biomarkers)
            if signaling_count > nutritional_count:
                tree_set.discard(RecommendationTree.NUTRITIONAL_REPLETION)
                biomarkers_by_tree.pop(RecommendationTree.NUTRITIONAL_REPLETION, None)

    # Priority order for primary tree selection.
    priority = [
        RecommendationTree.PGX_CONTEXT,
        RecommendationTree.ETIOLOGICAL,
        RecommendationTree.CULTURE,
        RecommendationTree.CELIAC,
        RecommendationTree.ALLERGY,
        RecommendationTree.AUTOIMMUNE,
        RecommendationTree.EXPOSURE,
        RecommendationTree.NUTRITIONAL_REPLETION,
        RecommendationTree.SIGNALING,
    ]
    primary = next((t for t in priority if t in tree_set), RecommendationTree.SIGNALING)

    ordered_trees = [t for t in priority if t in tree_set]
    return RecommendationRoutingContext(
        trees=ordered_trees,
        biomarkers_by_tree=biomarkers_by_tree,
        primary_tree=primary,
    )
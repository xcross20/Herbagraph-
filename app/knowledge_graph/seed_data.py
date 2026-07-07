"""Canonical botanical/nutraceutical knowledge graph seed data.

This module is the single source of truth for `scripts/seed_db.py`. It is pure
data (no I/O) so it can be imported and asserted against directly in tests.
"""

from app.knowledge_graph.biomarker_catalog import get_seed_records
from app.knowledge_graph.catalog_merge import merge_interventions
from app.knowledge_graph.herb_catalog import HERB_INTERVENTIONS
from app.knowledge_graph.lifestyle_evidence import LIFESTYLE_EVIDENCE_CLAIMS
from app.knowledge_graph.lifestyle_methods_catalog import LIFESTYLE_INTERVENTIONS
from app.knowledge_graph.supplement_catalog import SUPPLEMENT_INTERVENTIONS
from app.knowledge_graph.tier_a_catalog import TIER_A_HERBS, TIER_A_SUPPLEMENTS
from app.knowledge_graph.tier_a_evidence import TIER_A_EVIDENCE_CLAIMS

# ---------------------------------------------------------------------------
# 266 Biomarkers: comprehensive clinical panel
# ---------------------------------------------------------------------------
BIOMARKERS: list[dict] = get_seed_records()

# ---------------------------------------------------------------------------
# 16 host signaling pathways + 12 etiological pathways
# ---------------------------------------------------------------------------
SIGNALING_PATHWAYS: list[dict] = [
    {"code": "NF_KB", "name": "NF-κB Inflammatory Signaling",
     "description": "Master transcriptional regulator of the inflammatory response."},
    {"code": "IL6_JAK_STAT3", "name": "IL-6/JAK-STAT3 Signaling",
     "description": "Cytokine signaling axis driving the acute-phase response."},
    {"code": "AMPK", "name": "AMPK Energy Sensing",
     "description": "Cellular energy sensor that promotes catabolism and mitochondrial biogenesis."},
    {"code": "INSULIN_PI3K_AKT", "name": "Insulin/PI3K-Akt Signaling",
     "description": "Insulin receptor signaling cascade governing glucose uptake."},
    {"code": "NRF2", "name": "Nrf2 Antioxidant Response",
     "description": "Master regulator of the cellular antioxidant and detoxification response."},
    {"code": "MTOR_AUTOPHAGY", "name": "mTOR/Autophagy",
     "description": "Nutrient-sensing pathway balancing growth signaling against autophagic recycling."},
    {"code": "HPA_AXIS", "name": "HPA Axis (Stress Response)",
     "description": "Hypothalamic-pituitary-adrenal axis governing the cortisol stress response."},
    {"code": "THYROID_HPT", "name": "Thyroid/HPT Axis",
     "description": "Hypothalamic-pituitary-thyroid axis governing thyroid hormone output."},
    {"code": "HEPATIC_LIPID", "name": "Hepatic Lipid Metabolism",
     "description": "Hepatic pathways governing lipid synthesis, oxidation, and export."},
    {"code": "ONE_CARBON_METHYLATION", "name": "One-Carbon/Methylation Cycle",
     "description": "Folate/B12-dependent methylation cycle that clears homocysteine."},
    {"code": "GLP1_INCRETINS", "name": "GLP-1/Incretin Signaling",
     "description": "Incretin hormone signaling that regulates postprandial glucose and satiety."},
    {"code": "MITOCHONDRIAL_NAD", "name": "Mitochondrial NAD+ Metabolism",
     "description": "NAD+-dependent mitochondrial bioenergetics and sirtuin activity."},
    {"code": "IRON_HEPCIDIN", "name": "Iron/Hepcidin Regulation",
     "description": "Hepcidin-mediated regulation of iron absorption and storage."},
    {"code": "PURINE_URIC_ACID", "name": "Purine/Uric Acid Metabolism",
     "description": "Purine catabolism pathway terminating in uric acid production."},
    {"code": "VITAMIN_D_RECEPTOR", "name": "Vitamin D Receptor Signaling",
     "description": "Nuclear receptor signaling mediating vitamin D's immune and skeletal effects."},
    {"code": "RENAL_FILTRATION", "name": "Renal Filtration Function",
     "description": "Glomerular filtration and renal clearance function."},
]

ETIOLOGICAL_PATHWAYS: list[dict] = [
    {"code": "GASTRIC_COLONIZATION", "name": "Gastric Pathogen Colonization",
     "description": "Active colonization of the gastric niche (e.g. H. pylori).", "pathway_type": "etiological"},
    {"code": "GI_MUCOSAL_BARRIER", "name": "GI Mucosal Barrier Integrity",
     "description": "Epithelial barrier function and mucosal healing in the GI tract.", "pathway_type": "etiological"},
    {"code": "PATHOGEN_BURDEN", "name": "Pathogen Burden",
     "description": "Active infectious organism load detected by lab testing.", "pathway_type": "etiological"},
    {"code": "BIOFILM_ADHESION", "name": "Biofilm and Microbial Adhesion",
     "description": "Persistent colonization via biofilm and adhesion mechanisms.", "pathway_type": "etiological"},
    {"code": "FOOD_ANTIGEN_EXPOSURE", "name": "Food Antigen Exposure",
     "description": "Dietary antigen driving immune response (e.g. gluten in celiac disease).", "pathway_type": "etiological"},
    {"code": "IGE_SENSITIZATION", "name": "IgE Sensitization",
     "description": "Allergen-specific IgE-mediated sensitization.", "pathway_type": "etiological"},
    {"code": "AUTOIMMUNE_TARGETING", "name": "Autoimmune Targeting",
     "description": "Self-antigen immune response driving autoimmune serology.", "pathway_type": "etiological"},
    {"code": "HEPATOTROPIC_VIRAL", "name": "Hepatotropic Viral Infection",
     "description": "Viral hepatitis markers indicating liver-tropic infection.", "pathway_type": "etiological"},
    {"code": "DRUG_METABOLISM_VARIANT", "name": "Drug Metabolism Variant",
     "description": "Pharmacogenomic variants affecting drug metabolism and safety.", "pathway_type": "etiological"},
    {"code": "NUTRIENT_DEFICIENCY", "name": "Nutrient Deficiency",
     "description": "Measured deficiency of essential vitamins, minerals, or cofactors.", "pathway_type": "etiological"},
    {"code": "URINARY_PATHOGEN", "name": "Urinary Tract Pathogen",
     "description": "Bacterial colonization of the urinary tract.", "pathway_type": "etiological"},
    {"code": "RESPIRATORY_PATHOGEN", "name": "Respiratory Pathogen",
     "description": "Upper or lower respiratory tract infection markers.", "pathway_type": "etiological"},
]

PATHWAYS: list[dict] = [
    {**pw, "pathway_type": "signaling"} for pw in SIGNALING_PATHWAYS
] + ETIOLOGICAL_PATHWAYS

# ---------------------------------------------------------------------------
# Interventions: 200 herbs + 200 supplements + 77 lifestyle methods (Tier A merged)
# ---------------------------------------------------------------------------
_TIER_A_SUPPLEMENT_ONLY = [s for s in TIER_A_SUPPLEMENTS if s["category"] == "supplement"]
_CURATED_OVERRIDE = TIER_A_HERBS + _TIER_A_SUPPLEMENT_ONLY + LIFESTYLE_INTERVENTIONS

INTERVENTIONS: list[dict] = merge_interventions(
    SUPPLEMENT_INTERVENTIONS,
    HERB_INTERVENTIONS,
    curated=_CURATED_OVERRIDE,
)

SUPPLEMENT_LIFESTYLE_INTERVENTIONS: list[dict] = [
    i for i in INTERVENTIONS if i["category"] not in ("herb", "food", "phytochemical", "peptide")
]

# ---------------------------------------------------------------------------
# Evidence claims — Tier A + lifestyle (real PMIDs); lifestyle overrides Tier A dupes
# ---------------------------------------------------------------------------
_LIFESTYLE_EVIDENCE_NAMES = {c["intervention_name"] for c in LIFESTYLE_EVIDENCE_CLAIMS}

EVIDENCE_CLAIMS: list[dict] = [
    c for c in TIER_A_EVIDENCE_CLAIMS if c["intervention_name"] not in _LIFESTYLE_EVIDENCE_NAMES
] + LIFESTYLE_EVIDENCE_CLAIMS


def expected_seeded_intervention_count(
    *,
    food_interventions: list[dict],
    phytochemical_compounds: list[dict],
    peptide_interventions: list[dict],
) -> int:
    """Unique intervention names after seeder deduplication (supplement/phytochemical name overlap)."""
    names = {i["name"] for i in INTERVENTIONS}
    for data in [*phytochemical_compounds, *food_interventions, *peptide_interventions]:
        names.add(data["name"])
    return len(names)
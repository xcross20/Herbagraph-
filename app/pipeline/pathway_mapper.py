"""Stage 3: Pathway Mapper.

Maps each abnormal biomarker to one or more of the 16 biological pathways
with weighted activation scores, using 50+ biomarker-to-pathway rules across
the 25-biomarker MVP panel. These scores are internal/evidence-weighted
signals, not direct measurements of biological activation -- see
app/pipeline/biological_systems.py for the simplified, user-facing rollup
into 7 biological systems with a 0-3 signal scale.
"""

from app.models.enums import LabResultStatus, PathwayDirection
from app.pipeline.pathway_mapping_catalog import build_catalog_pathway_configs
from app.schemas.pipeline import NormalizedLabResult, PathwayActivation

_ABNORMAL_STATUSES = {
    LabResultStatus.CRITICAL_LOW,
    LabResultStatus.LOW,
    LabResultStatus.HIGH,
    LabResultStatus.CRITICAL_HIGH,
}

_SEVERITY_MULTIPLIER = {
    LabResultStatus.CRITICAL_LOW: 1.3,
    LabResultStatus.LOW: 1.0,
    LabResultStatus.HIGH: 1.0,
    LabResultStatus.CRITICAL_HIGH: 1.3,
}

_PATHWAY_NAMES = {
    "NF_KB": "NF-κB Inflammatory Signaling",
    "IL6_JAK_STAT3": "IL-6/JAK-STAT3 Signaling",
    "AMPK": "AMPK Energy Sensing",
    "INSULIN_PI3K_AKT": "Insulin/PI3K-Akt Signaling",
    "NRF2": "Nrf2 Antioxidant Response",
    "MTOR_AUTOPHAGY": "mTOR/Autophagy",
    "HPA_AXIS": "HPA Axis (Stress Response)",
    "THYROID_HPT": "Thyroid/HPT Axis",
    "HEPATIC_LIPID": "Hepatic Lipid Metabolism",
    "ONE_CARBON_METHYLATION": "One-Carbon/Methylation Cycle",
    "GLP1_INCRETINS": "GLP-1/Incretin Signaling",
    "MITOCHONDRIAL_NAD": "Mitochondrial NAD+ Metabolism",
    "IRON_HEPCIDIN": "Iron/Hepcidin Regulation",
    "PURINE_URIC_ACID": "Purine/Uric Acid Metabolism",
    "VITAMIN_D_RECEPTOR": "Vitamin D Receptor Signaling",
    "RENAL_FILTRATION": "Renal Filtration Function",
    # Etiological pathways
    "GASTRIC_COLONIZATION": "Gastric Pathogen Colonization",
    "GI_MUCOSAL_BARRIER": "GI Mucosal Barrier Integrity",
    "PATHOGEN_BURDEN": "Pathogen Burden",
    "BIOFILM_ADHESION": "Biofilm and Microbial Adhesion",
    "FOOD_ANTIGEN_EXPOSURE": "Food Antigen Exposure",
    "IGE_SENSITIZATION": "IgE Sensitization",
    "AUTOIMMUNE_TARGETING": "Autoimmune Targeting",
    "HEPATOTROPIC_VIRAL": "Hepatotropic Viral Infection",
    "DRUG_METABOLISM_VARIANT": "Drug Metabolism Variant",
    "NUTRIENT_DEFICIENCY": "Nutrient Deficiency",
    "URINARY_PATHOGEN": "Urinary Tract Pathogen",
    "RESPIRATORY_PATHOGEN": "Respiratory Pathogen",
}

# Custom/profile display names that should hit catalog pathway rules.
_PATHWAY_BIOMARKER_ALIASES: dict[str, str] = {
    "Lp(a) Mass": "Lp(a)",
    # Portal display names that may persist before alias refresh / custom profile overlap.
    "Iron, Total": "Iron",
    "Vitamin D, 25-OH": "Vitamin D",
    "Vit D 25-Hydroxy": "Vitamin D",
    "Vitamin B-12": "B12",
    "Folate (Folic Acid), Serum": "Folate",
    "Zinc, Plasma": "Zinc",
    "Copper, Serum": "Copper",
    "Selenium, Serum": "Selenium",
    "Magnesium, RBC": "Magnesium",
    "% Saturation": "Transferrin Saturation",
    "Iron Binding Capacity": "TIBC",
    "Vitamin A, Serum": "Vitamin A",
    "Vitamin E, Serum": "Vitamin E",
    "Vitamin K, Plasma": "Vitamin K",
    "Thiamine, Plasma": "Vitamin B1",
    "Riboflavin, Plasma": "Vitamin B2",
    "Pyridoxine, Plasma": "Vitamin B6",
    "Vitamin C, Plasma": "Vitamin C",
    "Prealbumin, Serum": "Prealbumin",
    "Soluble Transferrin Receptor, Serum": "Soluble Transferrin Receptor",
}

# Each rule: (biomarker_name, {triggering statuses}, pathway_code, weight, direction)
_PATHWAY_CONFIGS_CORE: list[tuple[str, set[LabResultStatus], str, float, PathwayDirection]] = [
    ("CRP", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "NF_KB", 0.9, PathwayDirection.ACTIVATED),
    ("CRP", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "IL6_JAK_STAT3", 0.7, PathwayDirection.ACTIVATED),

    ("Homocysteine", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "ONE_CARBON_METHYLATION", 0.9,
     PathwayDirection.SUPPRESSED),
    ("Methylmalonic Acid", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "ONE_CARBON_METHYLATION", 0.8,
     PathwayDirection.SUPPRESSED),
    ("Methylmalonic Acid", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "NUTRIENT_DEFICIENCY", 0.85,
     PathwayDirection.SUPPRESSED),
    ("Homocysteine", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "NF_KB", 0.3,
     PathwayDirection.ACTIVATED),

    ("Glucose", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "INSULIN_PI3K_AKT", 0.8,
     PathwayDirection.SUPPRESSED),
    ("Glucose", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "GLP1_INCRETINS", 0.5,
     PathwayDirection.SUPPRESSED),
    ("Glucose", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "AMPK", 0.4, PathwayDirection.SUPPRESSED),

    ("HbA1c", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "INSULIN_PI3K_AKT", 0.9,
     PathwayDirection.SUPPRESSED),
    ("HbA1c", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "GLP1_INCRETINS", 0.5,
     PathwayDirection.SUPPRESSED),
    ("HbA1c", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "MITOCHONDRIAL_NAD", 0.3,
     PathwayDirection.SUPPRESSED),

    ("Insulin", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "INSULIN_PI3K_AKT", 0.85,
     PathwayDirection.SUPPRESSED),
    ("Insulin", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "MTOR_AUTOPHAGY", 0.4,
     PathwayDirection.ACTIVATED),

    ("Uric Acid", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "PURINE_URIC_ACID", 0.9,
     PathwayDirection.ACTIVATED),
    ("Uric Acid", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "NF_KB", 0.3,
     PathwayDirection.ACTIVATED),
    ("Uric Acid", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "RENAL_FILTRATION", 0.4,
     PathwayDirection.SUPPRESSED),

    ("LDL", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "HEPATIC_LIPID", 0.9,
     PathwayDirection.ACTIVATED),
    ("LDL", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "NRF2", 0.4, PathwayDirection.SUPPRESSED),

    ("HDL", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "HEPATIC_LIPID", 0.6,
     PathwayDirection.SUPPRESSED),
    ("HDL", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "NRF2", 0.3, PathwayDirection.SUPPRESSED),

    ("Triglycerides", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "HEPATIC_LIPID", 0.85,
     PathwayDirection.ACTIVATED),
    ("Triglycerides", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "AMPK", 0.3,
     PathwayDirection.SUPPRESSED),

    ("ALT", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "HEPATIC_LIPID", 0.7,
     PathwayDirection.ACTIVATED),
    ("ALT", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "NRF2", 0.5, PathwayDirection.SUPPRESSED),

    ("AST", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "HEPATIC_LIPID", 0.6,
     PathwayDirection.ACTIVATED),
    ("AST", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "NRF2", 0.4, PathwayDirection.SUPPRESSED),
    ("AST", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "MITOCHONDRIAL_NAD", 0.3,
     PathwayDirection.SUPPRESSED),

    ("Vitamin D", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "VITAMIN_D_RECEPTOR", 0.9,
     PathwayDirection.SUPPRESSED),

    ("TSH", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "THYROID_HPT", 0.8,
     PathwayDirection.SUPPRESSED),
    ("TSH", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "HPA_AXIS", 0.3, PathwayDirection.ACTIVATED),
    ("TSH", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "THYROID_HPT", 0.8,
     PathwayDirection.ACTIVATED),

    ("B12", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "ONE_CARBON_METHYLATION", 0.8,
     PathwayDirection.SUPPRESSED),

    ("Folate", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "ONE_CARBON_METHYLATION", 0.85,
     PathwayDirection.SUPPRESSED),

    ("Ferritin", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "IRON_HEPCIDIN", 0.85,
     PathwayDirection.ACTIVATED),
    ("Ferritin", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "NF_KB", 0.3,
     PathwayDirection.ACTIVATED),
    ("Ferritin", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "IRON_HEPCIDIN", 0.85,
     PathwayDirection.SUPPRESSED),
    ("Ferritin", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "MITOCHONDRIAL_NAD", 0.3,
     PathwayDirection.SUPPRESSED),

    ("Vitamin D", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "VITAMIN_D_RECEPTOR", 0.5,
     PathwayDirection.ACTIVATED),

    ("Triglycerides", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "MITOCHONDRIAL_NAD", 0.2,
     PathwayDirection.SUPPRESSED),

    ("Glucose", {LabResultStatus.CRITICAL_HIGH}, "RENAL_FILTRATION", 0.3, PathwayDirection.SUPPRESSED),

    ("HbA1c", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "NF_KB", 0.2,
     PathwayDirection.ACTIVATED),

    ("LDL", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "IL6_JAK_STAT3", 0.2,
     PathwayDirection.ACTIVATED),

    # --- Rules for the 8 "optional near-MVP" / core-panel additions (ApoB, GGT, Creatinine,
    # eGFR, Lp(a), Free T3, Free T4, Cortisol, DHEA-S) ---
    ("ApoB", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "HEPATIC_LIPID", 0.9,
     PathwayDirection.ACTIVATED),

    ("GGT", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "HEPATIC_LIPID", 0.5,
     PathwayDirection.ACTIVATED),
    ("GGT", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "NRF2", 0.5,
     PathwayDirection.SUPPRESSED),

    ("Creatinine", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "RENAL_FILTRATION", 0.85,
     PathwayDirection.SUPPRESSED),

    ("eGFR", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "RENAL_FILTRATION", 0.9,
     PathwayDirection.SUPPRESSED),

    ("Lp(a)", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "HEPATIC_LIPID", 0.6,
     PathwayDirection.ACTIVATED),

    ("Free T3", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "THYROID_HPT", 0.7,
     PathwayDirection.SUPPRESSED),
    ("Free T3", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "THYROID_HPT", 0.5,
     PathwayDirection.ACTIVATED),

    ("Free T4", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "THYROID_HPT", 0.7,
     PathwayDirection.SUPPRESSED),
    ("Free T4", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "THYROID_HPT", 0.5,
     PathwayDirection.ACTIVATED),

    ("Cortisol", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "HPA_AXIS", 0.8,
     PathwayDirection.ACTIVATED),
    ("Cortisol", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "HPA_AXIS", 0.6,
     PathwayDirection.SUPPRESSED),

    ("DHEA-S", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "HPA_AXIS", 0.4,
     PathwayDirection.SUPPRESSED),

    # --- Expanded catalog (200+ biomarker panel) ---
    ("BUN", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "RENAL_FILTRATION", 0.7,
     PathwayDirection.SUPPRESSED),
    ("Hemoglobin", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "IRON_HEPCIDIN", 0.75,
     PathwayDirection.SUPPRESSED),
    ("WBC", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "NF_KB", 0.5,
     PathwayDirection.ACTIVATED),
    ("WBC", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "IL6_JAK_STAT3", 0.4,
     PathwayDirection.ACTIVATED),
    ("Albumin", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "HEPATIC_LIPID", 0.5,
     PathwayDirection.SUPPRESSED),
    ("Alkaline Phosphatase", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "HEPATIC_LIPID", 0.55,
     PathwayDirection.ACTIVATED),
    ("Bilirubin Total", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "HEPATIC_LIPID", 0.65,
     PathwayDirection.ACTIVATED),
    ("Bilirubin Total", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "NRF2", 0.4,
     PathwayDirection.SUPPRESSED),
    ("Total Cholesterol", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "HEPATIC_LIPID", 0.7,
     PathwayDirection.ACTIVATED),
    ("Non-HDL Cholesterol", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "HEPATIC_LIPID", 0.8,
     PathwayDirection.ACTIVATED),
    ("ESR", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "NF_KB", 0.6,
     PathwayDirection.ACTIVATED),
    ("Iron", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "IRON_HEPCIDIN", 0.8,
     PathwayDirection.SUPPRESSED),
    ("Transferrin Saturation", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "IRON_HEPCIDIN", 0.7,
     PathwayDirection.SUPPRESSED),
    ("Soluble Transferrin Receptor", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "IRON_HEPCIDIN", 0.75,
     PathwayDirection.SUPPRESSED),
    ("TIBC", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "IRON_HEPCIDIN", 0.7,
     PathwayDirection.SUPPRESSED),
    ("UIBC", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "IRON_HEPCIDIN", 0.7,
     PathwayDirection.SUPPRESSED),
    ("Potassium", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "RENAL_FILTRATION", 0.4,
     PathwayDirection.SUPPRESSED),
    ("Potassium", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "RENAL_FILTRATION", 0.5,
     PathwayDirection.SUPPRESSED),
    ("Sodium", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "RENAL_FILTRATION", 0.4,
     PathwayDirection.SUPPRESSED),
    ("Microalbumin", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "RENAL_FILTRATION", 0.75,
     PathwayDirection.SUPPRESSED),
    ("Cystatin C", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "RENAL_FILTRATION", 0.7,
     PathwayDirection.SUPPRESSED),
    ("LDH", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "MITOCHONDRIAL_NAD", 0.4,
     PathwayDirection.SUPPRESSED),
    ("BNP", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "IL6_JAK_STAT3", 0.5,
     PathwayDirection.ACTIVATED),
    ("Testosterone Total", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "HPA_AXIS", 0.4,
     PathwayDirection.SUPPRESSED),
    ("Estradiol", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "HPA_AXIS", 0.35,
     PathwayDirection.SUPPRESSED),
    ("Zinc", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "ONE_CARBON_METHYLATION", 0.3,
     PathwayDirection.SUPPRESSED),
    ("Magnesium", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "INSULIN_PI3K_AKT", 0.35,
     PathwayDirection.SUPPRESSED),
    ("Magnesium", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "NUTRIENT_DEFICIENCY", 0.8,
     PathwayDirection.SUPPRESSED),
    ("Calcium", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "NUTRIENT_DEFICIENCY", 0.8,
     PathwayDirection.SUPPRESSED),
    ("Potassium", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "NUTRIENT_DEFICIENCY", 0.8,
     PathwayDirection.SUPPRESSED),
    ("Copper", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "NUTRIENT_DEFICIENCY", 0.8,
     PathwayDirection.SUPPRESSED),
    ("Selenium", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "NUTRIENT_DEFICIENCY", 0.75,
     PathwayDirection.SUPPRESSED),
    ("Vitamin C", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "NUTRIENT_DEFICIENCY", 0.8,
     PathwayDirection.SUPPRESSED),
    ("Prealbumin", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "NUTRIENT_DEFICIENCY", 0.85,
     PathwayDirection.SUPPRESSED),
    ("Vitamin B6", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "NUTRIENT_DEFICIENCY", 0.8,
     PathwayDirection.SUPPRESSED),
    ("Vitamin B1", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "NUTRIENT_DEFICIENCY", 0.8,
     PathwayDirection.SUPPRESSED),
    ("Vitamin B2", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "NUTRIENT_DEFICIENCY", 0.8,
     PathwayDirection.SUPPRESSED),
    ("Vitamin A", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "NUTRIENT_DEFICIENCY", 0.85,
     PathwayDirection.SUPPRESSED),
    ("Vitamin E", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "NUTRIENT_DEFICIENCY", 0.8,
     PathwayDirection.SUPPRESSED),
    ("Vitamin K", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "NUTRIENT_DEFICIENCY", 0.8,
     PathwayDirection.SUPPRESSED),
    ("Urine Protein", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "RENAL_FILTRATION", 0.6,
     PathwayDirection.SUPPRESSED),
    ("Urine Ketones", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "INSULIN_PI3K_AKT", 0.5,
     PathwayDirection.SUPPRESSED),

    # --- Infectious disease / microbiology (qualitative positives) ---
    ("H. pylori Urea Breath Test", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "NF_KB", 0.75,
     PathwayDirection.ACTIVATED),
    ("H. pylori Urea Breath Test", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "IL6_JAK_STAT3", 0.5,
     PathwayDirection.ACTIVATED),
    ("H. pylori Stool Antigen", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "NF_KB", 0.75,
     PathwayDirection.ACTIVATED),
    ("H. pylori IgG Antibody", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "NF_KB", 0.4,
     PathwayDirection.ACTIVATED),
    ("Hepatitis B Surface Antigen", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "HEPATIC_LIPID", 0.8,
     PathwayDirection.ACTIVATED),
    ("Hepatitis C Antibody", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "HEPATIC_LIPID", 0.7,
     PathwayDirection.ACTIVATED),
    ("HIV Ag/Ab 4th Gen", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "NF_KB", 0.6,
     PathwayDirection.ACTIVATED),
    ("Chlamydia trachomatis RNA", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "NF_KB", 0.5,
     PathwayDirection.ACTIVATED),
    ("Neisseria gonorrhoeae RNA", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "NF_KB", 0.5,
     PathwayDirection.ACTIVATED),
    ("RPR Syphilis Screen", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "NF_KB", 0.45,
     PathwayDirection.ACTIVATED),
    ("C. difficile Toxin", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "NF_KB", 0.65,
     PathwayDirection.ACTIVATED),
    ("TB Quantiferon", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "NF_KB", 0.55,
     PathwayDirection.ACTIVATED),

    # --- Etiological pathways (root-cause layer) ---
    ("H. pylori Urea Breath Test", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "GASTRIC_COLONIZATION", 0.9,
     PathwayDirection.ACTIVATED),
    ("H. pylori Stool Antigen", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "GASTRIC_COLONIZATION", 0.9,
     PathwayDirection.ACTIVATED),
    ("H. pylori Urea Breath Test", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "GI_MUCOSAL_BARRIER", 0.6,
     PathwayDirection.SUPPRESSED),
    ("H. pylori IgG Antibody", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "GASTRIC_COLONIZATION", 0.3,
     PathwayDirection.ACTIVATED),
    ("Hepatitis B Surface Antigen", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "HEPATOTROPIC_VIRAL", 0.9,
     PathwayDirection.ACTIVATED),
    ("Hepatitis C Antibody", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "HEPATOTROPIC_VIRAL", 0.85,
     PathwayDirection.ACTIVATED),
    ("Hepatitis A IgM", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "HEPATOTROPIC_VIRAL", 0.85,
     PathwayDirection.ACTIVATED),
    ("C. difficile Toxin", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "PATHOGEN_BURDEN", 0.85,
     PathwayDirection.ACTIVATED),
    ("Chlamydia trachomatis RNA", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "PATHOGEN_BURDEN", 0.8,
     PathwayDirection.ACTIVATED),
    ("Neisseria gonorrhoeae RNA", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "PATHOGEN_BURDEN", 0.8,
     PathwayDirection.ACTIVATED),
    ("Urine Culture", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "URINARY_PATHOGEN", 0.9,
     PathwayDirection.ACTIVATED),
    ("Urine Culture", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "PATHOGEN_BURDEN", 0.75,
     PathwayDirection.ACTIVATED),
    ("Blood Culture", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "PATHOGEN_BURDEN", 0.9,
     PathwayDirection.ACTIVATED),
    ("Stool Culture", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "PATHOGEN_BURDEN", 0.8,
     PathwayDirection.ACTIVATED),
    ("Throat Culture", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "RESPIRATORY_PATHOGEN", 0.8,
     PathwayDirection.ACTIVATED),
    ("Throat Culture", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "BIOFILM_ADHESION", 0.45,
     PathwayDirection.ACTIVATED),
    ("Sputum Culture", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "RESPIRATORY_PATHOGEN", 0.85,
     PathwayDirection.ACTIVATED),
    ("tTG IgA", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "FOOD_ANTIGEN_EXPOSURE", 0.95,
     PathwayDirection.ACTIVATED),
    ("tTG IgG", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "FOOD_ANTIGEN_EXPOSURE", 0.95,
     PathwayDirection.ACTIVATED),
    ("EMA IgA", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "FOOD_ANTIGEN_EXPOSURE", 0.95,
     PathwayDirection.ACTIVATED),
    ("Deamidated Gliadin IgA", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "FOOD_ANTIGEN_EXPOSURE", 0.9,
     PathwayDirection.ACTIVATED),
    ("Deamidated Gliadin IgG", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "FOOD_ANTIGEN_EXPOSURE", 0.9,
     PathwayDirection.ACTIVATED),
    ("Peanut IgE", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "IGE_SENSITIZATION", 0.9,
     PathwayDirection.ACTIVATED),
    ("Milk IgE", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "IGE_SENSITIZATION", 0.9,
     PathwayDirection.ACTIVATED),
    ("Total IgE", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "IGE_SENSITIZATION", 0.7,
     PathwayDirection.ACTIVATED),
    ("CYP2D6 Genotype", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "DRUG_METABOLISM_VARIANT", 0.95,
     PathwayDirection.ACTIVATED),
    ("CYP2C19 Genotype", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "DRUG_METABOLISM_VARIANT", 0.95,
     PathwayDirection.ACTIVATED),
    ("DPYD Genotype", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "DRUG_METABOLISM_VARIANT", 0.95,
     PathwayDirection.ACTIVATED),
    ("Vitamin D", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "NUTRIENT_DEFICIENCY", 0.9,
     PathwayDirection.SUPPRESSED),
    ("B12", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "NUTRIENT_DEFICIENCY", 0.9,
     PathwayDirection.SUPPRESSED),
    ("Folate", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "NUTRIENT_DEFICIENCY", 0.9,
     PathwayDirection.SUPPRESSED),
    ("Ferritin", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "NUTRIENT_DEFICIENCY", 0.75,
     PathwayDirection.SUPPRESSED),
    ("Iron", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "NUTRIENT_DEFICIENCY", 0.85,
     PathwayDirection.SUPPRESSED),
    ("Zinc", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "NUTRIENT_DEFICIENCY", 0.8,
     PathwayDirection.SUPPRESSED),

    # --- CBC indices: macrocytosis / anisocytosis nutrient patterns ---
    ("MCV", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "ONE_CARBON_METHYLATION", 0.85,
     PathwayDirection.SUPPRESSED),
    ("MCV", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "NUTRIENT_DEFICIENCY", 0.85,
     PathwayDirection.SUPPRESSED),
    ("MCV", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "THYROID_HPT", 0.35,
     PathwayDirection.SUPPRESSED),
    ("MCV", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "IRON_HEPCIDIN", 0.8,
     PathwayDirection.SUPPRESSED),
    ("MCV", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "NUTRIENT_DEFICIENCY", 0.75,
     PathwayDirection.SUPPRESSED),

    ("MCH", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "ONE_CARBON_METHYLATION", 0.8,
     PathwayDirection.SUPPRESSED),
    ("MCH", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "NUTRIENT_DEFICIENCY", 0.8,
     PathwayDirection.SUPPRESSED),
    ("MCH", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "IRON_HEPCIDIN", 0.75,
     PathwayDirection.SUPPRESSED),
    ("MCH", {LabResultStatus.LOW, LabResultStatus.CRITICAL_LOW}, "NUTRIENT_DEFICIENCY", 0.7,
     PathwayDirection.SUPPRESSED),

    ("RDW", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "IRON_HEPCIDIN", 0.7,
     PathwayDirection.SUPPRESSED),
    ("RDW", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "ONE_CARBON_METHYLATION", 0.6,
     PathwayDirection.SUPPRESSED),
    ("RDW", {LabResultStatus.HIGH, LabResultStatus.CRITICAL_HIGH}, "NUTRIENT_DEFICIENCY", 0.75,
     PathwayDirection.SUPPRESSED),
]

_CORE_BIOMARKERS = {rule[0] for rule in _PATHWAY_CONFIGS_CORE}
_PATHWAY_CONFIGS: list[tuple[str, set[LabResultStatus], str, float, PathwayDirection]] = [
    *_PATHWAY_CONFIGS_CORE,
    *build_catalog_pathway_configs(skip_biomarkers=_CORE_BIOMARKERS),
]


def _abnormal_for_pathway_rule(
    rule_biomarker: str,
    abnormal: dict[str, NormalizedLabResult],
) -> NormalizedLabResult | None:
    hit = abnormal.get(rule_biomarker)
    if hit is not None:
        return hit
    for observed_name, result in abnormal.items():
        if _PATHWAY_BIOMARKER_ALIASES.get(observed_name) == rule_biomarker:
            return result
    return None


def map_pathways(normalized_results: list[NormalizedLabResult]) -> list[PathwayActivation]:
    """Map abnormal biomarkers to activated/suppressed pathways with weighted activation scores."""
    abnormal = {r.biomarker_name: r for r in normalized_results if r.status in _ABNORMAL_STATUSES}

    # pathway_code -> {"activated": float, "suppressed": float, "biomarkers": set[str]}
    accum: dict[str, dict] = {}

    for biomarker_name, statuses, pathway_code, weight, direction in _PATHWAY_CONFIGS:
        result = _abnormal_for_pathway_rule(biomarker_name, abnormal)
        if result is None or result.status not in statuses:
            continue
        multiplier = _SEVERITY_MULTIPLIER[result.status]
        bucket = accum.setdefault(pathway_code, {"activated": 0.0, "suppressed": 0.0, "biomarkers": set()})
        bucket[direction.value] += weight * multiplier
        bucket["biomarkers"].add(result.biomarker_name)

    activations: list[PathwayActivation] = []
    for pathway_code, bucket in accum.items():
        net_activated = bucket["activated"]
        net_suppressed = bucket["suppressed"]
        if net_activated >= net_suppressed:
            direction = PathwayDirection.ACTIVATED
            score = net_activated
        else:
            direction = PathwayDirection.SUPPRESSED
            score = net_suppressed
        activations.append(
            PathwayActivation(
                pathway_code=pathway_code,
                pathway_name=_PATHWAY_NAMES[pathway_code],
                activation_score=min(score, 1.0),
                direction=direction,
                contributing_biomarkers=sorted(bucket["biomarkers"]),
            )
        )

    activations.sort(key=lambda a: a.activation_score, reverse=True)
    return activations


def get_pathways_for_biomarker(biomarker_name: str) -> set[str]:
    """All pathway codes this biomarker can contribute to, regardless of status/direction.

    Used by app.pipeline.response_analysis to figure out which biological systems a
    biomarker's baseline->follow-up change should be attributed to.
    """
    return {code for name, _statuses, code, _weight, _direction in _PATHWAY_CONFIGS if name == biomarker_name}

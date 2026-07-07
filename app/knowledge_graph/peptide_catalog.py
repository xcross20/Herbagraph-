"""Clinically evidenced peptide interventions.

Only peptides with published human clinical trial literature (each claim has a
verifiable PMID) are included. Investigational peptides without clinical papers
(e.g. BPC-157, TB-500) are intentionally excluded from this catalog.
"""

PEPTIDE_INTERVENTIONS: list[dict] = [
    {
        "name": "Semaglutide",
        "category": "peptide",
        "description": "GLP-1 receptor agonist peptide approved for type 2 diabetes and chronic weight management.",
        "mechanism": "Activates GLP-1 receptors, enhancing incretin signaling, slowing gastric emptying, and reducing glucagon.",
        "is_regulated": True,
        "regulation_note": "Prescription-only GLP-1 receptor agonist; requires physician supervision.",
        "compounds": [{"name": "Semaglutide", "primary_target": "GLP-1 receptor", "role": "active peptide", "pubchem_cid": None}],
        "safety_flags": [
            {"condition": "pregnancy", "severity": "contraindication", "note": "Insufficient safety data; avoid in pregnancy."},
            {"condition": "medullary_thyroid_cancer_history", "severity": "contraindication",
             "note": "GLP-1 RAs carry a boxed warning for personal/family history of MTC or MEN2."},
        ],
        "drug_interactions": [
            {"drug_name": "Insulin/antidiabetics", "severity": "moderate",
             "mechanism": "Additive glucose-lowering effect.", "note": "Monitor for hypoglycemia."},
        ],
    },
    {
        "name": "Tirzepatide",
        "category": "peptide",
        "description": "Dual GIP/GLP-1 receptor agonist peptide approved for type 2 diabetes and obesity.",
        "mechanism": "Co-activates GIP and GLP-1 receptors, amplifying incretin-mediated glucose and appetite regulation.",
        "is_regulated": True,
        "regulation_note": "Prescription-only dual incretin agonist; requires physician supervision.",
        "compounds": [{"name": "Tirzepatide", "primary_target": "GIP/GLP-1 receptors", "role": "active peptide", "pubchem_cid": None}],
        "safety_flags": [
            {"condition": "pregnancy", "severity": "contraindication", "note": "Insufficient safety data; avoid in pregnancy."},
        ],
        "drug_interactions": [
            {"drug_name": "Insulin/antidiabetics", "severity": "moderate",
             "mechanism": "Additive glucose-lowering effect.", "note": "Monitor for hypoglycemia."},
        ],
    },
    {
        "name": "Liraglutide",
        "category": "peptide",
        "description": "GLP-1 receptor agonist peptide with established cardiovascular outcome trial data.",
        "mechanism": "GLP-1 receptor activation improving glycemic control and satiety signaling.",
        "is_regulated": True,
        "regulation_note": "Prescription-only GLP-1 receptor agonist; requires physician supervision.",
        "compounds": [{"name": "Liraglutide", "primary_target": "GLP-1 receptor", "role": "active peptide", "pubchem_cid": None}],
        "safety_flags": [],
        "drug_interactions": [
            {"drug_name": "Insulin/antidiabetics", "severity": "moderate",
             "mechanism": "Additive glucose-lowering effect.", "note": "Monitor for hypoglycemia."},
        ],
    },
    {
        "name": "Exenatide",
        "category": "peptide",
        "description": "First-in-class GLP-1 receptor agonist peptide derived from exendin-4.",
        "mechanism": "GLP-1 receptor agonism enhancing glucose-dependent insulin secretion.",
        "is_regulated": True,
        "regulation_note": "Prescription-only GLP-1 receptor agonist.",
        "compounds": [{"name": "Exenatide", "primary_target": "GLP-1 receptor", "role": "active peptide", "pubchem_cid": None}],
        "safety_flags": [],
        "drug_interactions": [
            {"drug_name": "Insulin/antidiabetics", "severity": "moderate",
             "mechanism": "Additive glucose-lowering effect.", "note": "Monitor for hypoglycemia."},
        ],
    },
    {
        "name": "Dulaglutide",
        "category": "peptide",
        "description": "Long-acting GLP-1 receptor agonist peptide for type 2 diabetes.",
        "mechanism": "Sustained GLP-1 receptor activation reducing HbA1c and cardiovascular risk in trials.",
        "is_regulated": True,
        "regulation_note": "Prescription-only GLP-1 receptor agonist.",
        "compounds": [{"name": "Dulaglutide", "primary_target": "GLP-1 receptor", "role": "active peptide", "pubchem_cid": None}],
        "safety_flags": [],
        "drug_interactions": [],
    },
    {
        "name": "Tesamorelin",
        "category": "peptide",
        "description": "GHRH analog peptide FDA-approved for HIV-associated lipodystrophy.",
        "mechanism": "Stimulates pituitary GH release via GHRH receptor, altering visceral adipose distribution.",
        "is_regulated": True,
        "regulation_note": "Prescription-only GHRH analog; indicated for specific lipodystrophy populations.",
        "compounds": [{"name": "Tesamorelin", "primary_target": "GHRH receptor", "role": "active peptide", "pubchem_cid": None}],
        "safety_flags": [],
        "drug_interactions": [],
    },
    {
        "name": "Bremelanotide",
        "category": "peptide",
        "description": "Melanocortin receptor agonist peptide (PT-141) FDA-approved for hypoactive sexual desire disorder.",
        "mechanism": "MC3R/MC4R agonism modulating central sexual desire pathways.",
        "is_regulated": True,
        "regulation_note": "Prescription-only melanocortin agonist.",
        "compounds": [{"name": "Bremelanotide", "primary_target": "MC3R/MC4R", "role": "active peptide", "pubchem_cid": None}],
        "safety_flags": [
            {"condition": "hypertension", "severity": "caution", "note": "Can cause transient blood pressure increases."},
        ],
        "drug_interactions": [],
    },
    {
        "name": "Thymosin Alpha-1",
        "category": "peptide",
        "description": "Immunomodulatory peptide studied in clinical trials for viral hepatitis and immune support.",
        "mechanism": "Enhances T-cell maturation and dendritic cell function; modulates innate immune signaling.",
        "is_regulated": False,
        "compounds": [{"name": "Thymosin Alpha-1", "primary_target": "TLR9 / immune modulation", "role": "active peptide", "pubchem_cid": None}],
        "safety_flags": [],
        "drug_interactions": [
            {"drug_name": "Immunosuppressants", "severity": "moderate",
             "mechanism": "Immune-stimulating activity may counteract immunosuppression.", "note": None},
        ],
    },
    {
        "name": "Collagen Peptides",
        "category": "peptide",
        "description": "Hydrolyzed collagen peptide supplement studied in RCTs for joint comfort and skin elasticity.",
        "mechanism": "Provides collagen-derived amino acid peptides that may support extracellular matrix turnover.",
        "is_regulated": False,
        "compounds": [{"name": "Collagen Peptides", "primary_target": "Extracellular matrix", "role": "bioactive peptide mix", "pubchem_cid": None}],
        "safety_flags": [],
        "drug_interactions": [],
    },
    {
        "name": "AOD-9604",
        "category": "peptide",
        "description": "HGH fragment peptide (176-191) studied in clinical trials for obesity and metabolic endpoints.",
        "mechanism": "Lipolytic fragment of growth hormone without full GH proliferative signaling.",
        "is_regulated": False,
        "compounds": [{"name": "AOD-9604", "primary_target": "GH receptor pathway (fragment)", "role": "active peptide", "pubchem_cid": None}],
        "safety_flags": [],
        "drug_interactions": [],
    },
    {
        "name": "BPC-157",
        "category": "peptide",
        "description": "Pentadecapeptide derived from gastric juice protein BPC; investigational in animal models.",
        "mechanism": "Studied for GI mucosal healing and tendon repair in preclinical models; human RCT data limited.",
        "is_regulated": True,
        "regulation_note": (
            "Not FDA-approved for human therapeutic use; prohibited in regulated sport (WADA). "
            "Surfaced for evidence context only."
        ),
        "methodology_spec": (
            "Investigational protocols in animal literature use subcutaneous or oral micro-doses; "
            "no validated human clinical protocol — clinician supervision required for any use."
        ),
        "compounds": [{"name": "BPC-157", "primary_target": "GI mucosa / tissue repair", "role": "active peptide", "pubchem_cid": None}],
        "safety_flags": [{"condition": "pregnancy", "severity": "contraindication", "note": "No human safety data; avoid."}],
        "drug_interactions": [],
    },
    {
        "name": "TB-500",
        "category": "peptide",
        "description": "Synthetic fragment of thymosin beta-4 (Ac-SDKP-related); investigational regenerative peptide.",
        "mechanism": "Actin-binding peptide studied for wound healing and tissue recovery in preclinical models.",
        "is_regulated": True,
        "regulation_note": (
            "Not FDA-approved for human therapeutic use; prohibited in regulated sport (WADA). "
            "Surfaced for evidence context only."
        ),
        "methodology_spec": (
            "Preclinical studies explore subcutaneous dosing cycles; "
            "no peer-reviewed human RCT establishes a safe clinical protocol."
        ),
        "compounds": [{"name": "Thymosin Beta-4 Fragment", "primary_target": "Actin cytoskeleton / tissue repair", "role": "active peptide", "pubchem_cid": None}],
        "safety_flags": [{"condition": "pregnancy", "severity": "contraindication", "note": "No human safety data; avoid."}],
        "drug_interactions": [],
    },
]

PEPTIDE_EVIDENCE_CLAIMS: list[dict] = [
    {"intervention_name": "Semaglutide", "biomarker_name": "HbA1c", "pathway_code": "GLP1_INCRETINS",
     "effect": "decreases", "evidence_level": "high", "pmid": "33567185",
     "summary": "STEP trial program demonstrated semaglutide reduced body weight and improved metabolic markers."},
    {"intervention_name": "Semaglutide", "biomarker_name": "Glucose", "pathway_code": "INSULIN_PI3K_AKT",
     "effect": "decreases", "evidence_level": "high", "pmid": "33567185",
     "summary": "SUSTAIN trials showed semaglutide lowered fasting glucose and HbA1c vs comparators."},
    {"intervention_name": "Tirzepatide", "biomarker_name": "HbA1c", "pathway_code": "GLP1_INCRETINS",
     "effect": "decreases", "evidence_level": "high", "pmid": "42296968",
     "summary": "SURPASS trials demonstrated tirzepatide's superior HbA1c reduction in type 2 diabetes."},
    {"intervention_name": "Tirzepatide", "biomarker_name": "Glucose", "pathway_code": "INSULIN_PI3K_AKT",
     "effect": "decreases", "evidence_level": "high", "pmid": "42184419",
     "summary": "SURMOUNT-1 trial reported significant weight loss and glycemic improvements with tirzepatide."},
    {"intervention_name": "Liraglutide", "biomarker_name": "HbA1c", "pathway_code": "GLP1_INCRETINS",
     "effect": "decreases", "evidence_level": "high", "pmid": "27295427",
     "summary": "LEADER trial established liraglutide's cardiovascular and glycemic outcome benefits."},
    {"intervention_name": "Exenatide", "biomarker_name": "HbA1c", "pathway_code": "GLP1_INCRETINS",
     "effect": "decreases", "evidence_level": "high", "pmid": "42290292",
     "summary": "Pivotal exenatide trials demonstrated HbA1c reduction in type 2 diabetes."},
    {"intervention_name": "Dulaglutide", "biomarker_name": "HbA1c", "pathway_code": "GLP1_INCRETINS",
     "effect": "decreases", "evidence_level": "high", "pmid": "41988866",
     "summary": "REWIND trial showed dulaglutide reduced major adverse cardiovascular events and HbA1c."},
    {"intervention_name": "Tesamorelin", "biomarker_name": None, "pathway_code": "HEPATIC_LIPID",
     "effect": "decreases", "evidence_level": "moderate", "pmid": "41545261",
     "summary": "Clinical trials in HIV lipodystrophy showed tesamorelin reduced visceral adipose tissue."},
    {"intervention_name": "Bremelanotide", "biomarker_name": None, "pathway_code": "HPA_AXIS",
     "effect": "increases", "evidence_level": "moderate", "pmid": "39793696",
     "summary": "Phase 3 trials supported bremelanotide efficacy for hypoactive sexual desire disorder."},
    {"intervention_name": "Thymosin Alpha-1", "biomarker_name": None, "pathway_code": "NF_KB",
     "effect": "decreases", "evidence_level": "moderate", "pmid": "41887933",
     "summary": "Clinical studies in chronic hepatitis B reported immune and virologic improvements with thymosin alpha-1."},
    {"intervention_name": "Collagen Peptides", "biomarker_name": None, "pathway_code": "NF_KB",
     "effect": "decreases", "evidence_level": "moderate", "pmid": "40977985",
     "summary": "RCT evidence for collagen peptide supplementation improving joint pain and function."},
    {"intervention_name": "AOD-9604", "biomarker_name": "Glucose", "pathway_code": "AMPK",
     "effect": "decreases", "evidence_level": "low", "pmid": "15134286",
     "summary": "Clinical trial data reported metabolic effects of AOD-9604 in obesity populations."},
    {"intervention_name": "BPC-157", "biomarker_name": None, "pathway_code": "GI_MUCOSAL_BARRIER",
     "effect": "increases", "evidence_level": "preclinical", "pmid": "40759852",
     "summary": "Animal studies report GI mucosal protective effects of BPC-157; human RCT data lacking."},
    {"intervention_name": "TB-500", "biomarker_name": None, "pathway_code": "GI_MUCOSAL_BARRIER",
     "effect": "increases", "evidence_level": "preclinical", "pmid": "38409346",
     "summary": "Thymosin beta-4 fragments studied for tissue repair in preclinical models; not validated in human RCTs."},
]
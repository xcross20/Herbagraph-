"""Common clinical conditions library for patient profile matrix UI.

Stored on the profile as human-readable labels (and optional free-text "Other").
``safety_keys`` map each entry onto Safety Engine / condition-lane catalogs.
"""

from __future__ import annotations

# Each entry: key, label, category, optional aliases, safety_keys (condition_catalog / lanes)
COMMON_CONDITIONS: list[dict] = [
    # ── Cardiovascular ──────────────────────────────────────────────
    {"key": "hypertension", "label": "Hypertension", "category": "Cardiovascular",
     "aliases": ["high blood pressure", "htn"], "safety_keys": ["hypertension"]},
    {"key": "coronary_artery_disease", "label": "Coronary artery disease", "category": "Cardiovascular",
     "aliases": ["cad", "coronary disease", "heart disease"], "safety_keys": []},
    {"key": "heart_failure", "label": "Heart failure", "category": "Cardiovascular",
     "aliases": ["chf", "congestive heart failure", "hfrEF", "hfpef"], "safety_keys": []},
    {"key": "atrial_fibrillation", "label": "Atrial fibrillation", "category": "Cardiovascular",
     "aliases": ["afib", "a-fib"], "safety_keys": ["bleeding_disorder"]},
    {"key": "arrhythmia", "label": "Arrhythmia (other)", "category": "Cardiovascular",
     "aliases": ["dysrhythmia"], "safety_keys": []},
    {"key": "hyperlipidemia", "label": "Hyperlipidemia / high cholesterol", "category": "Cardiovascular",
     "aliases": ["high cholesterol", "dyslipidemia", "hypercholesterolemia"], "safety_keys": []},
    {"key": "peripheral_artery_disease", "label": "Peripheral artery disease", "category": "Cardiovascular",
     "aliases": ["pad", "pvd"], "safety_keys": []},
    {"key": "stroke_tia", "label": "Stroke / TIA history", "category": "Cardiovascular",
     "aliases": ["cva", "tia", "stroke"], "safety_keys": ["bleeding_disorder"]},
    {"key": "deep_vein_thrombosis", "label": "DVT / PE history", "category": "Cardiovascular",
     "aliases": ["dvt", "pulmonary embolism", "pe", "venous thromboembolism"], "safety_keys": ["bleeding_disorder"]},
    {"key": "valvular_heart_disease", "label": "Valvular heart disease", "category": "Cardiovascular",
     "aliases": ["valve disease", "aortic stenosis", "mitral regurgitation"], "safety_keys": []},

    # ── Metabolic / Endocrine ───────────────────────────────────────
    {"key": "type_1_diabetes", "label": "Type 1 diabetes", "category": "Metabolic & endocrine",
     "aliases": ["t1dm", "insulin dependent diabetes"], "safety_keys": ["diabetes"]},
    {"key": "type_2_diabetes", "label": "Type 2 diabetes", "category": "Metabolic & endocrine",
     "aliases": ["t2dm", "niddm", "diabetes mellitus type 2"], "safety_keys": ["diabetes"]},
    {"key": "prediabetes", "label": "Prediabetes", "category": "Metabolic & endocrine",
     "aliases": ["impaired fasting glucose", "impaired glucose tolerance"], "safety_keys": ["diabetes"]},
    {"key": "metabolic_syndrome", "label": "Metabolic syndrome", "category": "Metabolic & endocrine",
     "aliases": [], "safety_keys": ["diabetes", "hypertension"]},
    {"key": "obesity", "label": "Obesity", "category": "Metabolic & endocrine",
     "aliases": ["bmi obesity"], "safety_keys": []},
    {"key": "hypothyroidism", "label": "Hypothyroidism", "category": "Metabolic & endocrine",
     "aliases": ["underactive thyroid", "hashimoto"], "safety_keys": ["thyroid_disease", "autoimmune_disease"]},
    {"key": "hyperthyroidism", "label": "Hyperthyroidism", "category": "Metabolic & endocrine",
     "aliases": ["overactive thyroid", "graves"], "safety_keys": ["thyroid_disease", "autoimmune_disease"]},
    {"key": "pcos", "label": "PCOS", "category": "Metabolic & endocrine",
     "aliases": ["polycystic ovary", "polycystic ovarian"], "safety_keys": []},
    {"key": "adrenal_insufficiency", "label": "Adrenal insufficiency", "category": "Metabolic & endocrine",
     "aliases": ["addison", "adrenal failure"], "safety_keys": []},
    {"key": "cushings", "label": "Cushing syndrome", "category": "Metabolic & endocrine",
     "aliases": ["cushing"], "safety_keys": []},
    {"key": "gout", "label": "Gout / hyperuricemia", "category": "Metabolic & endocrine",
     "aliases": ["hyperuricemia"], "safety_keys": []},
    {"key": "osteoporosis", "label": "Osteoporosis / osteopenia", "category": "Metabolic & endocrine",
     "aliases": ["osteopenia", "low bone density"], "safety_keys": []},
    {"key": "vitamin_d_deficiency", "label": "Vitamin D deficiency (known)", "category": "Metabolic & endocrine",
     "aliases": [], "safety_keys": []},
    {"key": "iron_deficiency", "label": "Iron deficiency / anemia (known)", "category": "Metabolic & endocrine",
     "aliases": ["iron deficiency anemia", "ida"], "safety_keys": []},

    # ── Kidney & liver ──────────────────────────────────────────────
    {"key": "ckd", "label": "Chronic kidney disease", "category": "Kidney & liver",
     "aliases": ["ckd", "chronic renal failure", "renal insufficiency"], "safety_keys": ["kidney_disease"]},
    {"key": "aki_history", "label": "Acute kidney injury history", "category": "Kidney & liver",
     "aliases": ["aki"], "safety_keys": ["kidney_disease"]},
    {"key": "kidney_stones", "label": "Kidney stones", "category": "Kidney & liver",
     "aliases": ["nephrolithiasis", "urolithiasis"], "safety_keys": []},
    {"key": "nafld", "label": "NAFLD / fatty liver", "category": "Kidney & liver",
     "aliases": ["fatty liver", "nash", "masld"], "safety_keys": ["liver_disease"]},
    {"key": "hepatitis_b", "label": "Hepatitis B", "category": "Kidney & liver",
     "aliases": ["hbv"], "safety_keys": ["liver_disease"]},
    {"key": "hepatitis_c", "label": "Hepatitis C", "category": "Kidney & liver",
     "aliases": ["hcv"], "safety_keys": ["liver_disease"]},
    {"key": "cirrhosis", "label": "Cirrhosis", "category": "Kidney & liver",
     "aliases": [], "safety_keys": ["liver_disease"]},
    {"key": "liver_disease", "label": "Liver disease (other)", "category": "Kidney & liver",
     "aliases": ["hepatic disease", "chronic liver disease"], "safety_keys": ["liver_disease"]},
    {"key": "gallstones", "label": "Gallstones / gallbladder disease", "category": "Kidney & liver",
     "aliases": ["cholelithiasis", "cholecystitis"], "safety_keys": []},

    # ── Gastrointestinal ────────────────────────────────────────────
    {"key": "gerd", "label": "GERD / reflux", "category": "Gastrointestinal",
     "aliases": ["acid reflux", "heartburn", "gerd"], "safety_keys": []},
    {"key": "peptic_ulcer", "label": "Peptic ulcer disease", "category": "Gastrointestinal",
     "aliases": ["gastric ulcer", "duodenal ulcer"], "safety_keys": ["bleeding_disorder"]},
    {"key": "ibs", "label": "IBS", "category": "Gastrointestinal",
     "aliases": ["irritable bowel"], "safety_keys": []},
    {"key": "ibd_crohn", "label": "Crohn's disease", "category": "Gastrointestinal",
     "aliases": ["crohn"], "safety_keys": ["autoimmune_disease"]},
    {"key": "ibd_uc", "label": "Ulcerative colitis", "category": "Gastrointestinal",
     "aliases": ["uc", "ulcerative colitis"], "safety_keys": ["autoimmune_disease"]},
    {"key": "celiac", "label": "Celiac disease", "category": "Gastrointestinal",
     "aliases": ["coeliac", "gluten enteropathy"], "safety_keys": ["autoimmune_disease"]},
    {"key": "diverticulitis", "label": "Diverticulitis / diverticulosis", "category": "Gastrointestinal",
     "aliases": ["diverticular disease"], "safety_keys": []},
    {"key": "constipation_chronic", "label": "Chronic constipation", "category": "Gastrointestinal",
     "aliases": [], "safety_keys": []},
    {"key": "pancreatitis_history", "label": "Pancreatitis history", "category": "Gastrointestinal",
     "aliases": [], "safety_keys": []},
    {"key": "h_pylori_history", "label": "H. pylori history", "category": "Gastrointestinal",
     "aliases": ["helicobacter"], "safety_keys": []},

    # ── Autoimmune / rheumatology ───────────────────────────────────
    {"key": "rheumatoid_arthritis", "label": "Rheumatoid arthritis", "category": "Autoimmune & rheumatology",
     "aliases": ["ra"], "safety_keys": ["autoimmune_disease"]},
    {"key": "osteoarthritis", "label": "Osteoarthritis", "category": "Autoimmune & rheumatology",
     "aliases": ["oa", "degenerative joint"], "safety_keys": []},
    {"key": "lupus", "label": "Lupus (SLE)", "category": "Autoimmune & rheumatology",
     "aliases": ["sle", "systemic lupus"], "safety_keys": ["autoimmune_disease"]},
    {"key": "sjogren", "label": "Sjögren's syndrome", "category": "Autoimmune & rheumatology",
     "aliases": ["sjogren"], "safety_keys": ["autoimmune_disease"]},
    {"key": "psoriasis", "label": "Psoriasis / psoriatic arthritis", "category": "Autoimmune & rheumatology",
     "aliases": ["psoriatic"], "safety_keys": ["autoimmune_disease"]},
    {"key": "ankylosing_spondylitis", "label": "Ankylosing spondylitis", "category": "Autoimmune & rheumatology",
     "aliases": ["axial spondyloarthritis"], "safety_keys": ["autoimmune_disease"]},
    {"key": "multiple_sclerosis", "label": "Multiple sclerosis", "category": "Autoimmune & rheumatology",
     "aliases": ["ms"], "safety_keys": ["autoimmune_disease"]},
    {"key": "hashimoto_thyroiditis", "label": "Hashimoto's thyroiditis", "category": "Autoimmune & rheumatology",
     "aliases": ["hashimoto"], "safety_keys": ["thyroid_disease", "autoimmune_disease"]},
    {"key": "fibromyalgia", "label": "Fibromyalgia", "category": "Autoimmune & rheumatology",
     "aliases": [], "safety_keys": []},
    {"key": "chronic_pain", "label": "Chronic pain syndrome", "category": "Autoimmune & rheumatology",
     "aliases": [], "safety_keys": []},

    # ── Respiratory ─────────────────────────────────────────────────
    {"key": "asthma", "label": "Asthma", "category": "Respiratory",
     "aliases": [], "safety_keys": []},
    {"key": "copd", "label": "COPD", "category": "Respiratory",
     "aliases": ["emphysema", "chronic bronchitis"], "safety_keys": []},
    {"key": "sleep_apnea", "label": "Sleep apnea", "category": "Respiratory",
     "aliases": ["osa", "obstructive sleep apnea"], "safety_keys": []},
    {"key": "allergic_rhinitis", "label": "Allergic rhinitis / allergies", "category": "Respiratory",
     "aliases": ["hay fever", "seasonal allergies"], "safety_keys": []},
    {"key": "chronic_sinusitis", "label": "Chronic sinusitis", "category": "Respiratory",
     "aliases": [], "safety_keys": []},
    {"key": "interstitial_lung", "label": "Interstitial lung disease", "category": "Respiratory",
     "aliases": ["ild", "pulmonary fibrosis"], "safety_keys": []},

    # ── Neuro / psych ───────────────────────────────────────────────
    {"key": "migraine", "label": "Migraine", "category": "Neurologic & mental health",
     "aliases": [], "safety_keys": []},
    {"key": "epilepsy", "label": "Epilepsy / seizure disorder", "category": "Neurologic & mental health",
     "aliases": ["seizure disorder"], "safety_keys": []},
    {"key": "parkinson", "label": "Parkinson's disease", "category": "Neurologic & mental health",
     "aliases": ["parkinson"], "safety_keys": []},
    {"key": "neuropathy", "label": "Peripheral neuropathy", "category": "Neurologic & mental health",
     "aliases": ["diabetic neuropathy"], "safety_keys": []},
    {"key": "depression", "label": "Depression", "category": "Neurologic & mental health",
     "aliases": ["mdd", "major depression"], "safety_keys": []},
    {"key": "anxiety", "label": "Anxiety disorder", "category": "Neurologic & mental health",
     "aliases": ["gad", "panic disorder"], "safety_keys": []},
    {"key": "bipolar", "label": "Bipolar disorder", "category": "Neurologic & mental health",
     "aliases": [], "safety_keys": []},
    {"key": "adhd", "label": "ADHD", "category": "Neurologic & mental health",
     "aliases": ["attention deficit"], "safety_keys": []},
    {"key": "insomnia", "label": "Insomnia / sleep disorder", "category": "Neurologic & mental health",
     "aliases": [], "safety_keys": []},
    {"key": "cognitive_impairment", "label": "Mild cognitive impairment / dementia", "category": "Neurologic & mental health",
     "aliases": ["alzheimer", "dementia", "mci"], "safety_keys": []},

    # ── Women's / reproductive ──────────────────────────────────────
    {"key": "pregnancy", "label": "Currently pregnant", "category": "Women's health & reproductive",
     "aliases": ["pregnant", "gestation"], "safety_keys": ["pregnancy"]},
    {"key": "breastfeeding", "label": "Currently breastfeeding", "category": "Women's health & reproductive",
     "aliases": ["lactating", "nursing"], "safety_keys": ["breastfeeding"]},
    {"key": "menopause", "label": "Menopause / perimenopause", "category": "Women's health & reproductive",
     "aliases": ["perimenopause", "postmenopausal"], "safety_keys": []},
    {"key": "endometriosis", "label": "Endometriosis", "category": "Women's health & reproductive",
     "aliases": [], "safety_keys": []},
    {"key": "uterine_fibroids", "label": "Uterine fibroids", "category": "Women's health & reproductive",
     "aliases": ["fibroids"], "safety_keys": []},
    {"key": "infertility", "label": "Infertility / fertility treatment", "category": "Women's health & reproductive",
     "aliases": ["ivf"], "safety_keys": []},
    {"key": "pms_pmdd", "label": "PMS / PMDD", "category": "Women's health & reproductive",
     "aliases": ["pmdd"], "safety_keys": []},

    # ── Heme / oncology / transplant ────────────────────────────────
    {"key": "anemia_chronic", "label": "Chronic anemia", "category": "Blood, cancer & transplant",
     "aliases": [], "safety_keys": []},
    {"key": "bleeding_disorder", "label": "Bleeding disorder", "category": "Blood, cancer & transplant",
     "aliases": ["hemophilia", "von willebrand", "coagulopathy"], "safety_keys": ["bleeding_disorder"]},
    {"key": "thrombophilia", "label": "Clotting disorder / thrombophilia", "category": "Blood, cancer & transplant",
     "aliases": ["factor v leiden", "antiphospholipid"], "safety_keys": ["bleeding_disorder"]},
    {"key": "cancer_history", "label": "Cancer (active or history)", "category": "Blood, cancer & transplant",
     "aliases": ["malignancy", "oncology"], "safety_keys": []},
    {"key": "chemotherapy", "label": "Recent/ongoing chemotherapy", "category": "Blood, cancer & transplant",
     "aliases": ["chemo"], "safety_keys": []},
    {"key": "organ_transplant", "label": "Organ transplant recipient", "category": "Blood, cancer & transplant",
     "aliases": ["transplant"], "safety_keys": ["organ_transplant"]},
    {"key": "immunosuppression", "label": "Immunosuppression (non-transplant)", "category": "Blood, cancer & transplant",
     "aliases": ["immunocompromised"], "safety_keys": ["organ_transplant"]},

    # ── Skin / ENT / other common ───────────────────────────────────
    {"key": "eczema", "label": "Eczema / atopic dermatitis", "category": "Skin & other",
     "aliases": ["atopic dermatitis"], "safety_keys": []},
    {"key": "rosacea", "label": "Rosacea", "category": "Skin & other",
     "aliases": [], "safety_keys": []},
    {"key": "chronic_urticaria", "label": "Chronic urticaria", "category": "Skin & other",
     "aliases": ["hives"], "safety_keys": []},
    {"key": "glaucoma", "label": "Glaucoma", "category": "Skin & other",
     "aliases": [], "safety_keys": []},
    {"key": "cataracts", "label": "Cataracts", "category": "Skin & other",
     "aliases": [], "safety_keys": []},
    {"key": "hearing_loss", "label": "Hearing loss", "category": "Skin & other",
     "aliases": [], "safety_keys": []},
    {"key": "chronic_fatigue", "label": "Chronic fatigue / ME-CFS", "category": "Skin & other",
     "aliases": ["me/cfs", "cfs"], "safety_keys": []},
    {"key": "long_covid", "label": "Long COVID / post-viral syndrome", "category": "Skin & other",
     "aliases": ["long covid", "pasc"], "safety_keys": []},
    {"key": "substance_use", "label": "Substance use disorder history", "category": "Skin & other",
     "aliases": ["alcohol use disorder", "oud", "aud"], "safety_keys": ["liver_disease"]},
    {"key": "tobacco_use", "label": "Current tobacco use", "category": "Skin & other",
     "aliases": ["smoker", "smoking"], "safety_keys": []},
    {"key": "bariatric_surgery", "label": "Bariatric surgery history", "category": "Skin & other",
     "aliases": ["gastric bypass", "sleeve gastrectomy"], "safety_keys": []},
]


def list_common_conditions() -> list[dict]:
    """API-ready list (stable order as defined)."""
    return [
        {
            "key": e["key"],
            "label": e["label"],
            "category": e["category"],
            "aliases": list(e.get("aliases") or []),
            "safety_keys": list(e.get("safety_keys") or []),
        }
        for e in COMMON_CONDITIONS
    ]


def conditions_by_category() -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for e in list_common_conditions():
        grouped.setdefault(e["category"], []).append(e)
    return grouped


def match_common_condition_keys(known_conditions: list[str]) -> set[str]:
    """Return library keys whose label/alias/key appear in free-text condition list.

    Prefers exact matches (matrix labels). Allows longer substring matches for free text.
    """
    if not known_conditions:
        return set()
    texts = [str(c).strip().lower() for c in known_conditions if str(c).strip()]
    if not texts:
        return set()
    matched: set[str] = set()
    for e in COMMON_CONDITIONS:
        key = e["key"]
        label = e["label"].lower()
        aliases = {a.lower() for a in (e.get("aliases") or [])}
        key_phrase = key.replace("_", " ")
        exact = {key, label, key_phrase, *aliases}
        for t in texts:
            if t in exact:
                matched.add(key)
                break
            # Free-text: only longer queries use containment (avoids "ms" ⊂ "pms pmdd")
            if len(t) < 5:
                continue
            for token in (label, *aliases, key_phrase):
                if len(token) < 5:
                    continue
                if token in t or t in token:
                    matched.add(key)
                    break
            else:
                continue
            break
    return matched


def safety_keys_for_known_conditions(known_conditions: list[str]) -> set[str]:
    """Map free-text / matrix labels onto safety catalog keys."""
    keys: set[str] = set()
    for ck in match_common_condition_keys(known_conditions):
        for e in COMMON_CONDITIONS:
            if e["key"] == ck:
                keys.update(e.get("safety_keys") or [])
                break
    return keys


def other_conditions_not_in_library(known_conditions: list[str]) -> list[str]:
    """Free-text entries that do not match any library condition."""
    if not known_conditions:
        return []
    matched_keys = match_common_condition_keys(known_conditions)
    matched_labels = set()
    for e in COMMON_CONDITIONS:
        if e["key"] in matched_keys:
            matched_labels.add(e["label"].lower())
            matched_labels.add(e["key"])
            matched_labels.update(a.lower() for a in (e.get("aliases") or []))
    other: list[str] = []
    for raw in known_conditions:
        s = str(raw).strip()
        if not s:
            continue
        if s.lower() in matched_labels or s.lower().replace(" ", "_") in matched_keys:
            continue
        # if this string only matched as substring of a library item, still keep if not exact
        if s.lower() not in matched_labels:
            # re-check: if match_common includes a key only because of this string
            alone = match_common_condition_keys([s])
            if alone:
                continue
            other.append(s)
    return other

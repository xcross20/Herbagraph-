#!/usr/bin/env python3
"""Regenerate app/knowledge_graph/biomarker_catalog.py. Run from repo root."""

from __future__ import annotations

import pprint
from pathlib import Path


def _entry(
    name: str,
    cat: str,
    unit: str,
    lo: float | None,
    hi: float | None,
    aliases: list[str],
    *,
    desc: str | None = None,
    opt_lo: float | None = None,
    opt_hi: float | None = None,
    crit_lo: float | None = None,
    crit_hi: float | None = None,
    result_kind: str = "numeric",
) -> dict:
    return {
        "canonical_name": name,
        "category": cat,
        "default_unit": unit,
        "reference_low": lo,
        "reference_high": hi,
        "optimal_low": lo if opt_lo is None else opt_lo,
        "optimal_high": hi if opt_hi is None else opt_hi,
        "critical_low": crit_lo,
        "critical_high": crit_hi,
        "description": desc or f"Clinical laboratory measurement: {name}.",
        "aliases": aliases,
        "result_kind": result_kind,
    }


def _enrich_aliases(canonical: str, aliases: list[str]) -> list[str]:
    """Add common lab naming variants (parenthetical abbreviations, mean-cell wording)."""
    merged = set(aliases)
    lower = canonical.lower()

    if canonical in {"MCV", "MCH", "MCHC", "RDW"}:
        word = {
            "MCV": ("mean cell volume", "mean corpuscular volume"),
            "MCH": ("mean cell hemoglobin", "mean corpuscular hemoglobin"),
            "MCHC": ("mean cell hemoglobin concentration", "mean corpuscular hemoglobin concentration"),
            "RDW": ("red cell distribution width",),
        }[canonical]
        for phrase in word:
            merged.add(phrase)
            merged.add(f"{phrase} {canonical.lower()}")

    if canonical == "WBC":
        merged.update({"white blood cell", "white blood cell wbc", "white blood cell count"})
    if canonical == "RBC":
        merged.update({"red blood cell", "red blood cell rbc", "red blood cell count"})

    absolute_map = {
        "Absolute Neutrophils": ("neutrophil absolute", "neutrophil", "absolute neutrophil", "anc"),
        "Absolute Lymphocytes": ("lymphocyte absolute", "lymphocyte", "absolute lymphocyte", "alc"),
        "Absolute Monocytes": ("monocyte absolute", "monocyte", "absolute monocyte"),
        "Absolute Eosinophils": ("eosinophil absolute", "eosinophil", "absolute eosinophil"),
        "Absolute Basophils": ("basophil absolute", "basophil", "absolute basophil"),
    }
    if canonical in absolute_map:
        merged.update(absolute_map[canonical])

    percent_map = {
        "Neutrophils %": ("neutrophils percent", "neutrophil percent"),
        "Lymphocytes %": ("lymphocytes percent", "lymphocyte percent"),
        "Monocytes %": ("monocytes percent", "monocyte percent"),
        "Eosinophils %": ("eosinophils percent", "eosinophil percent"),
        "Basophils %": ("basophils percent", "basophil percent"),
    }
    if canonical in percent_map:
        merged.update(percent_map[canonical])

    if "vitamin d" in lower or canonical == "Vitamin D":
        merged.update({"vitamin d 25 hydroxy", "25 hydroxy vitamin d", "vit d 25 oh"})

    lipid_calc_map = {
        "ApoB": ("apolipoprotein b calc", "apo b calc", "apob calc"),
        "LDL": ("ldl chol calc", "ldl cholesterol calc"),
        "HDL": ("hdl chol calc", "hdl cholesterol calc"),
    }
    if canonical in lipid_calc_map:
        merged.update(lipid_calc_map[canonical])

    nutrient_map = {
        "B12": ("vitamin b12", "vitamin b12 serum", "cobalamin", "b 12"),
        "Folate": ("folic acid", "folate serum", "folic acid serum"),
        "Ferritin": ("ferritin serum", "iron ferritin"),
        "Iron": ("iron serum", "serum iron"),
        "Homocysteine": ("plasma homocysteine", "homocysteine plasma"),
        "Zinc": ("zinc serum", "serum zinc"),
    }
    if canonical in nutrient_map:
        merged.update(nutrient_map[canonical])

    merged.add(lower)
    return sorted(merged)


def _build_entries() -> list[dict]:
    entries: list[dict] = []
    seen: set[str] = set()

    def add(
        name: str,
        cat: str,
        unit: str,
        lo: float | None,
        hi: float | None,
        *aliases: str,
        opt_lo: float | None = None,
        opt_hi: float | None = None,
        crit_lo: float | None = None,
        crit_hi: float | None = None,
        desc: str | None = None,
        result_kind: str = "numeric",
    ) -> None:
        if name in seen:
            return
        seen.add(name)
        enriched = _enrich_aliases(name, list(aliases))
        entries.append(
            _entry(name, cat, unit, lo, hi, enriched, desc=desc,
                   opt_lo=opt_lo, opt_hi=opt_hi, crit_lo=crit_lo, crit_hi=crit_hi,
                   result_kind=result_kind)
        )

    def add_qualitative(name: str, cat: str, *aliases: str, desc: str | None = None) -> None:
        """Qualitative test: 0 = expected negative, 1 = positive/detected."""
        add(
            name, cat, "qualitative", 0, 0, *aliases,
            desc=desc or f"Qualitative laboratory test: {name}.",
            result_kind="qualitative",
        )

    def add_culture(name: str, *aliases: str, desc: str | None = None) -> None:
        """Culture: 0 = no growth, 1 = organism isolated."""
        add(
            name, "microbiology", "culture", 0, 0, *aliases,
            desc=desc or f"Microbiological culture: {name}.",
            result_kind="culture",
        )

    def add_genotype(name: str, *aliases: str, desc: str | None = None) -> None:
        """Pharmacogenomic genotype result."""
        add(
            name, "pharmacogenomics", "genotype", 0, 0, *aliases,
            desc=desc or f"Pharmacogenomic genotype: {name}.",
            result_kind="genotype",
        )

    # Core panel (25)
    add("CRP", "inflammatory", "mg/L", 0, 3, "crp", "c reactive protein", "hs crp", "high sensitivity crp", "hscrp", opt_hi=1, crit_hi=10)
    add("Glucose", "metabolic", "mg/dL", 70, 99, "glucose", "glucose fasting", "fasting glucose", "fbg", "glucose serum", "fasting blood glucose", opt_hi=85, crit_lo=54, crit_hi=250)
    add("HbA1c", "metabolic", "%", 4, 5.6, "hba1c", "hemoglobin a1c", "a1c", "glycated hemoglobin", opt_hi=5.3, crit_hi=9)
    add("Insulin", "metabolic", "uIU/mL", 2.6, 24.9, "insulin", "fasting insulin", opt_hi=6, crit_hi=50)
    add("LDL", "lipid", "mg/dL", 0, 99, "ldl", "ldl cholesterol", "ldl c", "ldl chol calc", "cardio iq ldl cholesterol", "low density lipoprotein", opt_hi=80, crit_hi=190)
    add("HDL", "lipid", "mg/dL", 40, 100, "hdl", "hdl cholesterol", "hdl c", "cardio iq hdl cholesterol", opt_lo=60, crit_lo=20)
    add("Triglycerides", "lipid", "mg/dL", 0, 149, "triglycerides", "trig", "cardio iq triglycerides", opt_hi=100, crit_hi=500)
    add("ApoB", "lipid", "mg/dL", 40, 100, "apob", "apolipoprotein b", "apo b", opt_hi=80, crit_hi=160)
    add("Vitamin D", "hormonal", "ng/mL", 30, 100, "vitamin d", "vitamin d 25 hydroxy", "25 oh vitamin d", "vit d", opt_lo=50, opt_hi=80, crit_lo=10, crit_hi=150)
    add("Ferritin", "iron_metabolism", "ng/mL", 20, 250, "ferritin", "serum ferritin", opt_lo=50, opt_hi=150, crit_lo=10, crit_hi=500)
    add("B12", "nutritional", "pg/mL", 200, 900, "vitamin b12", "b12", "cobalamin", opt_lo=500, crit_lo=150)
    add("Folate", "nutritional", "ng/mL", 2.7, 17, "folate", "folic acid", "serum folate", opt_lo=7)
    add("TSH", "hormonal", "mIU/L", 0.4, 4.0, "tsh", "thyroid stimulating hormone", "thyrotropin", "tsh w reflex to ft4", opt_lo=0.5, opt_hi=2.5, crit_lo=0.01, crit_hi=10)
    add("ALT", "hepatic", "U/L", 7, 56, "alt", "alt sgpt", "sgpt", "alanine aminotransferase", opt_hi=25, crit_hi=200)
    add("AST", "hepatic", "U/L", 10, 40, "ast", "ast sgot", "sgot", "aspartate aminotransferase", opt_hi=25, crit_hi=200)
    add("GGT", "hepatic", "U/L", 8, 61, "ggt", "gamma glutamyl transferase", "gamma gt", opt_hi=30, crit_hi=200)
    add("Creatinine", "renal", "mg/dL", 0.6, 1.3, "creatinine", "creatinine serum", "serum creatinine", opt_lo=0.7, opt_hi=1.1, crit_lo=0.3, crit_hi=3)
    add("eGFR", "renal", "mL/min/1.73m2", 90, None, "egfr", "gfr", "estimated gfr", "estimated glomerular filtration rate", opt_hi=120, crit_lo=15)
    add("Homocysteine", "inflammatory", "umol/L", 5, 15, "homocysteine", "hcy", "homocyst e ine", opt_hi=8, crit_hi=30)
    add("Uric Acid", "metabolic", "mg/dL", 3.5, 7.2, "uric acid", "urate", opt_hi=6, crit_lo=2, crit_hi=10)
    add("Lp(a)", "lipid", "mg/dL", 0, 30, "lp a", "lipoprotein a", "lpa", opt_hi=14, crit_hi=100)
    add("Free T3", "hormonal", "pg/mL", 2.3, 4.2, "free t3", "ft3", crit_lo=1, crit_hi=6)
    add("Free T4", "hormonal", "ng/dL", 0.8, 1.8, "free t4", "ft4", crit_lo=0.4, crit_hi=3)
    add("Cortisol", "hormonal", "ug/dL", 6, 23, "cortisol", "cortisol am", "am cortisol", opt_lo=10, opt_hi=18, crit_lo=3, crit_hi=35)
    add("DHEA-S", "hormonal", "ug/dL", 65, 380, "dhea s", "dheas", opt_lo=100, opt_hi=300, crit_lo=20)

    # CMP / electrolytes
    add("BUN", "renal", "mg/dL", 7, 25, "bun", "urea nitrogen bun", "urea nitrogen", "blood urea nitrogen", opt_hi=18, crit_hi=80)
    add("Sodium", "electrolyte", "mmol/L", 135, 146, "sodium", "sodium serum", "na", crit_lo=120, crit_hi=160)
    add("Potassium", "electrolyte", "mmol/L", 3.5, 5.3, "potassium", "potassium serum", "k", crit_lo=2.5, crit_hi=6.5)
    add("Chloride", "electrolyte", "mmol/L", 98, 110, "chloride", "chloride serum", "cl")
    add("CO2", "electrolyte", "mmol/L", 20, 32, "carbon dioxide", "co2", "bicarbonate", "hco3", "total co2")
    add("Calcium", "electrolyte", "mg/dL", 8.6, 10.3, "calcium", "calcium serum", "ca", crit_lo=6, crit_hi=13)
    add("Magnesium", "electrolyte", "mg/dL", 1.7, 2.4, "magnesium", "magnesium serum", "mg", crit_lo=1, crit_hi=4)
    add("Phosphorus", "electrolyte", "mg/dL", 2.5, 4.5, "phosphorus", "phosphate", "phosphorus serum")
    add("Anion Gap", "electrolyte", "mEq/L", 3, 11, "anion gap")
    add("Osmolality", "electrolyte", "mOsm/kg", 275, 295, "osmolality", "serum osmolality")

    # Liver
    add("Albumin", "hepatic", "g/dL", 3.6, 5.1, "albumin", "albumin serum", crit_lo=2.5)
    add("Total Protein", "hepatic", "g/dL", 6.1, 8.1, "protein total", "total protein", "protein serum")
    add("Globulin", "hepatic", "g/dL", 1.9, 3.7, "globulin", "globulin calc")
    add("Bilirubin Total", "hepatic", "mg/dL", 0.2, 1.2, "bilirubin total", "total bilirubin", "bilirubin", crit_hi=15)
    add("Bilirubin Direct", "hepatic", "mg/dL", 0, 0.3, "bilirubin direct", "direct bilirubin")
    add("Bilirubin Indirect", "hepatic", "mg/dL", 0, 1.1, "bilirubin indirect", "indirect bilirubin")
    add("Alkaline Phosphatase", "hepatic", "U/L", 36, 130, "alkaline phosphatase", "alp", "alk phos", crit_hi=400)
    add("LDH", "hepatic", "U/L", 120, 246, "ldh", "lactate dehydrogenase")
    add("Ammonia", "hepatic", "umol/L", 11, 35, "ammonia", crit_hi=100)
    add("Lipase", "hepatic", "U/L", 0, 60, "lipase")
    add("Amylase", "hepatic", "U/L", 30, 110, "amylase")

    # Lipids extended
    add("Total Cholesterol", "lipid", "mg/dL", 0, 200, "cholesterol total", "total cholesterol", "cardio iq cholesterol total", opt_hi=180, crit_hi=300)
    add("Non-HDL Cholesterol", "lipid", "mg/dL", 0, 130, "non hdl cholesterol", "non hdl", opt_hi=100, crit_hi=220)
    add("VLDL", "lipid", "mg/dL", 0, 30, "vldl", "vldl cholesterol", opt_hi=20)
    add("Chol/HDL Ratio", "lipid", "ratio", 0, 5, "chol hdlc ratio", "chol hdl ratio")
    add("LDL/HDL Ratio", "lipid", "ratio", 0, 3.5, "ldl hdl ratio")
    add("ApoA1", "lipid", "mg/dL", 100, 200, "apoa1", "apolipoprotein a1", "apo a1")
    add("Lp-PLA2", "lipid", "ng/mL", 0, 200, "lp pla2")
    add("OxLDL", "lipid", "U/L", 0, 60, "oxldl", "oxidized ldl")

    # CBC
    add("WBC", "cbc", "K/uL", 3.8, 10.8, "white blood cell count", "wbc", "leukocytes", crit_lo=2, crit_hi=30)
    add("RBC", "cbc", "M/uL", 4.2, 5.8, "red blood cell count", "rbc", crit_lo=2.5, crit_hi=7)
    add("Hemoglobin", "cbc", "g/dL", 13.2, 17.1, "hemoglobin", "hgb", "hb", crit_lo=7, crit_hi=20)
    add("Hematocrit", "cbc", "%", 38.5, 50, "hematocrit", "hct", crit_lo=20, crit_hi=60)
    add("MCV", "cbc", "fL", 80, 100, "mcv", "mean corpuscular volume")
    add("MCH", "cbc", "pg", 27, 33, "mch", "mean corpuscular hemoglobin")
    add("MCHC", "cbc", "g/dL", 32, 36, "mchc")
    add("RDW", "cbc", "%", 11, 15, "rdw", "red cell distribution width")
    add("Platelet Count", "cbc", "K/uL", 140, 400, "platelet count", "platelets", "plt", crit_lo=50, crit_hi=1000)
    add("MPV", "cbc", "fL", 7.5, 12.5, "mpv", "mean platelet volume")
    add("Neutrophils %", "cbc", "%", 40, 70, "neutrophils", "neutrophils percent")
    add("Lymphocytes %", "cbc", "%", 15, 45, "lymphocytes", "lymphocytes percent")
    add("Monocytes %", "cbc", "%", 2, 10, "monocytes", "monocytes percent")
    add("Eosinophils %", "cbc", "%", 0, 6, "eosinophils", "eosinophils percent")
    add("Basophils %", "cbc", "%", 0, 2, "basophils", "basophils percent")
    add("Absolute Neutrophils", "cbc", "cells/uL", 1500, 7800, "absolute neutrophils", "anc")
    add("Absolute Lymphocytes", "cbc", "cells/uL", 850, 3900, "absolute lymphocytes", "alc")
    add("Absolute Monocytes", "cbc", "cells/uL", 200, 950, "absolute monocytes")
    add("Absolute Eosinophils", "cbc", "cells/uL", 15, 500, "absolute eosinophils")
    add("Absolute Basophils", "cbc", "cells/uL", 0, 200, "absolute basophils")
    add("Reticulocyte Count", "cbc", "%", 0.5, 2.5, "reticulocyte count", "reticulocytes")
    add("Haptoglobin", "cbc", "mg/dL", 30, 200, "haptoglobin")

    # Iron
    add("Iron", "iron_metabolism", "ug/dL", 60, 170, "iron", "iron serum", "serum iron")
    add("TIBC", "iron_metabolism", "ug/dL", 250, 450, "tibc", "total iron binding capacity")
    add("UIBC", "iron_metabolism", "ug/dL", 150, 375, "uibc")
    add("Transferrin", "iron_metabolism", "mg/dL", 200, 360, "transferrin")
    add("Transferrin Saturation", "iron_metabolism", "%", 20, 50, "transferrin saturation", "iron saturation", "tsat")
    add("Soluble Transferrin Receptor", "iron_metabolism", "mg/L", 0.8, 1.8, "soluble transferrin receptor", "stfr")
    add("Ceruloplasmin", "iron_metabolism", "mg/dL", 20, 35, "ceruloplasmin")

    # Thyroid
    add("Total T3", "hormonal", "ng/dL", 80, 200, "total t3", "t3 total", "triiodothyronine")
    add("Total T4", "hormonal", "ug/dL", 4.5, 12, "total t4", "t4 total", "thyroxine")
    add("Reverse T3", "hormonal", "ng/dL", 9, 24, "reverse t3", "rt3")
    add("TPO Antibody", "autoimmune", "IU/mL", 0, 9, "tpo antibody", "anti tpo", "tpo ab")
    add("Thyroglobulin Antibody", "autoimmune", "IU/mL", 0, 1, "thyroglobulin antibody", "anti tg")
    add("Thyroglobulin", "hormonal", "ng/mL", 0, 55, "thyroglobulin")
    add("TSH Receptor Antibody", "autoimmune", "IU/L", 0, 1.75, "tsh receptor antibody", "trab")

    # Vitamins / minerals
    add("Vitamin A", "nutritional", "ug/dL", 30, 95, "vitamin a", "retinol")
    add("Vitamin E", "nutritional", "mg/L", 5, 20, "vitamin e", "alpha tocopherol")
    add("Vitamin K", "nutritional", "ng/mL", 0.1, 2.2, "vitamin k")
    add("Vitamin B1", "nutritional", "nmol/L", 70, 180, "vitamin b1", "thiamine")
    add("Vitamin B2", "nutritional", "nmol/L", 106, 428, "vitamin b2", "riboflavin")
    add("Vitamin B6", "nutritional", "ng/mL", 5, 50, "vitamin b6", "pyridoxine")
    add("Vitamin C", "nutritional", "mg/dL", 0.4, 2, "vitamin c", "ascorbic acid")
    add("Zinc", "nutritional", "ug/dL", 60, 130, "zinc", "zinc serum")
    add("Copper", "nutritional", "ug/dL", 70, 175, "copper")
    add("Selenium", "nutritional", "ug/L", 70, 150, "selenium")
    add("Methylmalonic Acid", "nutritional", "nmol/L", 0, 370, "methylmalonic acid", "mma")
    add("Prealbumin", "nutritional", "mg/dL", 15, 36, "prealbumin", "transthyretin")

    # Hormones
    add("Testosterone Total", "hormonal", "ng/dL", 300, 1000, "testosterone total", "testosterone", "total testosterone")
    add("Testosterone Free", "hormonal", "pg/mL", 50, 210, "testosterone free", "free testosterone")
    add("Estradiol", "hormonal", "pg/mL", 10, 40, "estradiol", "e2")
    add("Progesterone", "hormonal", "ng/mL", 0.1, 20, "progesterone")
    add("LH", "hormonal", "mIU/mL", 1.5, 9.3, "lh", "luteinizing hormone")
    add("FSH", "hormonal", "mIU/mL", 1.4, 12.8, "fsh", "follicle stimulating hormone")
    add("Prolactin", "hormonal", "ng/mL", 4, 15, "prolactin")
    add("SHBG", "hormonal", "nmol/L", 10, 57, "shbg", "sex hormone binding globulin")
    add("IGF-1", "hormonal", "ng/mL", 100, 300, "igf 1", "insulin like growth factor 1")
    add("Growth Hormone", "hormonal", "ng/mL", 0, 5, "growth hormone", "gh")
    add("ACTH", "hormonal", "pg/mL", 7, 63, "acth")
    add("Aldosterone", "hormonal", "ng/dL", 2, 16, "aldosterone")
    add("Renin", "hormonal", "ng/mL/hr", 0.5, 3.3, "renin", "plasma renin activity")
    add("PTH", "hormonal", "pg/mL", 15, 65, "pth", "parathyroid hormone")
    add("Calcitonin", "hormonal", "pg/mL", 0, 10, "calcitonin")
    add("AMH", "hormonal", "ng/mL", 1, 10, "amh", "anti mullerian hormone")
    add("Leptin", "hormonal", "ng/mL", 2, 20, "leptin")
    add("Adiponectin", "hormonal", "ug/mL", 3, 30, "adiponectin")
    add("C-Peptide", "metabolic", "ng/mL", 0.8, 3.1, "c peptide", "cpeptide")
    add("Glucagon", "metabolic", "pg/mL", 50, 150, "glucagon")
    add("DHEA", "hormonal", "ng/dL", 100, 500, "dhea")
    add("DHT", "hormonal", "ng/dL", 30, 85, "dht", "dihydrotestosterone")
    add("Androstenedione", "hormonal", "ng/dL", 0.3, 3.1, "androstenedione")
    add("Estrone", "hormonal", "pg/mL", 10, 60, "estrone", "e1")
    add("Estriol", "hormonal", "ng/mL", 0, 14, "estriol", "e3")
    add("HCG", "hormonal", "mIU/mL", 0, 5, "hcg", "beta hcg")
    add("Pregnenolone", "hormonal", "ng/dL", 50, 200, "pregnenolone")

    # Inflammatory
    add("ESR", "inflammatory", "mm/hr", 0, 15, "esr", "sed rate", "erythrocyte sedimentation rate")
    add("Fibrinogen", "inflammatory", "mg/dL", 200, 400, "fibrinogen")
    add("IL-6", "inflammatory", "pg/mL", 0, 7, "il 6", "interleukin 6")
    add("TNF-alpha", "inflammatory", "pg/mL", 0, 8, "tnf alpha")
    add("NLR", "inflammatory", "ratio", 1, 3, "nlr", "neutrophil lymphocyte ratio")
    add("PLR", "inflammatory", "ratio", 50, 200, "plr", "platelet lymphocyte ratio")

    # Coagulation
    add("PT", "coagulation", "sec", 11, 13.5, "pt", "prothrombin time")
    add("INR", "coagulation", "ratio", 0.8, 1.2, "inr", crit_hi=5)
    add("PTT", "coagulation", "sec", 25, 35, "ptt", "aptt", "partial thromboplastin time")
    add("D-Dimer", "coagulation", "ug/mL", 0, 0.5, "d dimer", "ddimer")
    add("Protein C", "coagulation", "%", 70, 140, "protein c")
    add("Protein S", "coagulation", "%", 70, 140, "protein s")
    add("Antithrombin III", "coagulation", "%", 80, 120, "antithrombin iii")

    # Cardiac
    add("Troponin I", "cardiac", "ng/mL", 0, 0.04, "troponin i", "tni", crit_hi=0.5)
    add("Troponin T", "cardiac", "ng/mL", 0, 0.01, "troponin t", "tnt")
    add("BNP", "cardiac", "pg/mL", 0, 100, "bnp", crit_hi=500)
    add("NT-proBNP", "cardiac", "pg/mL", 0, 125, "nt probnp", crit_hi=1000)
    add("CK", "cardiac", "U/L", 30, 200, "ck", "creatine kinase", "cpk")
    add("CK-MB", "cardiac", "ng/mL", 0, 5, "ck mb")
    add("Myoglobin", "cardiac", "ng/mL", 0, 90, "myoglobin")

    # Renal extended
    add("Cystatin C", "renal", "mg/L", 0.5, 1.0, "cystatin c")
    add("Microalbumin", "renal", "mg/L", 0, 30, "microalbumin", "urine microalbumin")
    add("Albumin/Creatinine Ratio", "renal", "mg/g", 0, 30, "albumin creatinine ratio", "acr", "uacr")
    add("BUN/Creatinine Ratio", "renal", "ratio", 6, 22, "bun creatinine ratio", "bun cr ratio")
    add("Beta-2 Microglobulin", "renal", "mg/L", 0, 2.5, "beta 2 microglobulin", "b2m")

    # Urinalysis
    add("Urine pH", "urinalysis", "pH", 5, 8, "ph urine", "urine ph", "ph")
    add("Urine Specific Gravity", "urinalysis", "ratio", 1.001, 1.035, "specific gravity", "urine specific gravity")
    add("Urine Protein", "urinalysis", "mg/dL", 0, 10, "urine protein", "protein urine")
    add("Urine Glucose", "urinalysis", "mg/dL", 0, None, "urine glucose", "glucose urine")
    add("Urine Ketones", "urinalysis", "mg/dL", 0, None, "urine ketones", "ketones urine", "ketones")
    add("Urine Blood", "urinalysis", "", 0, None, "urine blood", "occult blood urine", "occult blood")
    add("Urine WBC", "urinalysis", "/HPF", 0, 5, "urine wbc", "wbc urine", "wbc none seen")
    add("Urine RBC", "urinalysis", "/HPF", 0, 2, "urine rbc", "rbc urine", "rbc none seen")
    add("Urine Nitrite", "urinalysis", "", 0, None, "urine nitrite", "nitrite")
    add("Urine Leukocyte Esterase", "urinalysis", "", 0, None, "leukocyte esterase")
    add("Urine Bilirubin", "urinalysis", "", 0, None, "urine bilirubin", "bilirubin urine")
    add("Urine Urobilinogen", "urinalysis", "mg/dL", 0.1, 1, "urine urobilinogen", "urobilinogen")
    add("Urine Creatinine", "urinalysis", "mg/dL", 20, 300, "urine creatinine")
    add("Urine Albumin", "urinalysis", "mg/L", 0, 30, "urine albumin")
    add("Squamous Epithelial Cells", "urinalysis", "/HPF", 0, 5, "squamous epithelial cells", "epithelial cells")
    add("Bacteria Urine", "urinalysis", "/HPF", 0, None, "bacteria urine", "bacteria none seen")
    add("Hyaline Cast", "urinalysis", "/LPF", 0, None, "hyaline cast", "casts urine")

    # Autoimmune / immunology
    add("ANA", "autoimmune", "titer", 0, None, "ana", "antinuclear antibody")
    add("RF", "autoimmune", "IU/mL", 0, 14, "rf", "rheumatoid factor")
    add("Anti-CCP", "autoimmune", "U/mL", 0, 20, "anti ccp", "ccp antibody")
    add("dsDNA Antibody", "autoimmune", "IU/mL", 0, 30, "dsdna antibody", "anti dsdna")
    add("Complement C3", "autoimmune", "mg/dL", 90, 180, "complement c3", "c3")
    add("Complement C4", "autoimmune", "mg/dL", 10, 40, "complement c4", "c4")
    add("IgA", "autoimmune", "mg/dL", 70, 400, "iga", "immunoglobulin a")
    add("IgG", "autoimmune", "mg/dL", 700, 1600, "igg", "immunoglobulin g")
    add("IgM", "autoimmune", "mg/dL", 40, 230, "igm", "immunoglobulin m")
    add("IgE", "autoimmune", "IU/mL", 0, 100, "ige", "immunoglobulin e")

    # Tumor markers
    add("PSA", "tumor_marker", "ng/mL", 0, 4, "psa", "prostate specific antigen")
    add("Free PSA", "tumor_marker", "ng/mL", 0, 4, "free psa", "psa free")
    add("CEA", "tumor_marker", "ng/mL", 0, 3, "cea", "carcinoembryonic antigen")
    add("CA-125", "tumor_marker", "U/mL", 0, 35, "ca 125", "ca125")
    add("CA 19-9", "tumor_marker", "U/mL", 0, 37, "ca 19 9", "ca199")
    add("AFP", "tumor_marker", "ng/mL", 0, 10, "afp", "alpha fetoprotein")
    add("CA 15-3", "tumor_marker", "U/mL", 0, 30, "ca 15 3", "ca153")

    # Toxicology / other
    add("Lactate", "metabolic", "mmol/L", 0.5, 2.2, "lactate", "lactic acid", crit_hi=4)
    add("Beta-Hydroxybutyrate", "metabolic", "mmol/L", 0, 0.6, "beta hydroxybutyrate", "bhb")
    add("Fructosamine", "metabolic", "umol/L", 200, 285, "fructosamine")
    add("eAG", "metabolic", "mg/dL", 68, 126, "eag", "estimated average glucose")
    add("HOMA-IR", "metabolic", "index", 0, 2.5, "homa ir", "homa index")
    add("Lead", "toxicology", "ug/dL", 0, 5, "lead", "lead blood")
    add("Mercury", "toxicology", "ug/L", 0, 10, "mercury")
    add("Arsenic", "toxicology", "ug/L", 0, 50, "arsenic")
    add("Alpha-1 Antitrypsin", "hepatic", "mg/dL", 90, 200, "alpha 1 antitrypsin", "a1at")
    add("Alpha-2 Macroglobulin", "hepatic", "mg/dL", 150, 425, "alpha 2 macroglobulin")
    add("Albumin/Globulin Ratio", "hepatic", "ratio", 1.0, 2.5, "albumin globulin ratio", "a g ratio", "albumin/globulin ratio")
    add("Color Urine", "urinalysis", "", 0, None, "color", "color urine", "urine color")

    # Infectious disease / microbiology (qualitative)
    add_qualitative(
        "H. pylori Urea Breath Test",
        "infectious_disease",
        "helicobacter pylori urea breath test",
        "helicobacter pylori",
        "h pylori urea breath test",
        "urea breath test",
        "hpylori breath test",
        desc="Breath test for active Helicobacter pylori gastric colonization.",
    )
    add_qualitative(
        "H. pylori Stool Antigen",
        "infectious_disease",
        "h pylori stool antigen",
        "helicobacter pylori stool antigen",
        desc="Stool antigen test for active H. pylori infection.",
    )
    add_qualitative(
        "H. pylori IgG Antibody",
        "infectious_disease",
        "h pylori igg",
        "helicobacter pylori igg antibody",
        desc="Serology for prior or ongoing H. pylori exposure.",
    )
    add_qualitative(
        "Hepatitis A IgM",
        "infectious_disease",
        "hepatitis a igm",
        desc="Acute hepatitis A antibody screen.",
    )
    add_qualitative(
        "Hepatitis B Surface Antigen",
        "infectious_disease",
        "hepatitis b surface antigen",
        "hbsag",
        desc="Marker of active hepatitis B infection.",
    )
    add_qualitative(
        "Hepatitis B Core Antibody IgM",
        "infectious_disease",
        "hepatitis b core antibody igm",
        "hepatitis b core antibody",
        desc="Acute hepatitis B core antibody screen.",
    )
    add_qualitative(
        "Hepatitis C Antibody",
        "infectious_disease",
        "hepatitis c antibody",
        "hcv antibody",
        desc="Hepatitis C antibody screen.",
    )
    add_qualitative(
        "HIV Ag/Ab 4th Gen",
        "infectious_disease",
        "hiv ag ab 4th gen",
        "hiv 1 2 antigen antibody fourth generation",
        "hiv 1/2 antigen/antibody",
        desc="Fourth-generation HIV antigen/antibody combination assay.",
    )
    add_qualitative(
        "Chlamydia trachomatis RNA",
        "infectious_disease",
        "chlamydia trachomatis rna",
        "chlamydia trachomatis rna tma urogenital",
        desc="Nucleic acid amplification test for Chlamydia trachomatis.",
    )
    add_qualitative(
        "Neisseria gonorrhoeae RNA",
        "infectious_disease",
        "neisseria gonorrhoeae rna",
        "neisseria gonorrhoeae rna tma urogenital",
        desc="Nucleic acid amplification test for Neisseria gonorrhoeae.",
    )
    add_qualitative(
        "RPR Syphilis Screen",
        "infectious_disease",
        "rpr dx w refl titer",
        "rpr syphilis",
        "rpr",
        desc="Rapid plasma reagin syphilis screening test.",
    )
    add_qualitative(
        "C. difficile Toxin",
        "infectious_disease",
        "c difficile toxin",
        "clostridium difficile toxin",
        desc="Clostridioides difficile toxin assay.",
    )
    add_qualitative(
        "Mononucleosis Spot",
        "infectious_disease",
        "monospot",
        "mononucleosis spot test",
        desc="Heterophile antibody screen for infectious mononucleosis.",
    )
    add_qualitative(
        "Strep A Rapid",
        "infectious_disease",
        "strep a rapid",
        "group a strep rapid",
        desc="Rapid antigen test for group A Streptococcus.",
    )
    add_qualitative(
        "TB Quantiferon",
        "infectious_disease",
        "quantiferon tb gold",
        "tb quantiferon",
        desc="Interferon-gamma release assay for tuberculosis exposure.",
    )
    add_qualitative(
        "Lyme Antibody",
        "infectious_disease",
        "lyme antibody",
        "borrelia burgdorferi antibody",
        desc="Lyme disease serology screen.",
    )

    # GI / stool inflammation markers
    add("Fecal Calprotectin", "gi_stool", "ug/g", 0, 50, "fecal calprotectin", "calprotectin stool", "stool calprotectin", opt_hi=30, crit_hi=250)
    add("Fecal Lactoferrin", "gi_stool", "ug/mL", 0, 7.25, "fecal lactoferrin", "lactoferrin stool", crit_hi=50)
    add("Pancreatic Elastase", "gi_stool", "ug/g", 200, None, "pancreatic elastase", "fecal elastase", "elastase stool", crit_lo=100)
    add("Fecal Fat", "gi_stool", "g/24h", 0, 7, "fecal fat", "stool fat", "24 hour fecal fat")
    add("Stool pH", "gi_stool", "pH", 6.0, 7.5, "stool ph", "fecal ph")
    add("Fecal Alpha-1 Antitrypsin", "gi_stool", "mg/dL", 0, 0.3, "fecal alpha 1 antitrypsin", "stool a1at")
    add_qualitative("Fecal Occult Blood", "gi_stool", "fecal occult blood", "stool occult blood", "fobt", desc="Qualitative fecal occult blood screen.")
    add("Zonulin", "gi_stool", "ng/mL", 0, 48, "zonulin", "serum zonulin")

    # Microbiology cultures
    add_culture("Urine Culture", "urine culture", "culture urine", desc="Urine bacterial culture.")
    add_culture("Blood Culture", "blood culture", desc="Blood bacterial culture.")
    add_culture("Stool Culture", "stool culture", "fecal culture", desc="Stool bacterial culture.")
    add_culture("Throat Culture", "throat culture", "pharyngeal culture", desc="Throat bacterial culture.")
    add_culture("Wound Culture", "wound culture", desc="Wound site bacterial culture.")
    add_culture("Sputum Culture", "sputum culture", desc="Sputum bacterial culture.")
    add_culture("Vaginal Culture", "vaginal culture", desc="Vaginal bacterial culture.")
    add_culture("Cervical Culture", "cervical culture", desc="Cervical bacterial culture.")

    # Celiac / autoimmune serology
    add_qualitative("tTG IgA", "celiac_serology", "ttg iga", "tissue transglutaminase iga", "anti ttg iga", desc="Tissue transglutaminase IgA for celiac screening.")
    add_qualitative("tTG IgG", "celiac_serology", "ttg igg", "tissue transglutaminase igg", desc="Tissue transglutaminase IgG (when IgA deficient).")
    add_qualitative("EMA IgA", "celiac_serology", "ema iga", "endomysial antibody iga", desc="Endomysial IgA antibody for celiac disease.")
    add_qualitative("Deamidated Gliadin IgA", "celiac_serology", "deamidated gliadin iga", "dgp iga", desc="Deamidated gliadin peptide IgA.")
    add_qualitative("Deamidated Gliadin IgG", "celiac_serology", "deamidated gliadin igg", "dgp igg", desc="Deamidated gliadin peptide IgG.")
    add("Total IgA", "celiac_serology", "mg/dL", 70, 400, "total iga", "iga total", desc="Total IgA to interpret tTG/EMA in IgA-deficient patients.")

    # Allergy / specific IgE panels
    add("Total IgE", "allergy", "IU/mL", 0, 100, "total ige", "ige total", opt_hi=50, crit_hi=500)
    add("Peanut IgE", "allergy", "kU/L", 0, 0.35, "peanut ige", "ige peanut", "peanut specific ige")
    add("Milk IgE", "allergy", "kU/L", 0, 0.35, "milk ige", "cow milk ige", "ige milk")
    add("Egg IgE", "allergy", "kU/L", 0, 0.35, "egg ige", "egg white ige", "ige egg")
    add("Wheat IgE", "allergy", "kU/L", 0, 0.35, "wheat ige", "ige wheat")
    add("Soy IgE", "allergy", "kU/L", 0, 0.35, "soy ige", "ige soy")
    add("Tree Nut IgE", "allergy", "kU/L", 0, 0.35, "tree nut ige", "ige tree nut")
    add("Shellfish IgE", "allergy", "kU/L", 0, 0.35, "shellfish ige", "ige shellfish")
    add("Fish IgE", "allergy", "kU/L", 0, 0.35, "fish ige", "ige fish")
    add("Dust Mite IgE", "allergy", "kU/L", 0, 0.35, "dust mite ige", "d pteronyssinus ige", "ige dust mite")
    add("Cat Dander IgE", "allergy", "kU/L", 0, 0.35, "cat dander ige", "ige cat", "cat epithelium ige")
    add("Dog Dander IgE", "allergy", "kU/L", 0, 0.35, "dog dander ige", "ige dog", "dog epithelium ige")
    add("Grass Pollen IgE", "allergy", "kU/L", 0, 0.35, "grass pollen ige", "ige grass", "timothy grass ige")
    add("Ragweed IgE", "allergy", "kU/L", 0, 0.35, "ragweed ige", "ige ragweed")
    add("Birch Pollen IgE", "allergy", "kU/L", 0, 0.35, "birch pollen ige", "ige birch")
    add("Latex IgE", "allergy", "kU/L", 0, 0.35, "latex ige", "ige latex")

    # Pharmacogenomics (PGx)
    add_genotype("CYP2D6 Genotype", "cyp2d6 genotype", "cyp2d6", desc="CYP2D6 metabolizer status affecting many psychotropics and opioids.")
    add_genotype("CYP2C19 Genotype", "cyp2c19 genotype", "cyp2c19", desc="CYP2C19 metabolizer status affecting PPIs, clopidogrel, and some SSRIs.")
    add_genotype("CYP3A4 Genotype", "cyp3a4 genotype", "cyp3a4", desc="CYP3A4 variant affecting statins, immunosuppressants, and many drugs.")
    add_genotype("CYP2C9 Genotype", "cyp2c9 genotype", "cyp2c9", desc="CYP2C9 variant affecting warfarin and NSAID metabolism.")
    add_genotype("VKORC1 Genotype", "vkorc1 genotype", "vkorc1", desc="VKORC1 variant guiding warfarin dosing.")
    add_genotype("SLCO1B1 Genotype", "slco1b1 genotype", "slco1b1", desc="SLCO1B1 variant associated with statin myopathy risk.")
    add_genotype("TPMT Genotype", "tpmt genotype", "tpmt", desc="TPMT variant guiding thiopurine (azathioprine/6-MP) dosing.")
    add_genotype("DPYD Genotype", "dpyd genotype", "dpyd", desc="DPYD variant guiding fluoropyrimidine (5-FU/capecitabine) dosing.")
    add_genotype("HLA-B*5701", "hla b 5701", "hla b5701", desc="HLA-B*5701 screening for abacavir hypersensitivity risk.")
    add_genotype("MTHFR C677T", "mthfr c677t", "mthfr genotype", desc="MTHFR C677T variant relevant to homocysteine/folate metabolism.")
    add_genotype("Factor V Leiden", "factor v leiden", "f5 leiden", desc="Factor V Leiden thrombophilia variant.")
    add_genotype("Prothrombin G20210A", "prothrombin g20210a", "factor ii g20210a", desc="Prothrombin G20210A thrombophilia variant.")

    return entries


def main() -> None:
    entries = _build_entries()
    if len(entries) < 200:
        raise SystemExit(f"Expected >= 200 biomarkers, got {len(entries)}")

    body = pprint.pformat(entries, width=120, sort_dicts=False)
    content = f'''"""Comprehensive clinical biomarker catalog ({len(entries)} tests).

Single source of truth for reference ranges, aliases, and seed data.
Regenerate with: python scripts/generate_biomarker_catalog.py
"""

from __future__ import annotations

import re

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def _clean(raw_name: str) -> str:
    lowered = raw_name.strip().lower()
    collapsed = _NON_ALNUM_RE.sub(" ", lowered).strip()
    return re.sub(r"\\s+", " ", collapsed)


BIOMARKER_ENTRIES: list[dict] = {body}


def build_reference_data() -> dict[str, dict]:
    out: dict[str, dict] = {{}}
    for e in BIOMARKER_ENTRIES:
        out[e["canonical_name"]] = {{
            "reference_low": e["reference_low"],
            "reference_high": e["reference_high"],
            "optimal_low": e["optimal_low"],
            "optimal_high": e["optimal_high"],
            "critical_low": e.get("critical_low"),
            "critical_high": e.get("critical_high"),
            "category": e["category"],
            "result_kind": e.get("result_kind", "numeric"),
        }}
    return out


def build_alias_map() -> dict[str, str]:
    alias_map: dict[str, str] = {{}}
    for e in BIOMARKER_ENTRIES:
        canonical = e["canonical_name"]
        alias_map[_clean(canonical)] = canonical
        for alias in e.get("aliases", []):
            alias_map[_clean(alias)] = canonical
    return alias_map


def get_seed_records() -> list[dict]:
    return [
        {{
            "canonical_name": e["canonical_name"],
            "category": e["category"],
            "description": e["description"],
            "default_unit": e["default_unit"],
            "reference_low": e["reference_low"],
            "reference_high": e["reference_high"],
            "optimal_low": e["optimal_low"],
            "optimal_high": e["optimal_high"],
        }}
        for e in BIOMARKER_ENTRIES
    ]


REFERENCE_DATA = build_reference_data()
ALIAS_MAP = build_alias_map()
'''
    out_path = Path(__file__).resolve().parent.parent / "app" / "knowledge_graph" / "biomarker_catalog.py"
    out_path.write_text(content)
    print(f"Wrote {len(entries)} biomarkers to {out_path}")


if __name__ == "__main__":
    main()
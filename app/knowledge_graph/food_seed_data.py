"""Food -> Compound knowledge graph layer (see README 'Food -> Compound Layer').

Mirrors the shape of seed_data.py so both can be loaded by scripts/seed_db.py
in the same pass. COMPOUND_TO_FOOD_SOURCES / FOOD_TO_COMPOUNDS are static,
zero-latency lookup dicts derived from FOOD_COMPOUND_SOURCES so the pipeline
can attach `food_sources` to a recommendation without a database round-trip.
"""

PHYTOCHEMICAL_COMPOUNDS: list[dict] = [
    {
        "name": "Sulforaphane",
        "category": "phytochemical",
        "description": "Isothiocyanate formed from glucoraphanin via the myrosinase enzyme in cruciferous vegetables.",
        "mechanism": "Potent Nrf2 activator, upregulating phase II detoxification and antioxidant enzymes.",
        "is_regulated": False,
        "safety_flags": [],
        "drug_interactions": [],
    },
    {
        "name": "Anthocyanins",
        "category": "phytochemical",
        "description": "Flavonoid pigments responsible for red/blue/purple coloration in berries and grapes.",
        "mechanism": "Activate Nrf2 signaling and improve endothelial nitric oxide bioavailability.",
        "is_regulated": False,
        "safety_flags": [],
        "drug_interactions": [],
    },
    {
        "name": "EGCG",
        "category": "phytochemical",
        "description": "Epigallocatechin gallate, the principal catechin in green tea.",
        "mechanism": "Activates AMPK and inhibits NF-κB-driven inflammatory gene expression.",
        "is_regulated": False,
        "safety_flags": [
            {"condition": "liver_disease", "severity": "caution",
             "note": "Concentrated green tea extract (not brewed tea) carries a rare hepatotoxicity signal at high doses."},
        ],
        "drug_interactions": [],
    },
    {
        "name": "Allicin",
        "category": "phytochemical",
        "description": "Sulfur compound formed when garlic is crushed, converting alliin via allinase.",
        "mechanism": "Inhibits HMG-CoA reductase, lowering hepatic cholesterol synthesis; mild NF-κB inhibition.",
        "is_regulated": False,
        "safety_flags": [],
        "drug_interactions": [
            {"drug_name": "Warfarin", "severity": "moderate",
             "mechanism": "Additive antiplatelet effect may potentiate bleeding risk.",
             "note": "Monitor INR with concentrated garlic supplements."},
        ],
    },
    {
        "name": "Ellagic Acid",
        "category": "phytochemical",
        "description": "Polyphenol found in pomegranate, converted by gut bacteria into urolithins.",
        "mechanism": "Urolithin metabolites activate Nrf2 and support mitochondrial mitophagy.",
        "is_regulated": False,
        "safety_flags": [],
        "drug_interactions": [],
    },
    {
        "name": "Lycopene",
        "category": "phytochemical",
        "description": "Carotenoid pigment concentrated in cooked tomato products.",
        "mechanism": "Scavenges reactive oxygen species and inhibits LDL oxidation.",
        "is_regulated": False,
        "safety_flags": [],
        "drug_interactions": [],
    },
    {
        "name": "Beta-Carotene",
        "category": "phytochemical",
        "description": "Provitamin A carotenoid found in orange/yellow vegetables.",
        "mechanism": "Nrf2 pathway activation; converted to retinol as needed.",
        "is_regulated": False,
        "safety_flags": [
            {"condition": "smoking", "severity": "contraindication",
             "note": "High-dose beta-carotene supplements (not food-level intake) increased lung cancer incidence "
                     "in smokers in the ATBC and CARET trials."},
        ],
        "drug_interactions": [],
    },
    {
        "name": "Quercetin",
        "category": "phytochemical",
        "description": "Flavonol widely distributed in onions and other allium vegetables.",
        "mechanism": "Inhibits NF-κB and xanthine oxidase, reducing inflammatory signaling and uric acid production.",
        "is_regulated": False,
        "safety_flags": [],
        "drug_interactions": [
            {"drug_name": "Chemotherapy", "severity": "moderate",
             "mechanism": "May interact with certain chemotherapeutic agents via CYP3A4 modulation.",
             "note": "Discuss with oncologist before use."},
        ],
    },
]

FOOD_INTERVENTIONS: list[dict] = [
    {"name": "Broccoli Sprouts", "category": "food",
     "description": "Young broccoli sprouts, the richest common source of glucoraphanin.", "mechanism": None,
     "is_regulated": False, "safety_flags": [], "drug_interactions": []},
    {"name": "Broccoli", "category": "food", "description": "Mature broccoli florets.", "mechanism": None,
     "is_regulated": False, "safety_flags": [], "drug_interactions": []},
    {"name": "Brussels Sprouts", "category": "food", "description": "Cruciferous vegetable.", "mechanism": None,
     "is_regulated": False, "safety_flags": [], "drug_interactions": []},
    {"name": "Kale", "category": "food", "description": "Leafy cruciferous green.", "mechanism": None,
     "is_regulated": False, "safety_flags": [], "drug_interactions": []},
    {"name": "Blueberries", "category": "food", "description": "Anthocyanin-rich berry.", "mechanism": None,
     "is_regulated": False, "safety_flags": [], "drug_interactions": []},
    {"name": "Blackberries", "category": "food", "description": "Anthocyanin-rich berry.", "mechanism": None,
     "is_regulated": False, "safety_flags": [], "drug_interactions": []},
    {"name": "Purple Grapes", "category": "food", "description": "Anthocyanin-containing fruit.", "mechanism": None,
     "is_regulated": False, "safety_flags": [], "drug_interactions": []},
    {"name": "Green Tea", "category": "food", "description": "Camellia sinensis infusion, rich in catechins.",
     "mechanism": None, "is_regulated": False, "safety_flags": [], "drug_interactions": []},
    {"name": "Garlic", "category": "food", "description": "Allium sativum bulb.", "mechanism": None,
     "is_regulated": False, "safety_flags": [], "drug_interactions": []},
    {"name": "Pomegranate", "category": "food", "description": "Punica granatum fruit/juice.", "mechanism": None,
     "is_regulated": False, "safety_flags": [], "drug_interactions": []},
    {"name": "Cooked Tomatoes", "category": "food", "description": "Heat-processed tomato products.",
     "mechanism": None, "is_regulated": False, "safety_flags": [], "drug_interactions": []},
    {"name": "Carrots", "category": "food", "description": "Root vegetable rich in beta-carotene.",
     "mechanism": None, "is_regulated": False, "safety_flags": [], "drug_interactions": []},
    {"name": "Onions", "category": "food", "description": "Allium cepa bulb, a major dietary quercetin source.",
     "mechanism": None, "is_regulated": False, "safety_flags": [], "drug_interactions": []},
]

# (food, compound, richness, typical_serving, note)
FOOD_COMPOUND_SOURCES: list[tuple[str, str, str, str, str | None]] = [
    ("Broccoli Sprouts", "Sulforaphane", "high", "1/4 cup fresh sprouts",
     "Roughly 10-100x the glucoraphanin concentration of mature broccoli."),
    ("Broccoli", "Sulforaphane", "moderate", "1 cup steamed",
     "Light steaming preserves myrosinase better than boiling."),
    ("Brussels Sprouts", "Sulforaphane", "moderate", "1 cup cooked", None),
    ("Kale", "Sulforaphane", "low", "1-2 cups raw", "Lower glucosinolate density than broccoli."),
    ("Blueberries", "Anthocyanins", "high", "1 cup fresh", None),
    ("Blackberries", "Anthocyanins", "high", "1 cup fresh", None),
    ("Purple Grapes", "Anthocyanins", "moderate", "1 cup fresh", None),
    ("Green Tea", "EGCG", "high", "2-3 cups brewed", "Brewed tea; concentrated extracts carry different safety data."),
    ("Garlic", "Allicin", "high", "1-2 cloves crushed, raw",
     "Allicin forms only after crushing/chopping raw garlic; cooking deactivates allinase."),
    ("Pomegranate", "Ellagic Acid", "high", "1 cup arils or 8oz juice", None),
    ("Cooked Tomatoes", "Lycopene", "high", "1/2 cup tomato sauce",
     "Cooking with oil increases lycopene bioavailability relative to raw tomatoes."),
    ("Carrots", "Beta-Carotene", "high", "1 cup cooked", None),
    ("Onions", "Quercetin", "moderate", "1/2 cup raw", "Red/yellow onions contain more quercetin than white onions."),
]

# (compound, biomarker, effect, evidence_level, pmid, summary)
FOOD_COMPOUND_EVIDENCE_CLAIMS: list[dict] = [
    {"intervention_name": "Sulforaphane", "biomarker_name": "CRP", "pathway_code": "NRF2",
     "effect": "decreases", "evidence_level": "moderate", "pmid": "26893296",
     "summary": "RCT showing broccoli sprout sulforaphane reduced inflammatory markers including CRP."},
    {"intervention_name": "Anthocyanins", "biomarker_name": "LDL", "pathway_code": "NRF2",
     "effect": "decreases", "evidence_level": "moderate", "pmid": "25733639",
     "summary": "RCT of anthocyanin-rich berry intake improving lipid profile and endothelial function."},
    {"intervention_name": "EGCG", "biomarker_name": "Glucose", "pathway_code": "AMPK",
     "effect": "decreases", "evidence_level": "moderate", "pmid": "24001782",
     "summary": "Meta-analysis of green tea catechin effects on fasting glucose and insulin sensitivity."},
    {"intervention_name": "Allicin", "biomarker_name": "LDL", "pathway_code": "HEPATIC_LIPID",
     "effect": "decreases", "evidence_level": "moderate", "pmid": "23590705",
     "summary": "Meta-analysis of garlic preparations' modest LDL-lowering effect."},
    {"intervention_name": "Ellagic Acid", "biomarker_name": None, "pathway_code": "NRF2",
     "effect": "increases", "evidence_level": "preclinical", "pmid": "27187333",
     "summary": "Preclinical evidence for urolithin-mediated mitophagy activation."},
    {"intervention_name": "Lycopene", "biomarker_name": "LDL", "pathway_code": "NRF2",
     "effect": "decreases", "evidence_level": "moderate", "pmid": "21875839",
     "summary": "RCT evidence for lycopene's inhibition of LDL oxidation."},
    {"intervention_name": "Beta-Carotene", "biomarker_name": None, "pathway_code": "NRF2",
     "effect": "increases", "evidence_level": "low", "pmid": "8602180",
     "summary": "ATBC trial data informing the smoker contraindication for high-dose supplementation."},
    {"intervention_name": "Quercetin", "biomarker_name": "Uric Acid", "pathway_code": "PURINE_URIC_ACID",
     "effect": "decreases", "evidence_level": "moderate", "pmid": "27133315",
     "summary": "RCT showing quercetin supplementation lowered serum uric acid via xanthine oxidase inhibition."},
]


def _build_compound_to_food_sources() -> dict[str, list[dict]]:
    lookup: dict[str, list[dict]] = {}
    for food, compound, richness, serving, note in FOOD_COMPOUND_SOURCES:
        lookup.setdefault(compound, []).append(
            {"food": food, "richness": richness, "typical_serving": serving, "note": note}
        )
    return lookup


def _build_food_to_compounds() -> dict[str, list[dict]]:
    lookup: dict[str, list[dict]] = {}
    for food, compound, richness, serving, note in FOOD_COMPOUND_SOURCES:
        lookup.setdefault(food, []).append(
            {"compound": compound, "richness": richness, "typical_serving": serving, "note": note}
        )
    return lookup


COMPOUND_TO_FOOD_SOURCES: dict[str, list[dict]] = _build_compound_to_food_sources()
FOOD_TO_COMPOUNDS: dict[str, list[dict]] = _build_food_to_compounds()

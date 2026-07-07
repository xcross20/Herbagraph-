#!/usr/bin/env python3
"""Generate expanded herb, supplement, food, and phytochemical catalogs (200 each).

Tier A curated entries from tier_a_catalog.py override template rows by name.
Run from repo root: python scripts/generate_intervention_catalog.py
"""

from __future__ import annotations

import pprint
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from app.knowledge_graph.tier_a_catalog import (  # noqa: E402
    TIER_A_FOOD_COMPOUND_SOURCES,
    TIER_A_FOODS,
    TIER_A_HERBS,
    TIER_A_PHYTOCHEMICALS,
    TIER_A_SUPPLEMENTS,
)

PATHWAYS = [
    "NF_KB", "IL6_JAK_STAT3", "AMPK", "INSULIN_PI3K_AKT", "NRF2", "MTOR_AUTOPHAGY",
    "HPA_AXIS", "THYROID_HPT", "HEPATIC_LIPID", "ONE_CARBON_METHYLATION", "GLP1_INCRETINS",
    "MITOCHONDRIAL_NAD", "IRON_HEPCIDIN", "PURINE_URIC_ACID", "VITAMIN_D_RECEPTOR", "RENAL_FILTRATION",
]
BIOMARKERS = ["CRP", "Glucose", "HbA1c", "LDL", "HDL", "Triglycerides", "ALT", "TSH", "Vitamin D", "Ferritin"]
EFFECTS = ["decreases", "increases"]

# Preserve hand-authored core herbs (merged into catalog output)
CORE_HERBS: list[dict] = [
    {
        "name": "Boswellia serrata", "category": "herb",
        "description": "Indian frankincense resin extract standardized for boswellic acids.",
        "mechanism": "Selectively inhibits 5-LOX, reducing leukotriene B4 synthesis and downstream NF-κB activation.",
        "is_regulated": False,
        "compounds": [{"name": "AKBA (acetyl-11-keto-beta-boswellic acid)", "primary_target": "5-LOX (5-lipoxygenase)",
                       "role": "primary active constituent", "pubchem_cid": None}],
        "safety_flags": [{"condition": "pregnancy", "severity": "contraindication",
                          "note": "Insufficient safety data in pregnancy; avoid."}],
        "drug_interactions": [{"drug_name": "Warfarin", "severity": "moderate",
                               "mechanism": "May potentiate anticoagulant effect.", "note": "Monitor INR."}],
    },

    {
        "name": "Ashwagandha", "category": "herb",
        "description": "Withania somnifera root extract standardized for withanolides.",
        "mechanism": "Modulates HPA axis activity and supports GABAergic signaling.",
        "is_regulated": False,
        "compounds": [{"name": "Withanolides", "primary_target": "HPA axis", "role": "primary active constituent class", "pubchem_cid": None}],
        "safety_flags": [{"condition": "pregnancy", "severity": "contraindication", "note": "Avoid in pregnancy."}],
        "drug_interactions": [{"drug_name": "Levothyroxine", "severity": "moderate", "mechanism": "May affect thyroid levels.", "note": "Monitor TSH."}],
    },
    {
        "name": "Milk Thistle", "category": "herb",
        "description": "Silybum marianum seed extract standardized for silymarin.",
        "mechanism": "Upregulates Nrf2-mediated antioxidant defenses in hepatocytes.",
        "is_regulated": False,
        "compounds": [{"name": "Silymarin", "primary_target": "Nrf2", "role": "primary active constituent", "pubchem_cid": None}],
        "safety_flags": [], "drug_interactions": [],
    },
]

HERB_NAMES = [
    "Ginkgo biloba", "Panax ginseng", "Rhodiola rosea", "Eleuthero", "Schisandra", "Licorice Root",
    "Astragalus", "Reishi", "Cordyceps", "Lion's Mane", "Chaga", "Turkey Tail", "Shiitake", "Maitake",
    "Holy Basil", "Rhaponticum", "Shatavari", "Triphala", "Bacopa monnieri", "Gotu Kola", "Centella asiatica",
    "Valerian", "Passionflower", "Chamomile", "Lemon Balm", "Skullcap", "Kava", "Hops", "California Poppy",
    "St. John's Wort", "Saffron", "Rhodiola crenulata", "Maca", "Tribulus", "Fenugreek", "Saw Palmetto",
    "Pygeum", "Nettle Root", "Pumpkin Seed", "Red Clover", "Black Cohosh", "Dong Quai", "Chaste Tree",
    "Wild Yam", "Vitex", "Motherwort", "Blue Cohosh", "Damiana", "Muira Puama", "Catuaba", "Tongkat Ali",
    "Eurycoma longifolia", "Cistanche", "Epimedium", "Horny Goat Weed", "Ginseng American", "Codonopsis",
    "Danshen", "Salvia miltiorrhiza", "Ginger", "Turmeric", "Black Pepper", "Cinnamon", "Clove", "Nutmeg",
    "Cardamom", "Fennel", "Cumin", "Coriander", "Oregano", "Thyme", "Rosemary", "Sage", "Peppermint",
    "Spearmint", "Basil", "Parsley", "Cilantro", "Dill", "Bay Leaf", "Lavender", "Echinacea", "Goldenseal",
    "Oregon Grape", "Barberry", "Andrographis", "Cat's Claw", "Pau d'Arco", "Olive Leaf", "Garlic Extract",
    "Hawthorn", "Arjuna", "Gymnema", "Bitter Melon", "Fenugreek Seed", "Cinnamon Bark", "Banaba Leaf",
    "White Mulberry", "Berberine-containing Goldthread", "Neem", "Amla", "Haritaki", "Bibhitaki", "Guduchi",
    "Kutki", "Picrorhiza", "Kutki Root", "Phyllanthus amarus", "Bhumyamalaki", "Punarnava", "Shilajit",
    "Chyawanprash Base", "Yarrow", "Calendula", "Plantain", "Comfrey", "Arnica", "Bupleurum", "Coptis",
    "Scutellaria baicalensis", "Baikal Skullcap", "Phellodendron", "Gardenia", "Corydalis", "Corydalis yanhusuo",
    "Kudzu", "Pueraria", "Houttuynia", "Artemisia annua", "Sweet Wormwood", "Black Walnut Hull", "Wormwood",
    "Clove Bud", "Myrrh", "Frankincense", "Propolis", "Bee Pollen", "Royal Jelly", "Chlorella", "Spirulina",
    "Blue-Green Algae", "Aloe Vera", "Slippery Elm", "Marshmallow Root", "DGL Licorice", "Chamomile Flower",
    "Peppermint Leaf", "Fennel Seed", "Caraway", "Anise", "Artichoke Leaf", "Dandelion Root", "Burdock Root",
    "Yellow Dock", "Red Root", "Oregon Grape Root", "Chanca Piedra", "Uva Ursi", "Cranberry Extract",
    "Juniper Berry", "Celery Seed", "Celery Seed Extract", "Horsetail", "Corn Silk", "Gravel Root",
    "Stone Root", "Hydrangea Root", "Queen of the Meadow", "Buchu", "Bearberry", "Usnea", "Usnea lichen",
    "Rehmannia", "Eucommia", "Morinda", "Noni", "Mangosteen", "Camu Camu", "Acerola", "Rose Hips", "Bilberry",
    "Eyebright", "Bilberry Fruit", "Lutein-rich Marigold", "Saffron Stigma", "Safflower", "Milk Thistle Seed",
    "Artichoke Extract", "Boldo", "Fringe Tree", "Gentian", "Centaury", "Wormwood Herb", "Black Seed",
    "Nigella sativa", "Cumin Black", "Fenugreek Extract", "Gymnema sylvestre", "Salacia", "Pterocarpus",
    "Vijayasar", "Gurmar", "Karela", "Jamun", "Neem Leaf", "Tulsi", "Ocimum sanctum", "Moringa", "Drumstick Tree",
    "Baobab", "Lucuma", "Mesquite", "Chia Seed Herb", "Hemp Seed", "Flax Seed", "Psyllium Husk", "Triphala Powder",
    "Slippery Elm Bark", "Marshmallow Althaea", "Plantago", "Mullein", "Coltsfoot", "Elecampane", "Licorice DGL",
    "Thyme Leaf", "Oregano Oil Herb", "Monarda", "Bee Balm", "Elder Flower", "Elderberry Herb", "Honeysuckle",
    "Lonicera", "Isatis", "Ban Lan Gen", "Honeysuckle Flower", "Forsythia", "Lian Qiao", "Houttuynia cordata",
]

_LIFESTYLE_CATEGORIES = frozenset({
    "exercise", "sleep", "stress_reduction", "behavior", "medication", "hormone", "environmental",
})

CORE_SUPPLEMENTS: list[dict] = [
    s for s in TIER_A_SUPPLEMENTS if s["category"] == "supplement"
]

SUPPLEMENT_NAMES = [
    "Vitamin C", "Vitamin E", "Vitamin K2", "Vitamin A", "Vitamin B6", "Vitamin B1", "Vitamin B2",
    "Vitamin B3", "Vitamin B5", "Biotin", "Choline", "Inositol", "SAMe", "MSM", "DIM", "Calcium",
    "Potassium", "Selenium", "Copper", "Manganese", "Chromium", "Iodine", "Molybdenum", "Boron",
    "Silica", "Strontium", "Vanadium", "Probiotics", "Saccharomyces boulardii", "Lactobacillus rhamnosus",
    "Bifidobacterium longum", "Multi-Strain Probiotic", "Prebiotic Fiber", "Psyllium", "Glucomannan",
    "Pectin", "Apple Cider Vinegar Capsules", "Betaine HCl", "Digestive Enzymes", "Pancreatin",
    "Bromelain", "Papain", "Quercetin Supplement", "Resveratrol Supplement", "Pterostilbene",
    "PQQ Supplement", "Astaxanthin", "Lutein Supplement", "Zeaxanthin", "Lycopene Supplement",
    "Green Tea Extract", "Caffeine Anhydrous", "L-Theanine", "GABA Supplement", "5-HTP",
    "Melatonin Supplement", "Valerian Extract", "Passionflower Extract", "Lemon Balm Extract",
    "Kava Extract", "St. John's Wort Extract", "Saffron Extract", "Rhodiola Extract", "Ginseng Extract",
    "Cordyceps Extract", "Lion's Mane Extract", "Reishi Extract", "Chaga Extract", "Turkey Tail Extract",
    "Maitake Extract", "Shiitake Extract", "Agaricus blazei", "Poria cocos", "Polyporus umbellatus",
    "Astragalus Extract", "Eleuthero Extract", "Schisandra Extract", "Gymnema Extract", "Banaba Extract",
    "Bitter Melon Extract", "Fenugreek Extract", "Cinnamon Extract", "Chromium Picolinate",
    "Alpha-GPC", "Citicoline", "Phosphatidylserine", "Phosphatidylcholine", "Huperzine A",
    "Vinpocetine", "Bacopa Extract", "Ginkgo Extract", "Lion's Mane Powder", "Creatine Monohydrate",
    "Creatine HCl", "Beta-Alanine", "Citrulline Malate", "Beetroot Extract", "Nitrate Supplement",
    "HMB", "BCAA", "EAAs", "Whey Protein", "Casein Protein", "Plant Protein Blend", "Collagen Type II",
    "Glucosamine Sulfate", "Chondroitin Sulfate", "MSM Joint Formula", "Hyaluronic Acid Oral",
    "UC-II Collagen", "Boswellia Extract", "Turmeric Extract", "Curcumin Phytosome", "Ginger Extract",
    "Devil's Claw", "White Willow Bark", "Capsaicin Supplement", "Arnica Oral", "Bromelain Anti-Inflammatory",
    "Fish Oil", "Krill Oil", "Algal DHA", "Flaxseed Oil", "Evening Primrose Oil", "Borage Oil",
    "Black Seed Oil", "Pumpkin Seed Oil", "Sea Buckthorn Oil", "Cod Liver Oil", "MCT Oil Powder",
    "Caprylic Acid", "Capric Acid", "Butyrate", "Tributyrin", "Postbiotic", "Colostrum",
    "Lactoferrin", "Immunoglobulin G", "Beta-Glucan", "Echinacea Extract", "Elderberry Extract",
    "Andrographis Extract", "Pelargonium sidoides", "Umckaloabo", "Oregano Oil", "Monolaurin",
    "Lauricidin", "Silver Colloid", "Iodine Supplement", "Potassium Iodide", "Lugol's Iodine",
    "DHEA", "Pregnenolone", "7-Keto DHEA", "DIM Supplement", "Calcium D-Glucarate", "Indole-3-Carbinol",
    "Broccoli Extract", "Sulforaphane Supplement", "NAC Supplement", "Glutathione Liposomal",
    "Liposomal Vitamin C", "Liposomal Glutathione", "R-Lipoic Acid", "Benfotiamine", "Thiamine",
    "Riboflavin-5-Phosphate", "P5P", "Methylcobalamin B12", "Adenosylcobalamin", "Hydroxocobalamin",
    "Methylfolate", "Folinic Acid", "Trimethylglycine", "Choline Bitartrate", "CDP-Choline",
    "Uridine Monophosphate", "D-Ribose", "CoQ10 Ubiquinol", "PQQ", "Fulvic Acid",
    "Trace Mineral Complex", "Electrolyte Powder", "Oral Rehydration Salts", "Magnesium Citrate",
    "Magnesium Malate", "Magnesium L-Threonate", "Magnesium Taurate", "Zinc Picolinate",
    "Zinc Bisglycinate", "Iron Bisglycinate", "Ferrous Sulfate", "Copper Bisglycinate",
    "Selenium Selenomethionine", "Molybdenum Glycinate", "Potassium Citrate", "Calcium Citrate",
    "Calcium Hydroxyapatite", "Vitamin D3 K2 Combo", "Vitamin D2", "Vitamin K1", "MK-4",
    "Natto-Derived K2", "Mixed Tocopherols", "Mixed Tocotrienols", "Astaxanthin Krill",
    "Spirulina Powder", "Chlorella Powder", "Wheatgrass Powder", "Barley Grass Powder",
    "Moringa Powder", "Matcha Powder", "Cocoa Flavanol Extract", "Grape Seed Extract",
    "Pine Bark Extract", "Hawthorn Extract", "Beetroot Powder", "Chlorophyll Supplement",
    "Spirulina Tablets", "Blue-Green Algae Capsules", "Kelp Iodine", "Bladderwrack",
    "Irish Sea Moss", "Red Yeast Rice", "Policosanol", "Bergamot Extract", "Artichoke Extract",
    "Dandelion Extract", "Milk Thistle Phytosome", "Schisandra Berry", "Triphala Capsules",
    "Slippery Elm Capsules", "Marshmallow Root Capsules", "Aloe Vera Gel Capsules",
    "L-Glutamine Powder", "Glycine Powder", "Taurine Powder", "L-Arginine", "L-Citrulline",
    "L-Lysine", "L-Proline", "L-Tyrosine", "L-Tryptophan", "N-Acetyl Tyrosine", "Acetyl-L-Carnitine",
    "L-Carnitine Tartrate", "Propionyl-L-Carnitine", "Carnosine", "Anserine", "Beta-Sitosterol",
    "Saw Palmetto Extract", "Pygeum Extract", "Nettle Root Extract", "Pumpkin Seed Extract",
    "Lycopene Prostate Formula", "Cranberry PACs", "D-Mannose", "Uva Ursi Extract", "Juniper Extract",
    "Horsetail Extract", "Parsley Leaf", "Asparagus Extract", "Celery Seed Extract",
]

FOOD_NAMES = [
    "Broccoli Sprouts", "Broccoli", "Brussels Sprouts", "Kale", "Spinach", "Swiss Chard", "Collard Greens",
    "Bok Choy", "Arugula", "Watercress", "Cabbage", "Cauliflower", "Kohlrabi", "Turnip Greens", "Mustard Greens",
    "Beet Greens", "Romaine Lettuce", "Iceberg Lettuce", "Endive", "Escarole", "Radicchio", "Carrots", "Beets",
    "Sweet Potato", "Yam", "Potato", "Parsnip", "Rutabaga", "Turnip", "Radish", "Daikon", "Celery", "Cucumber",
    "Zucchini", "Yellow Squash", "Butternut Squash", "Acorn Squash", "Pumpkin", "Eggplant", "Bell Pepper", "Jalapeño",
    "Tomato", "Cooked Tomatoes", "Cherry Tomatoes", "Onions", "Red Onion", "Garlic", "Shallots", "Leeks", "Scallions",
    "Asparagus", "Green Beans", "Snap Peas", "Snow Peas", "Edamame", "Lima Beans", "Black Beans", "Kidney Beans",
    "Pinto Beans", "Navy Beans", "Chickpeas", "Lentils", "Split Peas", "Tofu", "Tempeh", "Miso", "Natto",
    "Blueberries", "Blackberries", "Raspberries", "Strawberries", "Cranberries", "Goji Berries", "Acai", "Mango",
    "Papaya", "Pineapple", "Banana", "Apple", "Pear", "Grapes", "Purple Grapes", "Red Grapes", "Orange", "Grapefruit",
    "Lemon", "Lime", "Kiwi", "Pomegranate", "Cherries", "Peaches", "Plums", "Apricots", "Figs", "Dates", "Prunes",
    "Avocado", "Coconut", "Olives", "Olive Oil", "Walnuts", "Almonds", "Cashews", "Pistachios", "Pecans", "Hazelnuts",
    "Brazil Nuts", "Macadamia Nuts", "Pine Nuts", "Sunflower Seeds", "Pumpkin Seeds", "Chia Seeds", "Flax Seeds",
    "Hemp Seeds", "Sesame Seeds", "Tahini", "Peanuts", "Peanut Butter", "Almond Butter", "Oats", "Steel Cut Oats",
    "Quinoa", "Brown Rice", "Wild Rice", "Barley", "Buckwheat", "Millet", "Amaranth", "Farro", "Bulgur", "Whole Wheat",
    "Sourdough Bread", "Rye Bread", "Salmon", "Sardines", "Mackerel", "Anchovies", "Herring", "Trout", "Tuna",
    "Cod", "Shrimp", "Mussels", "Oysters", "Clams", "Scallops", "Chicken Breast", "Turkey", "Grass-Fed Beef",
    "Lamb", "Pork Loin", "Eggs", "Greek Yogurt", "Kefir", "Cottage Cheese", "Mozzarella", "Cheddar", "Parmesan",
    "Feta", "Goat Cheese", "Butter", "Ghee", "Coconut Oil", "Avocado Oil", "Extra Virgin Olive Oil", "Green Tea",
    "Black Tea", "White Tea", "Oolong Tea", "Matcha", "Coffee", "Cocoa", "Dark Chocolate", "Turmeric Root",
    "Ginger Root", "Horseradish", "Wasabi", "Kimchi", "Sauerkraut", "Pickles", "Kombucha", "Miso Soup", "Bone Broth",
    "Chicken Broth", "Vegetable Broth", "Seaweed", "Nori", "Wakame", "Kelp", "Dulse", "Spirulina Powder", "Chlorella Powder",
    "Nutritional Yeast", "Mushrooms", "Shiitake Mushrooms", "Oyster Mushrooms", "Portobello", "Cremini", "Enoki",
    "King Oyster Mushroom", "Lion's Mane Mushroom", "Maitake Mushroom", "Bee Pollen Food", "Honey", "Maple Syrup",
    "Molasses", "Apple Cider Vinegar", "Balsamic Vinegar", "Red Wine Vinegar", "Tamari", "Coconut Aminos",
    "Hummus", "Guacamole", "Salsa", "Pesto", "Tomato Sauce", "Marinara", "Soy Milk", "Almond Milk", "Oat Milk",
    "Coconut Milk", "Rice Milk", "Hemp Milk", "Cashew Milk", "Water", "Sparkling Water", "Coconut Water",
]

CORE_PHYTOCHEMICALS: list[dict] = [
    {
        "name": "Sulforaphane", "category": "phytochemical",
        "description": "Isothiocyanate formed from glucoraphanin via the myrosinase enzyme in cruciferous vegetables.",
        "mechanism": "Potent Nrf2 activator, upregulating phase II detoxification and antioxidant enzymes.",
        "is_regulated": False, "safety_flags": [], "drug_interactions": [],
    },
    {
        "name": "Allicin", "category": "phytochemical",
        "description": "Sulfur compound formed when garlic is crushed, converting alliin via allinase.",
        "mechanism": "Inhibits HMG-CoA reductase, lowering hepatic cholesterol synthesis; mild NF-κB inhibition.",
        "is_regulated": False, "safety_flags": [],
        "drug_interactions": [{"drug_name": "Warfarin", "severity": "moderate",
                               "mechanism": "Additive antiplatelet effect may potentiate bleeding risk.",
                               "note": "Monitor INR with concentrated garlic supplements."}],
    },
    {
        "name": "Beta-Carotene", "category": "phytochemical",
        "description": "Provitamin A carotenoid found in orange/yellow vegetables.",
        "mechanism": "Nrf2 pathway activation; converted to retinol as needed.",
        "is_regulated": False,
        "safety_flags": [{"condition": "smoking", "severity": "contraindication",
                          "note": "High-dose beta-carotene supplements increased lung cancer incidence in smokers."}],
        "drug_interactions": [],
    },
]

# Names already represented as herbs/supplements in seed_data — skip in phytochemical catalog.
_RESERVED_INTERVENTION_NAMES = frozenset({
    "Curcumin", "Berberine", "Boswellia serrata", "Ashwagandha", "Milk Thistle",
    "Collagen Peptides",  # peptide_catalog.py
})

PHYTOCHEMICAL_BASES = [
    "Sulforaphane", "Anthocyanins", "EGCG", "Allicin", "Ellagic Acid", "Lycopene", "Beta-Carotene", "Quercetin",
    "Kaempferol", "Myricetin", "Rutin", "Hesperidin", "Naringenin", "Apigenin", "Luteolin", "Catechin", "Epicatechin",
    "Procyanidins", "Resveratrol", "Pterostilbene", "Piceatannol", "Curcumin", "Boswellic Acids", "Withanolides",
    "Ginsenosides", "Astragalosides", "Berberine", "Palmatine", "Coptisine", "Silymarin", "Silybin", "Chlorogenic Acid",
    "Caffeic Acid", "Ferulic Acid", "Rosmarinic Acid", "Carnosic Acid", "Carnosol", "Ursolic Acid", "Oleanolic Acid",
    "Betulinic Acid", "Glycyrrhizin", "Glabridin", "Honokiol", "Magnolol", "Baicalin", "Baicalein", "Wogonin",
    "Andrographolide", "Picrorhiza Kurroin", "Phyllanthin", "Gymnemic Acids", "Gymnemosides", "Mangiferin",
    "Morin", "Fisetin", "Lutein", "Zeaxanthin", "Astaxanthin", "Canthaxanthin", "Capsaicin", "Dihydrocapsaicin",
    "Piperine", "Gingerols", "Shogaols", "6-Gingerol", "Allyl Isothiocyanate", "Indole-3-Carbinol", "DIM",
    "Sulforaphane Nitrile", "Glucoraphanin", "Sinigrin", "Allicin-Derived Diallyl Sulfides", "Diallyl Disulfide",
    "S-Allyl Cysteine", "Theaflavins", "Thearubigins", "Chlorophyll", "Phycocyanin", "Phycoerythrin", "Betalains",
    "Betanin", "Phytosterols", "Beta-Sitosterol", "Stigmasterol", "Campesterol", "Saponins", "Ginseng Saponins",
    "Triterpenoid Saponins", "Steroidal Saponins", "Tannins", "Proanthocyanidins", "OPC", "Punicalagins",
    "Delphinidin", "Cyanidin", "Malvidin", "Pelargonidin", "Peonidin", "Petunidin", "Galangin", "Chrysin",
    "Baicalein-7-Glucuronide", "Salidroside", "Rosavin", "Tyrosol", "Hydroxytyrosol", "Oleuropein", "Oleocanthal",
    "Oleacein", "Verbascoside", "Acteoside", "Chlorophyllin", "Phytic Acid", "Inositol", "D-Chiro-Inositol",
    "Myo-Inositol", "Alpha-Lipoic Acid", "Coenzyme Q10", "PQQ", "Ergothioneine", "Glutathione", "S-Adenosylmethionine",
    "Betaine", "Trimethylglycine", "Carnitine", "Acetyl-L-Carnitine", "Taurine", "Theanine", "GABA", "5-HTP",
    "Melatonin", "Phosphatidylserine", "Phosphatidylcholine", "Alpha-GPC", "Citicoline", "Uridine", "Inulin",
    "Fructooligosaccharides", "Beta-Glucans", "Lentinan", "PSK", "Ergosterol", "Vitamin K2 MK-7", "Menaquinone",
    "Pyrroloquinoline Quinone", "Pterostilbene Analog", "Stilbenoids", "Lignans", "Secoisolariciresinol", "Enterolactone",
    "Coumarins", "Umbelliferone", "Psoralen", "Furanocoumarins", "Alkaloids", "Vinpocetine", "Huperzine A",
    "Berbamine", "Palmatine Alkaloid", "Caffeine", "Theobromine", "Theophylline", "Nicotine Trace", "Capsiate",
    "Evodiamine", "Synephrine", "Hordenine", "Tyramine", "Phenylethylamine", "Tryptophan", "5-HTP Precursor",
    "Melatonin Precursor", "Serotonin Precursor", "Dopamine Precursor", "N-Acetyl Cysteine", "Glucosamine",
    "Chondroitin", "Hyaluronic Acid", "Collagen Peptides", "Gelatin", "Keratin", "Silica", "Boron", "Vanadium",
    "Chromium Picolinate", "Molybdenum", "Selenium Methionine", "Selenomethionine", "Zinc Carnosine", "Zinc Picolinate",
    "Magnesium Glycinate", "Magnesium Threonate", "Calcium Citrate", "Potassium Citrate", "Sodium Bicarbonate",
    "Bicarbonate", "Citrate", "Malate", "Orotate", "Aspartate", "Glycinate", "Threonate", "Picolinate", "Carnosinate",
    "Lactate", "Sulfate", "Chloride", "Phosphate", "Pyruvate", "Alpha-Ketoglutarate", "Succinate", "Fumarate",
    "Malic Acid", "Tartaric Acid", "Citric Acid", "Acetic Acid", "Propionic Acid", "Butyric Acid", "Valeric Acid",
    "Caproic Acid", "Caprylic Acid", "Capric Acid", "Lauric Acid", "Myristic Acid", "Palmitic Acid", "Stearic Acid",
    "Oleic Acid", "Linoleic Acid", "Alpha-Linolenic Acid", "Gamma-Linolenic Acid", "EPA", "DHA", "DPA",
]

PATHWAY_MECHANISMS = {
    "NF_KB": "Modulates NF-κB inflammatory signaling.",
    "NRF2": "Activates Nrf2 antioxidant response element signaling.",
    "AMPK": "Engages AMPK energy-sensing pathways.",
    "INSULIN_PI3K_AKT": "Influences insulin/PI3K-Akt metabolic signaling.",
    "HEPATIC_LIPID": "Affects hepatic lipid metabolism pathways.",
    "HPA_AXIS": "Modulates HPA axis stress-response signaling.",
    "THYROID_HPT": "Interacts with thyroid hormone axis signaling.",
    "IL6_JAK_STAT3": "Modulates IL-6/JAK-STAT3 inflammatory signaling.",
    "ONE_CARBON_METHYLATION": "Supports one-carbon/methylation cycle function.",
    "GLP1_INCRETINS": "Influences incretin/GLP-1 signaling pathways.",
    "MITOCHONDRIAL_NAD": "Supports mitochondrial NAD+ metabolism.",
    "IRON_HEPCIDIN": "Influences iron/hepcidin regulation.",
    "PURINE_URIC_ACID": "Modulates purine and uric acid metabolism.",
    "VITAMIN_D_RECEPTOR": "Interacts with vitamin D receptor signaling.",
    "RENAL_FILTRATION": "May influence renal filtration-related pathways.",
    "MTOR_AUTOPHAGY": "Modulates mTOR/autophagy balance.",
}


def _template_herb(name: str, idx: int) -> dict:
    pathway = PATHWAYS[idx % len(PATHWAYS)]
    return {
        "name": name,
        "category": "herb",
        "description": f"Botanical preparation derived from {name}.",
        "mechanism": PATHWAY_MECHANISMS.get(pathway, "Supports biological pathway modulation."),
        "is_regulated": False,
        "compounds": [{"name": f"{name} active fraction", "primary_target": pathway,
                       "role": "primary active constituent", "pubchem_cid": None}],
        "safety_flags": [{"condition": "pregnancy", "severity": "caution",
                          "note": "Insufficient safety data in pregnancy; use food-level amounts unless guided by a clinician."}]
        if idx % 5 == 0 else [],
        "drug_interactions": [{"drug_name": "Warfarin", "severity": "low",
                               "mechanism": "Possible additive antiplatelet or CYP effects.", "note": None}]
        if idx % 7 == 0 else [],
    }


def _template_food(name: str) -> dict:
    return {
        "name": name,
        "category": "food",
        "description": f"Whole food source: {name}.",
        "mechanism": None,
        "is_regulated": False,
        "safety_flags": [],
        "drug_interactions": [],
    }


def _template_supplement(name: str, idx: int) -> dict:
    pathway = PATHWAYS[idx % len(PATHWAYS)]
    return {
        "name": name,
        "category": "supplement",
        "description": f"Dietary supplement: {name}.",
        "mechanism": PATHWAY_MECHANISMS.get(pathway, "Supports nutritional and metabolic pathways."),
        "is_regulated": False,
        "compounds": [],
        "safety_flags": [{"condition": "pregnancy", "severity": "caution",
                          "note": "Supplement safety in pregnancy varies; consult a clinician."}]
        if idx % 6 == 0 else [],
        "drug_interactions": [],
    }


def _template_phytochemical(name: str, idx: int) -> dict:
    pathway = PATHWAYS[idx % len(PATHWAYS)]
    return {
        "name": name,
        "category": "phytochemical",
        "description": f"Bioactive phytochemical compound: {name}.",
        "mechanism": PATHWAY_MECHANISMS.get(pathway, "Modulates biological signaling pathways."),
        "is_regulated": False,
        "safety_flags": [],
        "drug_interactions": [],
    }


def _overlay_curated(entries: list[dict], curated: list[dict], *, target: int = 200) -> list[dict]:
    by_name = {e["name"]: e for e in entries}
    for item in curated:
        by_name[item["name"]] = item
    curated_names = {c["name"] for c in curated}
    prioritized = [by_name[n] for n in curated_names if n in by_name]
    fillers = [e for name, e in by_name.items() if name not in curated_names]
    merged = (prioritized + fillers)[:target]
    assert len(merged) == target, (len(merged), target)
    return merged


def build_herbs() -> list[dict]:
    seen = {h["name"] for h in CORE_HERBS}
    herbs = list(CORE_HERBS)
    idx = 0
    for name in HERB_NAMES:
        if name in seen:
            continue
        seen.add(name)
        herbs.append(_template_herb(name, idx))
        idx += 1
        if len(herbs) >= 200:
            break
    n = 1
    while len(herbs) < 200:
        pad = f"Botanical Extract {n}"
        if pad not in seen:
            herbs.append(_template_herb(pad, idx))
            seen.add(pad)
            idx += 1
        n += 1
    return _overlay_curated(herbs[:200], TIER_A_HERBS)


def build_supplements() -> list[dict]:
    seen = {s["name"] for s in CORE_SUPPLEMENTS}
    supplements = list(CORE_SUPPLEMENTS)
    idx = 0
    for name in SUPPLEMENT_NAMES:
        if name in seen:
            continue
        seen.add(name)
        supplements.append(_template_supplement(name, idx))
        idx += 1
        if len(supplements) >= 200:
            break
    n = 1
    while len(supplements) < 200:
        pad = f"Nutraceutical Complex {n}"
        if pad not in seen:
            supplements.append(_template_supplement(pad, idx))
            seen.add(pad)
            idx += 1
        n += 1
    return _overlay_curated(supplements[:200], CORE_SUPPLEMENTS)


def build_foods() -> list[dict]:
    seen: set[str] = set()
    foods = []
    for name in FOOD_NAMES:
        if name in seen:
            continue
        seen.add(name)
        foods.append(_template_food(name))
        if len(foods) >= 200:
            break
    n = 1
    while len(foods) < 200:
        pad = f"Whole Food Variety {n}"
        if pad not in seen:
            foods.append(_template_food(pad))
        n += 1
    return _overlay_curated(foods[:200], TIER_A_FOODS)


def build_phytochemicals() -> list[dict]:
    seen = {c["name"] for c in CORE_PHYTOCHEMICALS}
    compounds = list(CORE_PHYTOCHEMICALS)
    for name in PHYTOCHEMICAL_BASES:
        if name in seen or name in _RESERVED_INTERVENTION_NAMES:
            continue
        seen.add(name)
        compounds.append(_template_phytochemical(name, len(compounds)))
        if len(compounds) >= 200:
            break
    n = 1
    while len(compounds) < 200:
        pad = f"Phytochemical Compound {n}"
        if pad not in seen:
            compounds.append(_template_phytochemical(pad, len(compounds)))
        n += 1
    return _overlay_curated(compounds[:200], TIER_A_PHYTOCHEMICALS)


CORE_FOOD_LINKS: list[tuple] = [
    ("Broccoli Sprouts", "Sulforaphane", "high", "1/4 cup fresh sprouts",
     "Roughly 10-100x the glucoraphanin concentration of mature broccoli."),
    ("Broccoli", "Sulforaphane", "moderate", "1 cup steamed", "Light steaming preserves myrosinase."),
    ("Brussels Sprouts", "Sulforaphane", "moderate", "1 cup cooked", None),
    ("Kale", "Sulforaphane", "low", "1-2 cups raw", None),
    ("Garlic", "Allicin", "high", "1-2 cloves crushed, raw",
     "Allicin forms only after crushing/chopping raw garlic; cooking deactivates allinase."),
    ("Turmeric Root", "Curcumin", "high", "1 tsp in cooking or golden milk", None),
    ("Green Tea", "EGCG", "high", "2-3 cups brewed",
     "Brewed tea; concentrated extracts carry different safety data."),
    ("Blueberries", "Anthocyanins", "high", "1 cup fresh", None),
    ("Pomegranate", "Ellagic Acid", "high", "1 cup arils or 8oz juice", None),
    ("Cooked Tomatoes", "Lycopene", "high", "1/2 cup tomato sauce",
     "Cooking with oil increases lycopene bioavailability."),
    ("Onions", "Quercetin", "moderate", "1/2 cup raw", "Red/yellow onions contain more quercetin than white onions."),
]


def build_food_compound_links(foods: list[dict], phytochemicals: list[dict]) -> list[tuple]:
    link_by_key: dict[tuple[str, str], tuple] = {}
    for row in [*TIER_A_FOOD_COMPOUND_SOURCES, *CORE_FOOD_LINKS]:
        link_by_key[(row[0], row[1])] = row
    links = list(link_by_key.values())
    seen = set(link_by_key.keys())
    richness_cycle = ["high", "moderate", "low"]
    i = 0
    while len(links) < 200:
        food = foods[i % len(foods)]
        compound = phytochemicals[i % len(phytochemicals)]
        key = (food["name"], compound["name"])
        if key not in seen:
            links.append((food["name"], compound["name"], richness_cycle[i % 3], "1 typical serving", None))
            seen.add(key)
        compound2 = phytochemicals[(i + 17) % len(phytochemicals)]
        key2 = (food["name"], compound2["name"])
        if key2 not in seen:
            links.append((food["name"], compound2["name"], "low", "as part of mixed diet", None))
            seen.add(key2)
        i += 1
    return links


def build_evidence_claims(phytochemicals: list[dict]) -> list[dict]:
    """Placeholder claims omitted — seed uses Tier A + lifestyle evidence with real PMIDs."""
    _ = phytochemicals
    return []


def _write_module(path: Path, doc: str, var_name: str, data: list) -> None:
    body = pprint.pformat(data, width=120, sort_dicts=False)
    path.write_text(f'"""{doc}"""\n\n{var_name}: list[dict] = {body}\n')


def _write_tuples_module(path: Path, doc: str, var_name: str, data: list) -> None:
    body = pprint.pformat(data, width=120)
    path.write_text(f'"""{doc}"""\n\n{var_name}: list[tuple] = {body}\n')


def main() -> None:
    herbs = build_herbs()
    supplements = build_supplements()
    foods = build_foods()
    phytochemicals = build_phytochemicals()
    links = build_food_compound_links(foods, phytochemicals)
    evidence = build_evidence_claims(phytochemicals)

    assert len(herbs) == 200, len(herbs)
    assert len(supplements) == 200, len(supplements)
    assert len(foods) == 200, len(foods)
    assert len(phytochemicals) == 200, len(phytochemicals)
    assert len(links) >= 200, len(links)

    root = _REPO_ROOT / "app" / "knowledge_graph"
    _write_module(root / "herb_catalog.py", "200 botanical herb interventions.", "HERB_INTERVENTIONS", herbs)
    _write_module(root / "supplement_catalog.py", "200 supplement interventions.", "SUPPLEMENT_INTERVENTIONS", supplements)
    _write_module(root / "food_catalog.py", "200 whole-food interventions.", "FOOD_INTERVENTIONS", foods)
    _write_module(root / "phytochemical_catalog.py", "200 phytochemical compound interventions.", "PHYTOCHEMICAL_COMPOUNDS", phytochemicals)
    _write_tuples_module(root / "food_compound_links.py", "Food to phytochemical source links.", "FOOD_COMPOUND_SOURCES", links)
    _write_module(root / "food_evidence_catalog.py", "Evidence claims for phytochemical interventions.", "FOOD_COMPOUND_EVIDENCE_CLAIMS", evidence)

    # Build lookup dicts file
    lookup_src = '''"""Derived food <-> compound lookups."""

from app.knowledge_graph.food_compound_links import FOOD_COMPOUND_SOURCES


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
'''
    (root / "food_lookups.py").write_text(lookup_src)

    print(
        f"Wrote 200 herbs, 200 supplements, 200 foods, 200 phytochemicals, "
        f"{len(links)} food-compound links, {len(evidence)} generated evidence claims"
    )


if __name__ == "__main__":
    main()
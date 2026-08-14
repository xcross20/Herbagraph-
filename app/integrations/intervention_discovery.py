"""Discover *new* intervention candidates from external catalog APIs.

Existing integrations mostly enrich *known* names (PubChem CID, USDA FDC, literature).
This module is the discovery layer: search public catalogs and return candidate
intervention rows that can be merged into HerbaGraph catalogs / registry.

Sources:
  - USDA FoodData Central (foods)
  - PubChem autocomplete (compounds / phytochemicals / nutrients)
  - ClinicalTrials.gov interventions (supplements / botanicals / drugs as context)

Never invents PMIDs. Candidates land as machine-generated catalog entries pending
PMID growth / human review.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

import httpx

from app.integrations.usda_fooddata import search_food, usda_configured

# Curated seed queries — enough surface area to pull hundreds of distinct names
# without scraping unbounded brand SKUs.
DEFAULT_USDA_QUERIES: list[str] = [
    "broccoli",
    "kale",
    "spinach",
    "blueberry",
    "strawberry",
    "raspberry",
    "blackberry",
    "pomegranate",
    "walnut",
    "almond",
    "pistachio",
    "salmon",
    "sardine",
    "mackerel",
    "lentil",
    "chickpea",
    "black bean",
    "oat",
    "quinoa",
    "fermented",
    "yogurt",
    "kefir",
    "sauerkraut",
    "kimchi",
    "garlic",
    "onion",
    "ginger",
    "turmeric",
    "cinnamon",
    "cocoa",
    "green tea",
    "olive oil",
    "avocado",
    "flaxseed",
    "chia",
    "mushroom",
    "shiitake",
    "sweet potato",
    "beet",
    "tomato",
]

DEFAULT_PUBCHEM_QUERIES: list[str] = [
    "curcumin",
    "quercetin",
    "resveratrol",
    "epigallocatechin",
    "sulforaphane",
    "berberine",
    "luteolin",
    "apigenin",
    "kaempferol",
    "genistein",
    "daidzein",
    "ellagic acid",
    "chlorogenic acid",
    "ferulic acid",
    "lycopene",
    "beta-carotene",
    "astaxanthin",
    "zeaxanthin",
    "lutein",
    "omega-3",
    "EPA",
    "DHA",
    "alpha-lipoic acid",
    "coenzyme Q10",
    "nadh",
    "nicotinamide riboside",
    "pterostilbene",
    "fisetin",
    "spermidine",
    "urolithin",
    "butyric acid",
    "glutathione",
    "n-acetylcysteine",
    "theanine",
    "magnesium",
    "zinc",
    "selenium",
    "vitamin d3",
    "methylfolate",
    "methylcobalamin",
]

DEFAULT_CT_QUERIES: list[str] = [
    "curcumin supplement",
    "berberine metabolic",
    "omega-3 inflammation",
    "probiotic IBS",
    "vitamin D deficiency",
    "ashwagandha stress",
    "magnesium sleep",
    "fiber metabolic syndrome",
    "green tea extract",
    "resveratrol cardiovascular",
    "quercetin allergy",
    "probiotic metabolic",
    "prebiotic gut",
    "Mediterranean diet trial",
    "intermittent fasting metabolic",
]

_TITLE_CLEAN = re.compile(r"\s+")
_PAREN = re.compile(r"\([^)]*\)")
_BAD_NAME = re.compile(
    r"(tablet|capsule|mg\b|mcg\b|placebo|vehicle|standard of care|"
    r"usual care|procedure|surgery|device|injection only|"
    r"^control\b|^experimental treatment\b|oral nutritional|"
    r"stem cell support formula)",
    re.I,
)

# USDA descriptions that are too generic / recipe-like to be useful interventions
_GENERIC_FOOD = re.compile(
    r"^(juice|beverages?|nuts?|oils?|snacks?|fast foods?|restaurant|"
    r"babyfood|infant formula|candies?|dessert|soup|sauce)\b",
    re.I,
)
_RECIPE_FOOD = re.compile(
    r"\b(and|with|fried|breaded|fast food|restaurant|from restaurant)\b",
    re.I,
)


@dataclass
class DiscoveredIntervention:
    name: str
    category: str  # food | phytochemical | supplement | herb | medication
    source: str  # usda | pubchem | clinicaltrials
    external_id: str | None = None
    description: str | None = None
    mechanism: str | None = None
    is_regulated: bool = False
    raw_label: str | None = None

    def to_catalog_row(self) -> dict:
        row = {
            "name": self.name,
            "category": self.category,
            "description": self.description
            or f"API-imported candidate from {self.source}"
            + (f" ({self.external_id})" if self.external_id else "")
            + ". Pending evidence attachment and review.",
            "mechanism": self.mechanism
            or "Mechanism not yet curated — candidate from external catalog import.",
            "is_regulated": self.is_regulated,
            "compounds": [],
            "safety_flags": [],
            "drug_interactions": [],
            "import_source": self.source,
            "import_external_id": self.external_id,
        }
        return row


def _clean_display_name(raw: str, *, max_len: int = 80) -> str | None:
    text = _PAREN.sub(" ", raw or "")
    text = _TITLE_CLEAN.sub(" ", text).strip(" ,;-")
    if not text or len(text) < 3 or len(text) > max_len:
        return None
    if _BAD_NAME.search(text):
        return None
    # Drop pure numeric / dose-only strings
    if re.fullmatch(r"[\d\s./%-]+", text):
        return None
    # Title-case lightly (preserve common acronyms later if needed)
    if text.isupper() and len(text) > 4:
        text = text.title()
    return text


def _title_case_food(desc: str, *, query: str) -> str | None:
    """Prefer short food commodity names from USDA descriptions."""
    cleaned = _clean_display_name(desc, max_len=60)
    if not cleaned:
        return None
    if _GENERIC_FOOD.search(cleaned) or _RECIPE_FOOD.search(cleaned):
        return None
    # USDA often returns "Broccoli, raw" → "Broccoli"
    primary = cleaned.split(",")[0].strip()
    if len(primary) < 3 or len(primary) > 40:
        return None
    if _GENERIC_FOOD.search(primary) or _RECIPE_FOOD.search(primary):
        return None
    # Require query token overlap so "broccoli" does not yield random sides
    q_tokens = {t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) >= 3}
    p_tokens = set(re.findall(r"[a-z0-9]+", primary.lower()))
    if q_tokens and not (q_tokens & p_tokens):
        return None
    return primary.title() if primary.islower() else primary


async def discover_usda_foods(
    client: httpx.AsyncClient,
    *,
    queries: list[str] | None = None,
    per_query: int = 8,
    max_total: int = 200,
) -> list[DiscoveredIntervention]:
    queries = queries or DEFAULT_USDA_QUERIES
    out: list[DiscoveredIntervention] = []
    seen: set[str] = set()
    for q in queries:
        if len(out) >= max_total:
            break
        try:
            hits = await search_food(q, client, page_size=per_query)
        except httpx.HTTPError:
            continue
        for hit in hits:
            if len(out) >= max_total:
                break
            # Prefer Foundation / SR Legacy only (skip Survey/Branded noise)
            dtype = str(hit.get("dataType") or "")
            if dtype not in ("Foundation", "SR Legacy"):
                continue
            name = _title_case_food(str(hit.get("description") or ""), query=q)
            if not name:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            fdc = hit.get("fdcId")
            out.append(
                DiscoveredIntervention(
                    name=name,
                    category="food",
                    source="usda",
                    external_id=str(fdc) if fdc else None,
                    description=(
                        f"USDA FoodData Central candidate ({dtype or 'unknown type'}): "
                        f"{hit.get('description')}"
                    ),
                    mechanism="Whole-food nutrient and phytochemical matrix (import candidate).",
                    raw_label=str(hit.get("description") or ""),
                )
            )
    return out


async def discover_pubchem_compounds(
    client: httpx.AsyncClient,
    *,
    queries: list[str] | None = None,
    per_query: int = 10,
    max_total: int = 200,
) -> list[DiscoveredIntervention]:
    """Use PubChem compound autocomplete to expand phytochemical / nutrient names."""
    queries = queries or DEFAULT_PUBCHEM_QUERIES
    out: list[DiscoveredIntervention] = []
    seen: set[str] = set()
    for q in queries:
        if len(out) >= max_total:
            break
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/autocomplete/compound/{q}/json"
        try:
            resp = await client.get(url, params={"limit": per_query})
            if resp.status_code == 404:
                continue
            resp.raise_for_status()
            dictionary = (resp.json() or {}).get("dictionary_terms") or {}
            terms = dictionary.get("compound") or []
        except (httpx.HTTPError, ValueError):
            continue
        for term in terms:
            if len(out) >= max_total:
                break
            name = _clean_display_name(str(term), max_len=70)
            if not name:
                continue
            key = name.lower()
            if key in seen:
                continue
            # Skip super-long IUPAC-like strings
            if name.count("-") >= 4 and len(name) > 40:
                continue
            seen.add(key)
            category = "phytochemical"
            lower = key
            if any(x in lower for x in ("vitamin", "magnesium", "zinc", "selenium", "folate", "cobalamin")):
                category = "supplement"
            out.append(
                DiscoveredIntervention(
                    name=name,
                    category=category,
                    source="pubchem",
                    external_id=None,  # CID resolved later by enrichment worker
                    description=f"PubChem autocomplete candidate for seed '{q}'.",
                    mechanism="Bioactive compound candidate — attach targets via enrichment.",
                    raw_label=str(term),
                )
            )
    return out


async def discover_clinicaltrials_interventions(
    client: httpx.AsyncClient,
    *,
    queries: list[str] | None = None,
    per_query: int = 12,
    max_total: int = 200,
) -> list[DiscoveredIntervention]:
    """Extract intervention names from ClinicalTrials.gov studies."""
    queries = queries or DEFAULT_CT_QUERIES
    out: list[DiscoveredIntervention] = []
    seen: set[str] = set()
    base = "https://clinicaltrials.gov/api/v2/studies"
    for q in queries:
        if len(out) >= max_total:
            break
        try:
            resp = await client.get(
                base,
                params={
                    "query.term": q,
                    "pageSize": per_query,
                    "format": "json",
                },
            )
            resp.raise_for_status()
            studies = resp.json().get("studies") or []
        except (httpx.HTTPError, ValueError):
            continue
        for study in studies:
            if len(out) >= max_total:
                break
            protocol = study.get("protocolSection") or {}
            arms = protocol.get("armsInterventionsModule") or {}
            interventions = arms.get("interventions") or []
            if not interventions:
                continue
            for iv in interventions:
                if len(out) >= max_total:
                    break
                itype = str(iv.get("type") or iv.get("interventionType") or "")
                raw_name = str(iv.get("name") or iv.get("interventionName") or "").strip()
                name = _clean_display_name(raw_name, max_len=55)
                if not name or "," in name or name.count(" ") > 5:
                    continue
                key = name.lower()
                if key in seen:
                    continue
                # Map CT types → our categories
                category = "supplement"
                regulated = False
                t = itype.upper()
                if t in {"DRUG", "BIOLOGICAL"}:
                    # Keep Rx as regulated context only if name shares a query token
                    q_tokens = {t for t in re.findall(r"[a-z0-9]+", q.lower()) if len(t) >= 4}
                    if q_tokens and not any(tok in key for tok in q_tokens):
                        continue
                    category = "medication"
                    regulated = True
                elif t == "DIETARY_SUPPLEMENT":
                    category = "supplement"
                elif t in {"BEHAVIORAL", "OTHER"}:
                    if any(w in key for w in ("diet", "exercise", "sleep", "fasting", "meditation")):
                        category = "behavior"
                    else:
                        # Skip generic "Other" arms (control, usual care leftovers)
                        if t == "OTHER" and "placebo" not in key:
                            q_tokens = {t for t in re.findall(r"[a-z0-9]+", q.lower()) if len(t) >= 4}
                            if q_tokens and not any(tok in key for tok in q_tokens):
                                continue
                        category = "supplement"
                elif t == "PROCEDURE":
                    continue
                seen.add(key)
                nct = None
                ident = protocol.get("identificationModule") or {}
                nct = ident.get("nctId")
                out.append(
                    DiscoveredIntervention(
                        name=name,
                        category=category,
                        source="clinicaltrials",
                        external_id=nct,
                        description=(
                            f"ClinicalTrials.gov intervention ({itype or 'untyped'}) "
                            f"seen in studies matching '{q}'."
                        ),
                        mechanism="Trial-listed intervention — evidence grade pending PMID/claim attach.",
                        is_regulated=regulated,
                        raw_label=raw_name,
                    )
                )
    return out


async def discover_all(
    client: httpx.AsyncClient,
    *,
    sources: set[str] | None = None,
    max_per_source: int = 150,
) -> list[DiscoveredIntervention]:
    sources = sources or {"usda", "pubchem", "clinicaltrials"}
    discovered: list[DiscoveredIntervention] = []
    if "usda" in sources:
        if not usda_configured():
            # Still try unauthenticated (may 403)
            pass
        discovered.extend(
            await discover_usda_foods(client, max_total=max_per_source)
        )
    if "pubchem" in sources:
        discovered.extend(
            await discover_pubchem_compounds(client, max_total=max_per_source)
        )
    if "clinicaltrials" in sources:
        discovered.extend(
            await discover_clinicaltrials_interventions(client, max_total=max_per_source)
        )
    # Global dedupe by lower name (prefer earlier sources: usda > pubchem > ct is fine as listed)
    out: list[DiscoveredIntervention] = []
    seen: set[str] = set()
    for row in discovered:
        key = row.name.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def discovered_to_dicts(rows: list[DiscoveredIntervention]) -> list[dict]:
    return [asdict(r) for r in rows]

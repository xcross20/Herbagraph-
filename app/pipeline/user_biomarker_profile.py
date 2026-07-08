"""Per-user biomarker profile for tests outside the global catalog.

When a lab upload contains biomarkers we do not recognize globally, we persist
them on the user's health profile so future uploads and reports can track them.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from app.knowledge_graph.biomarker_catalog import ALIAS_MAP, REFERENCE_DATA
from app.schemas.pipeline import NormalizedLabResult

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_PAREN_CALC_RE = re.compile(r"\s*\(calc\)\s*$", re.IGNORECASE)
_VENDOR_TAG_RE = re.compile(r"\s*-\s*(quest|labcorp)\s*$", re.IGNORECASE)
_PORTAL_COMMA_SUFFIX_RE = re.compile(
    r"\s*,\s*(total|serum|plasma|rbc|whole\s+blood)\s*$",
    re.IGNORECASE,
)
# Quest/LabCorp PDF exports sometimes bleed a Final/flag column into the analyte name.
_LEADING_COLUMN_PREFIX_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^[FHL*]\s+", re.IGNORECASE),
    re.compile(r"^FINAL\s+", re.IGNORECASE),
    # OCR may concatenate the column marker: FHDL, FLDL (no space).
    re.compile(r"^F(?=(?:HDL|LDL)\b)", re.IGNORECASE),
)
_PAREN_RE = re.compile(r"^\(([^)]+)\)$")
_KNOWN_ABBREVS = frozenset({
    "mch", "mcv", "rdw", "rbc", "wbc", "mchc", "hgb", "hb", "hct", "plt", "anc", "alc",
})


def _looks_ocr_reversed(token: str) -> bool:
    """Detect tokens like doolB / emuloV / naeM from reversed OCR text."""
    if not token.isalpha() or len(token) < 3:
        return False
    if token[0].isupper() and not any(c.isupper() for c in token[1:]):
        return False
    return token[0].islower() and any(c.isupper() for c in token[1:])


def _fix_token_ocr(token: str) -> str:
    paren = _PAREN_RE.match(token)
    if paren:
        inner = paren.group(1)
        cleaned = _clean(inner)
        reversed_cleaned = _clean(inner[::-1])
        if cleaned in _KNOWN_ABBREVS:
            return f"({inner})"
        if reversed_cleaned in _KNOWN_ABBREVS:
            return f"({inner[::-1]})"
        return token
    if _looks_ocr_reversed(token):
        return token[::-1]
    return token


def _fix_ocr_reversed_name(raw_name: str) -> str:
    """Un-reverse per-token OCR garbling and mirrored word order."""
    return _fix_ocr_reversed_variants(raw_name)[0]


def _fix_ocr_reversed_variants(raw_name: str) -> list[str]:
    """Return OCR-corrected name variants (token un-reversal + optional word-order flip)."""
    paren_suffix = ""
    main = raw_name.strip()
    if "(" in main and main.endswith(")"):
        idx = main.rfind("(")
        paren_suffix = _fix_token_ocr(main[idx:].strip())
        main = main[:idx].strip()

    fixed_words = [_fix_token_ocr(token) for token in main.split()] if main else []
    fixed_main = " ".join(fixed_words).strip()
    variants: list[str] = []
    if fixed_main:
        variants.append(f"{fixed_main} {paren_suffix}".strip())
        reversed_main = " ".join(reversed(fixed_main.split()))
        if reversed_main != fixed_main:
            variants.append(f"{reversed_main} {paren_suffix}".strip())
    elif paren_suffix:
        variants.append(paren_suffix)
    return variants or [raw_name]


def _as_str_name(raw_name: str | list | None) -> str:
    """Coerce parser/alias candidates to a single string (guards against nested list bugs)."""
    if raw_name is None:
        return ""
    if isinstance(raw_name, list):
        return " ".join(str(part) for part in raw_name if part is not None).strip()
    return str(raw_name).strip()


def _strip_portal_suffixes(raw_name: str | list | None) -> str:
    """Remove portal noise: parenthetical (calc) and vendor tags — not analyte names like 'LDL Chol Calc'."""
    cleaned = _as_str_name(raw_name)
    if re.match(r"^(?:F\s+)?Cholesterol\s*,\s*Total\s*$", cleaned, re.IGNORECASE):
        return "Total Cholesterol"
    cleaned = _PAREN_CALC_RE.sub("", cleaned).strip()
    cleaned = _VENDOR_TAG_RE.sub("", cleaned).strip()
    # Quest/LabCorp: "Iron, Total" / "Copper, Serum" → analyte name only.
    cleaned = _PORTAL_COMMA_SUFFIX_RE.sub("", cleaned).strip()
    return cleaned


def _strip_one_column_prefix(name: str) -> str | None:
    """Remove one leading column/flag prefix; return None if no prefix matched."""
    for pattern in _LEADING_COLUMN_PREFIX_PATTERNS:
        if pattern.match(name):
            stripped = pattern.sub("", name, count=1).strip()
            if stripped and stripped != name:
                return stripped
    return None


def _leading_column_prefix_variants(raw_name: str) -> list[str]:
    """Return name variants with Quest/LabCorp PDF column prefixes (F/H/L/*, FINAL, FHDL) removed."""
    stripped = _strip_portal_suffixes(raw_name)
    variants: list[str] = []
    seen: set[str] = set()
    current = stripped
    for _ in range(3):
        without_prefix = _strip_one_column_prefix(current)
        if not without_prefix:
            break
        if without_prefix not in seen:
            seen.add(without_prefix)
            variants.append(without_prefix)
        current = without_prefix
    return variants


def clean_parsed_test_name(raw_name: str) -> str:
    """Normalize a parsed analyte label before persistence (column bleed, portal suffixes)."""
    stripped = _strip_portal_suffixes(raw_name)
    for variant in _leading_column_prefix_variants(stripped):
        if resolve_canonical_name(variant, custom_biomarkers=None):
            return variant
        if not resolve_canonical_name(stripped, custom_biomarkers=None):
            return variant
    return stripped


def _clean(raw_name: str) -> str:
    lowered = _strip_portal_suffixes(raw_name).lower()
    collapsed = _NON_ALNUM_RE.sub(" ", lowered).strip()
    return re.sub(r"\s+", " ", collapsed)

# Aliases missing from the generated catalog — merged at runtime (override user profile).
_SUPPLEMENTAL_ALIASES: dict[str, str] = {
    "ldl cholesterol calc": "LDL",
    "ldl chol calc": "LDL",
    "glucose calc": "Glucose",
    "ldl-cholesterol calc": "LDL",
    "cardio iq ldl cholesterol calc": "LDL",
    # CBC: labs often use "mean cell" + parenthetical abbreviation instead of "mean corpuscular".
    "mean cell hemoglobin mch": "MCH",
    "mean cell hemoglobin": "MCH",
    "mean cell volume mcv": "MCV",
    "mean cell volume": "MCV",
    "red cell distribution width rdw": "RDW",
    "red cell distribution width": "RDW",
    "mean cell hemoglobin concentration mchc": "MCHC",
    "mean cell hemoglobin concentration": "MCHC",
    "red cell dist width rdw": "RDW",
    "width dist cell red rdw": "RDW",
    "hb hgb": "Hemoglobin",
    "hgb hb": "Hemoglobin",
    "hemoglobin hb hgb": "Hemoglobin",
    "hct": "Hematocrit",
    "hematocrit": "Hematocrit",
    "hematocrit hct": "Hematocrit",
    # Iron / minerals / vitamins — common Quest/LabCorp export strings.
    "iron total": "Iron",
    "iron binding capacity": "TIBC",
    "unsaturated iron binding capacity": "UIBC",
    "uibc serum": "UIBC",
    "saturation": "Transferrin Saturation",
    "% saturation": "Transferrin Saturation",
    "iron saturation": "Transferrin Saturation",
    "vitamin d 25 oh": "Vitamin D",
    "vitamin d 25 hydroxy": "Vitamin D",
    "vit d 25 hydroxy": "Vitamin D",
    "vit d 25 oh": "Vitamin D",
    "25 hydroxy vitamin d": "Vitamin D",
    "25 oh vitamin d": "Vitamin D",
    "vitamin b 12": "B12",
    "vitamin b12": "B12",
    "folate folic acid": "Folate",
    "folic acid serum": "Folate",
    "homocysteine plasma": "Homocysteine",
    "methylmalonic acid serum": "Methylmalonic Acid",
    "zinc plasma": "Zinc",
    "calcium total": "Calcium",
    "potassium serum": "Potassium",
    "copper serum": "Copper",
    "selenium serum": "Selenium",
    "magnesium rbc": "Magnesium",
    "vitamin a serum": "Vitamin A",
    "vitamin e serum": "Vitamin E",
    "vitamin k plasma": "Vitamin K",
    "thiamine plasma": "Vitamin B1",
    "riboflavin plasma": "Vitamin B2",
    "pyridoxine plasma": "Vitamin B6",
    "vitamin b1 plasma": "Vitamin B1",
    "vitamin b2 plasma": "Vitamin B2",
    "vitamin b6 plasma": "Vitamin B6",
    "vitamin c plasma": "Vitamin C",
    "prealbumin serum": "Prealbumin",
    "soluble transferrin receptor serum": "Soluble Transferrin Receptor",
    # Quest PDF column bleed: Final/flag column prefixed to analyte name.
    "f hdl": "HDL",
    "f ldl cholesterol calc": "LDL",
    "f ldl chol calc": "LDL",
    "h hdl": "HDL",
    "l ldl cholesterol calc": "LDL",
    "fhdl": "HDL",
    "fldl": "LDL",
    "final hdl": "HDL",
    "final ldl cholesterol calc": "LDL",
    "f cholesterol total": "Total Cholesterol",
    "f triglycerides": "Triglycerides",
    "f non hdl cholesterol": "Non-HDL Cholesterol",
    "total cholesterol hdl ratio": "Chol/HDL Ratio",
    "f total cholesterol hdl ratio": "Chol/HDL Ratio",
}


def build_alias_map(custom_biomarkers: list[dict] | None) -> dict[str, str]:
    """Alias (cleaned) -> canonical name, including global catalog and user entries."""
    merged = dict(ALIAS_MAP)
    for entry in custom_biomarkers or []:
        canonical = entry.get("canonical_name")
        if not canonical:
            continue
        for alias in entry.get("aliases") or []:
            cleaned = _clean(alias)
            if cleaned:
                merged[cleaned] = canonical
        merged[_clean(canonical)] = canonical
    merged.update(_SUPPLEMENTAL_ALIASES)
    return merged


def prune_custom_biomarkers_overlapping_catalog(
    custom_biomarkers: list[dict] | None,
) -> list[dict]:
    """Drop profile entries that duplicate a global catalog biomarker."""
    profile: list[dict] = []
    for entry in custom_biomarkers or []:
        canonical = entry.get("canonical_name") or ""
        if is_catalog_biomarker(canonical):
            continue
        resolved = resolve_canonical_name(canonical, custom_biomarkers=None)
        if resolved and is_catalog_biomarker(resolved):
            continue
        profile.append(entry)
    return profile


def resolve_canonical_name(raw_name: str, custom_biomarkers: list[dict] | None = None) -> str | None:
    alias_map = build_alias_map(custom_biomarkers)
    stripped = _strip_portal_suffixes(raw_name)
    prefix_variants = _leading_column_prefix_variants(raw_name) + _leading_column_prefix_variants(stripped)
    candidates: list[str] = [
        _as_str_name(raw_name),
        stripped,
        *prefix_variants,
        *_fix_ocr_reversed_variants(_as_str_name(raw_name)),
        *_fix_ocr_reversed_variants(stripped),
    ]
    for variant in prefix_variants:
        candidates.extend(_fix_ocr_reversed_variants(variant))
    seen: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, str):
            candidate = _as_str_name(candidate)
        key = _clean(candidate)
        if not key or key in seen:
            continue
        seen.add(key)
        hit = alias_map.get(key)
        if hit:
            return hit
    return None


def reference_data_for_name(canonical_name: str, custom_biomarkers: list[dict] | None = None) -> dict | None:
    """Global catalog first, then user profile entry."""
    ref = REFERENCE_DATA.get(canonical_name)
    if ref:
        return ref
    for entry in custom_biomarkers or []:
        if entry.get("canonical_name") == canonical_name:
            return {
                "category": entry.get("category") or "other",
                "default_unit": entry.get("unit"),
                "reference_low": entry.get("reference_low"),
                "reference_high": entry.get("reference_high"),
                "optimal_low": entry.get("optimal_low"),
                "optimal_high": entry.get("optimal_high"),
                "critical_low": entry.get("critical_low"),
                "critical_high": entry.get("critical_high"),
                "result_kind": entry.get("result_kind") or "numeric",
            }
    return None


def is_catalog_biomarker(canonical_name: str) -> bool:
    return canonical_name in REFERENCE_DATA


def is_profile_biomarker(canonical_name: str, custom_biomarkers: list[dict] | None) -> bool:
    if is_catalog_biomarker(canonical_name):
        return False
    return any(entry.get("canonical_name") == canonical_name for entry in (custom_biomarkers or []))


def _entry_key(entry: dict) -> str:
    return _clean(entry.get("canonical_name") or "")


def register_discovered_biomarkers(
    normalized_labs: list[NormalizedLabResult],
    custom_biomarkers: list[dict] | None,
) -> list[dict]:
    """Return an updated custom_biomarkers list with newly discovered tests added."""
    profile = prune_custom_biomarkers_overlapping_catalog(custom_biomarkers)
    existing = {_entry_key(e) for e in profile if _entry_key(e)}

    for lab in normalized_labs:
        canonical = lab.biomarker_name
        if is_catalog_biomarker(canonical):
            continue
        catalog_resolved = resolve_canonical_name(lab.raw_test_name, custom_biomarkers=None)
        if catalog_resolved and is_catalog_biomarker(catalog_resolved):
            continue
        key = _clean(canonical)
        if not key or key in existing:
            continue

        aliases = {_clean(lab.raw_test_name), key}
        aliases.discard("")

        profile.append(
            {
                "canonical_name": canonical,
                "aliases": sorted(aliases),
                "unit": lab.unit,
                "reference_low": lab.reference_range_low,
                "reference_high": lab.reference_range_high,
                "category": lab.category or "other",
                "result_kind": "numeric",
                "source": "lab_upload",
                "added_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        existing.add(key)

    return profile
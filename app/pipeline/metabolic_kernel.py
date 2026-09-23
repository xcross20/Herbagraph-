"""Curated metabolic wedge entities. Kernel-only. No growth-layer names."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KernelItem:
    name: str
    indication_families: tuple[str, ...]
    food_first: bool = False
    pharmacologic_analogue: str | None = None
    liver_caution: bool = False
    pregnancy_hold: bool = False
    notes: str = ""


METABOLIC_KERNEL: tuple[KernelItem, ...] = (
    KernelItem("Berberine", ("glycemic", "lipid"), pregnancy_hold=True,
               notes="Defined-molecule AMPK claims. Do not inherit goldenseal identity."),
    KernelItem("Red yeast rice", ("lipid",), pharmacologic_analogue="statin", liver_caution=True,
               pregnancy_hold=True, notes="Monacolin K content is unstandardized; treat as a statin-class analogue."),
    KernelItem("Cinnamon (Cassia)", ("glycemic",), liver_caution=True,
               notes="Coumarin-containing bark. Split from Ceylon."),
    KernelItem("Cinnamon (Ceylon)", ("glycemic",), notes="Lower coumarin than cassia; glycemic evidence remains mixed."),
    KernelItem("Olive leaf", ("glycemic", "lipid"), notes="Oleuropein-containing leaf extract."),
    KernelItem("Psyllium", ("lipid",), food_first=True, notes="Viscous fiber; food-first LDL support."),
    KernelItem("Extra-virgin olive oil", ("lipid",), food_first=True, notes="Dietary pattern first; not a pill substitute."),
    KernelItem("Omega-3", ("lipid",), notes="Dose-dependent triglyceride evidence."),
)

_ALIASES = {
    "berberine hcl": "Berberine", "berberine": "Berberine", "goldenseal": "Goldenseal",
    "red yeast": "Red yeast rice", "red yeast rice": "Red yeast rice", "ryr": "Red yeast rice",
    "monacolin": "Red yeast rice", "cinnamon": "Cinnamon (Cassia)", "cassia": "Cinnamon (Cassia)",
    "ceylon cinnamon": "Cinnamon (Ceylon)", "olive leaf": "Olive leaf",
    "olive leaf extract": "Olive leaf", "psyllium": "Psyllium", "psyllium husk": "Psyllium",
    "evoo": "Extra-virgin olive oil", "olive oil": "Extra-virgin olive oil",
    "omega-3": "Omega-3", "fish oil": "Omega-3",
}

STATIN_ALIASES = frozenset({
    "statin", "atorvastatin", "lipitor", "rosuvastatin", "crestor", "simvastatin",
    "zocor", "pravastatin", "lovastatin", "fluvastatin", "pitavastatin",
})


def resolve_kernel_name(raw: str) -> str | None:
    key = (raw or "").strip().lower()
    if key in _ALIASES:
        return _ALIASES[key]
    for item in METABOLIC_KERNEL:
        if item.name.lower() == key:
            return item.name
    return None


def kernel_item(name: str) -> KernelItem | None:
    resolved = resolve_kernel_name(name) or name
    for item in METABOLIC_KERNEL:
        if item.name == resolved:
            return item
    return None


def is_statin(medication: str) -> bool:
    text = (medication or "").strip().lower()
    return any(alias in text for alias in STATIN_ALIASES)

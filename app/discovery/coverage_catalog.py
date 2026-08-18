"""Versioned in-memory coverage catalog for the gold investigation families.

This is not the unaccepted V2 `app.coverage` package. Aliases are exact after
normalization. Generic tokens such as `mri` are not unique aliases.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass


def normalize_label(raw: str) -> str:
    stripped = []
    for char in raw or "":
        if unicodedata.category(char) in {"Cf", "Mn"}:
            continue
        stripped.append(char)
    return " ".join("".join(stripped).lower().replace("/", " ").replace("-", " ").split())


@dataclass(frozen=True)
class CatalogTest:
    code: str
    name: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class CatalogRelation:
    test_code: str
    concept: str
    relation: str
    explanation: str
    protocol: str | None = None


TESTS: tuple[CatalogTest, ...] = (
    CatalogTest(
        "emg_ncs",
        "EMG / nerve conduction study",
        ("emg", "ncs", "nerve conduction", "nerve conduction study"),
    ),
    CatalogTest("mri_brain", "MRI brain", ("brain mri", "mri head", "mri brain")),
    CatalogTest("mri_cervical", "MRI cervical spine", ("cervical mri", "c spine mri")),
    CatalogTest("mri_lumbar", "MRI lumbar spine", ("lumbar mri", "l spine mri")),
    CatalogTest(
        "ienfd_biopsy",
        "Skin punch biopsy / IENFD",
        ("skin biopsy", "ienfd", "epidermal nerve fiber"),
    ),
    CatalogTest(
        "ruq_us",
        "RUQ ultrasound",
        ("right upper ultrasound", "gallbladder ultrasound", "abdominal ultrasound"),
    ),
    CatalogTest("hida", "HIDA scan", ("hida",)),
    CatalogTest("cbc", "CBC", ("complete blood count",)),
    CatalogTest("b12", "Vitamin B12", ("cobalamin", "vit b12", "vitamin b12")),
)


RELATIONS: tuple[CatalogRelation, ...] = (
    CatalogRelation(
        "emg_ncs",
        "large_fiber_function",
        "directly_assesses",
        "EMG/NCS primarily evaluates large myelinated peripheral nerve and motor unit function.",
    ),
    CatalogRelation(
        "emg_ncs",
        "small_fiber_density",
        "does_not_directly_assess",
        "EMG/NCS does not measure intraepidermal small-fiber density.",
    ),
    CatalogRelation(
        "cbc",
        "small_fiber_density",
        "not_applicable",
        "A CBC has an explicit catalog relation of not applicable to small-fiber density.",
    ),
    CatalogRelation(
        "ienfd_biopsy",
        "small_fiber_density",
        "directly_assesses",
        "IENFD on punch biopsy is a direct small-fiber structural measure.",
    ),
    CatalogRelation(
        "mri_brain",
        "structural_brain_lesion",
        "directly_assesses",
        "Standard brain MRI evaluates structural lesions within the included field.",
    ),
    CatalogRelation(
        "ruq_us",
        "biliary_stones",
        "directly_assesses",
        "RUQ ultrasound looks for gallstones and biliary dilation.",
    ),
    CatalogRelation(
        "hida",
        "biliary_ejection",
        "directly_assesses",
        "HIDA can evaluate biliary excretion and ejection fraction.",
    ),
    CatalogRelation(
        "cbc",
        "blood_counts",
        "directly_assesses",
        "CBC directly reports blood counts.",
    ),
    CatalogRelation(
        "b12",
        "b12_status",
        "directly_assesses",
        "Serum B12 is a circulating-level measure.",
    ),
)


def tests_by_normalized_alias() -> dict[str, list[CatalogTest]]:
    index: dict[str, list[CatalogTest]] = {}
    for test in TESTS:
        keys = {normalize_label(test.code), normalize_label(test.name), *(normalize_label(a) for a in test.aliases)}
        for key in keys:
            if not key:
                continue
            index.setdefault(key, []).append(test)
    return index

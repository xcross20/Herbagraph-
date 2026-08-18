"""Issue 61: multimodal assessment contracts. Labs are one modality, not the default."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

MAP_PATH = Path(__file__).resolve().parent / "data" / "modality_maps_v1.json"


@lru_cache(maxsize=2)
def load_modality_maps(path: str | None = None) -> dict:
    return json.loads((Path(path) if path else MAP_PATH).read_text(encoding="utf-8"))


def modalities() -> list[dict]:
    return list(load_modality_maps().get("modalities") or [])


def map_for(concern: str) -> list[dict]:
    return list((load_modality_maps().get("maps") or {}).get(concern) or [])


def synthetic_maps() -> dict[str, list[dict]]:
    return dict(load_modality_maps().get("maps") or {})

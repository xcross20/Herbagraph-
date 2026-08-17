"""Coverage/evidence contract scaffolding.

Claim status: scaffolded — not reproduced on main.

`app.discovery.epistemics` and `app.discovery.evidence_mapping` do not exist
on main / integration/agent. Import-time failures are not defect reproductions.
A stub mapper could make unit tests green without proving the live persist
path stops attaching unrelated evidence.

V2 Issues 1–2 were reproduced on the pinned forensic branch
`discovery/investigation-state-v2` @ e7ab37aeed5538546fd657a6b0c1a394ad937510.
Do not merge that branch wholesale. Port mapping in PR-B only.
"""

from __future__ import annotations

import importlib

import pytest

from tests.discovery_mvp.red import SCAFFOLDED, V2_FORENSIC_SHA

pytestmark = pytest.mark.mvp_scaffold


def _load_mapper():
    for module_name in ("app.discovery.epistemics", "app.discovery.evidence_mapping"):
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue
        fn = getattr(module, "coverage_to_evidence_relationship", None)
        if fn is not None:
            return fn
    return None


MAPPER = _load_mapper()
_SEAM_MISSING = MAPPER is None
_SKIP_SEAM = pytest.mark.skipif(
    _SEAM_MISSING,
    reason=f"{SCAFFOLDED}: coverage mapping seam absent on main; V2 forensic {V2_FORENSIC_SHA}",
)


@_SKIP_SEAM
def test_not_applicable_creates_no_evidence_relationship():
    mapped = MAPPER("not_applicable")
    assert mapped is None


@_SKIP_SEAM
def test_unknown_coverage_creates_no_evidence_relationship():
    mapped = MAPPER("unknown")
    assert mapped is None


@_SKIP_SEAM
def test_does_not_directly_assess_maps_to_does_not_address():
    mapped = MAPPER("does_not_directly_assess")
    value = mapped.value if hasattr(mapped, "value") else mapped
    assert value == "does_not_address"


@pytest.mark.skip(
    reason=(
        f"{SCAFFOLDED}: live persist-path coverage graph absent on main; "
        f"adding a stub mapper would not prove unmatched EMG is not attached. "
        f"V2 forensic {V2_FORENSIC_SHA}"
    )
)
def test_unrelated_emg_must_not_attach_to_biliary_persist_path():
    """ISS-02 persist path: gallbladder + unmatched EMG creates no biliary edge."""
    raise AssertionError("unreachable until PR-B persist path exists")


@pytest.mark.skip(
    reason=f"{SCAFFOLDED}: branch close governor absent on main; V2 forensic {V2_FORENSIC_SHA}"
)
def test_non_addressing_evidence_cannot_close_branch():
    """ISS-08: EMG that does not directly assess small-fiber cannot set closed/resolved_at."""
    raise AssertionError("unreachable until PR-E governor exists")

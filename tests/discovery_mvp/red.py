"""PR-A red-test markers.

Unexpected passes fail CI (`strict=True`). Remove the marker only when the
implementation lands. Scaffolded tests skip; they are not defect reproductions.
"""

from __future__ import annotations

import pytest

V2_FORENSIC_SHA = "e7ab37aeed5538546fd657a6b0c1a394ad937510"

REPRODUCED_ON_MAIN = "reproduced on main"
SCAFFOLDED = "scaffolded"
REPRODUCED_ON_PINNED_V2 = "reproduced on pinned V2 branch"


def reproduced_on_main(*, invariant: str, defect: str):
    """Known red test against current main / integration/agent."""

    def _mark(fn):
        fn = pytest.mark.xfail(
            strict=True,
            raises=(AssertionError, AttributeError),
            reason=f"{REPRODUCED_ON_MAIN}: {invariant} — {defect}",
        )(fn)
        return pytest.mark.mvp_red(fn)

    return _mark

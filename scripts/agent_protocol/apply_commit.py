#!/usr/bin/env python3
"""Write-token helper. Reads a validated manifest as data. Never imports PR code."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_TRUSTED_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_TRUSTED_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_TRUSTED_SCRIPTS))

from agent_protocol.commit_api import create_fast_forward_commit
from agent_protocol.cycle import next_cycle_number
from agent_protocol.format import render_correction_report, render_handoff
from agent_protocol.manifest import load_manifest
from agent_protocol.trusted_path import assert_no_untrusted_modules, prepare_sys_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--trusted-scripts", default=str(_TRUSTED_SCRIPTS))
    parser.add_argument("--forbidden-root", action="append", default=[])
    args = parser.parse_args(argv)
    trusted = Path(args.trusted_scripts).resolve()
    forbidden = [Path(item).resolve() for item in args.forbidden_root]
    prepare_sys_path(trusted, forbidden_roots=forbidden)
    assert_no_untrusted_modules(forbidden)
    manifest = load_manifest(Path(args.manifest))
    if manifest.parent_sha != os.environ["REVIEWED"].lower():
        raise SystemExit("manifest_parent_mismatch")
    files = {item.path: (item.mode, item.content) for item in manifest.files}
    result = create_fast_forward_commit(
        api_root=f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}",
        token=os.environ["GH_TOKEN"],
        head_ref=os.environ["HEAD_REF"],
        expected_parent=os.environ["REVIEWED"],
        files=files,
        deletions=list(manifest.deletions),
        message=(
            f"fix: address architect review {os.environ['REVIEWED']}\n\n"
            f"HerbaGraph-Correction-Cycle: {next_cycle_number([])}\n"
            f"HerbaGraph-Reviewed-SHA: {os.environ['REVIEWED']}\n"
        ),
    )
    body = render_correction_report(
        task=os.environ["TASK"],
        pr_number=int(os.environ["PR_NUMBER"]),
        reviewed_commit=os.environ["REVIEWED"],
        new_commit=result.sha,
        cycle=next_cycle_number([]),
        tests="mapped no-secrets validation",
    )
    handoff = render_handoff(
        task=os.environ["TASK"],
        commit=result.sha,
        pr_number=int(os.environ["PR_NUMBER"]),
    )
    Path("/tmp/correction.md").write_text(body + "\n" + handoff, encoding="utf-8")
    print(result.sha)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

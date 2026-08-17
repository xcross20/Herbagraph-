"""Trusted GitHub-API commit + exact-SHA fast-forward. No git credentials."""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class ApiCommitResult:
    sha: str
    ref: str
    fast_forward: bool


def _request(method: str, url: str, token: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"github_api_{exc.code}:{detail}") from exc


def assert_grok_ref(head_ref: str) -> str:
    ref = head_ref.removeprefix("refs/heads/")
    if not ref.startswith("grok/"):
        raise ValueError("refusing_non_grok_push")
    return ref


def create_fast_forward_commit(
    *,
    api_root: str,
    token: str,
    head_ref: str,
    expected_parent: str,
    files: dict[str, str] | dict[str, bytes] | dict[str, tuple[str, bytes]],
    deletions: list[str],
    message: str,
    request=_request,
) -> ApiCommitResult:
    """Create a commit on expected_parent and fast-forward the grok/** ref."""
    ref = assert_grok_ref(head_ref)
    parent = expected_parent.lower()
    current = request("GET", f"{api_root}/git/ref/heads/{ref}", token)
    current_sha = str((current.get("object") or {}).get("sha") or "").lower()
    if current_sha != parent:
        raise ValueError("stale_run_remote_head_changed")
    parent_commit = request("GET", f"{api_root}/git/commits/{parent}", token)
    base_tree = str((parent_commit.get("tree") or {}).get("sha") or "")
    tree_items = []
    for path, payload in files.items():
        if isinstance(payload, tuple):
            mode, content = payload
        else:
            mode, content = "100644", payload
        if mode not in {"100644", "100755"}:
            raise ValueError(f"unsupported_mode:{path}:{mode}")
        raw = content.encode("utf-8") if isinstance(content, str) else content
        blob = request(
            "POST",
            f"{api_root}/git/blobs",
            token,
            {"content": base64.b64encode(raw).decode("ascii"), "encoding": "base64"},
        )
        tree_items.append({"path": path, "mode": mode, "type": "blob", "sha": blob["sha"]})
    for path in deletions:
        tree_items.append({"path": path, "mode": "100644", "type": "blob", "sha": None})
    tree = request(
        "POST",
        f"{api_root}/git/trees",
        token,
        {"base_tree": base_tree, "tree": tree_items},
    )
    commit = request(
        "POST",
        f"{api_root}/git/commits",
        token,
        {"message": message, "tree": tree["sha"], "parents": [parent]},
    )
    new_sha = str(commit["sha"])
    request(
        "PATCH",
        f"{api_root}/git/refs/heads/{ref}",
        token,
        {"sha": new_sha, "force": False},
    )
    return ApiCommitResult(sha=new_sha, ref=ref, fast_forward=True)

"""Trusted review artifacts. github-actions[bot] alone is not enough."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


def canonical_digest(
    *,
    pr_number: int,
    head_sha: str,
    task: str,
    workflow_run_id: str,
    trusted_workflow_sha: str,
    review_payload: str,
) -> str:
    blob = "\n".join(
        [
            str(int(pr_number)),
            (head_sha or "").lower(),
            task or "",
            str(workflow_run_id or ""),
            (trusted_workflow_sha or "").lower(),
            review_payload or "",
        ]
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ReviewArtifact:
    pr_number: int
    head_sha: str
    task: str
    workflow_run_id: str
    trusted_workflow_sha: str
    review_payload: str
    digest: str

    def matches(
        self,
        *,
        pr_number: int,
        head_sha: str,
        task: str,
        workflow_run_id: str | None = None,
        trusted_workflow_sha: str | None = None,
    ) -> bool:
        if int(self.pr_number) != int(pr_number):
            return False
        if self.head_sha.lower() != (head_sha or "").lower():
            return False
        if self.task != task:
            return False
        if workflow_run_id is not None and str(self.workflow_run_id) != str(workflow_run_id):
            return False
        if (
            trusted_workflow_sha is not None
            and self.trusted_workflow_sha.lower() != trusted_workflow_sha.lower()
        ):
            return False
        expected = canonical_digest(
            pr_number=self.pr_number,
            head_sha=self.head_sha,
            task=self.task,
            workflow_run_id=self.workflow_run_id,
            trusted_workflow_sha=self.trusted_workflow_sha,
            review_payload=self.review_payload,
        )
        return expected == self.digest


def stamp_trusted_task(payload: str, task: str) -> str:
    """Overwrite Codex's task field with the qualify-time handoff task.

    The ticket id is a control-plane binding, not a model output. Codex
    inventing "PR #15 agent-loop canary" must not fail-close a valid SHA.
    """
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return payload
    if not isinstance(data, dict):
        return payload
    data["task"] = task
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False)


def build_artifact(
    *,
    pr_number: int,
    head_sha: str,
    task: str,
    workflow_run_id: str,
    trusted_workflow_sha: str,
    review_payload: str,
) -> ReviewArtifact:
    digest = canonical_digest(
        pr_number=pr_number,
        head_sha=head_sha,
        task=task,
        workflow_run_id=workflow_run_id,
        trusted_workflow_sha=trusted_workflow_sha,
        review_payload=review_payload,
    )
    return ReviewArtifact(
        pr_number=int(pr_number),
        head_sha=head_sha.lower(),
        task=task,
        workflow_run_id=str(workflow_run_id),
        trusted_workflow_sha=trusted_workflow_sha.lower(),
        review_payload=review_payload,
        digest=digest,
    )


def artifact_from_dict(raw: dict) -> ReviewArtifact:
    return ReviewArtifact(
        pr_number=int(raw["pr_number"]),
        head_sha=str(raw["head_sha"]).lower(),
        task=str(raw["task"]),
        workflow_run_id=str(raw["workflow_run_id"]),
        trusted_workflow_sha=str(raw["trusted_workflow_sha"]).lower(),
        review_payload=str(raw["review_payload"]),
        digest=str(raw["digest"]),
    )


def load_artifact(path: str) -> ReviewArtifact:
    return artifact_from_dict(json.loads(open(path, encoding="utf-8").read()))


def dump_artifact(artifact: ReviewArtifact) -> dict:
    return {
        "pr_number": artifact.pr_number,
        "head_sha": artifact.head_sha,
        "task": artifact.task,
        "workflow_run_id": artifact.workflow_run_id,
        "trusted_workflow_sha": artifact.trusted_workflow_sha,
        "review_payload": artifact.review_payload,
        "digest": artifact.digest,
    }

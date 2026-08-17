"""Shared constants for the Codex ↔ Grok review loop."""

from __future__ import annotations

MAX_CORRECTION_CYCLES = 3
REQUIRED_BASE_BRANCH = "integration/agent"
REQUIRED_HEAD_PREFIX = "grok/"
REQUIRED_LABEL = "agent-loop"

LABEL_CHANGES_REQUIRED = "changes-required"
LABEL_ARCHITECT_APPROVED = "architect-approved"
LABEL_FOUNDER_DECISION = "founder-decision-required"
LABEL_READY_FOR_ARCHITECT = "ready-for-architect"

MANAGED_LABELS = (
    REQUIRED_LABEL,
    LABEL_READY_FOR_ARCHITECT,
    LABEL_CHANGES_REQUIRED,
    LABEL_ARCHITECT_APPROVED,
    LABEL_FOUNDER_DECISION,
)

# PR #6 is the baseline red-test draft and is excluded from automation rollout.
EXCLUDED_HEAD_REFS = frozenset({"grok/mvp-baseline-red-tests"})

VERDICT_CHANGES_REQUIRED = "CHANGES_REQUIRED"
VERDICT_APPROVED = "ARCHITECT_APPROVED"
VERDICT_FOUNDER = "FOUNDER_DECISION_REQUIRED"

VERDICTS = frozenset(
    {
        VERDICT_CHANGES_REQUIRED,
        VERDICT_APPROVED,
        VERDICT_FOUNDER,
    }
)

REVIEW_HEADING = "HERBAGRAPH_ARCHITECT_REVIEW"
HANDOFF_HEADING = "HERBAGRAPH_IMPLEMENTATION_REPORT"
CORRECTION_HEADING = "HERBAGRAPH_CORRECTION_REPORT"

COMMENT_MARKER_PREFIX = "<!-- herbagraph-architect-review"
CORRECTION_MARKER_PREFIX = "<!-- herbagraph-correction-report"
HANDOFF_MARKER_PREFIX = "<!-- herbagraph-implementation-report"

FORBIDDEN_ACTIONS = frozenset(
    {
        "merge",
        "deploy",
        "create_secret",
        "promote_to_main",
        "migrate_production",
    }
)

TRUSTED_REVIEW_AUTHORS = frozenset({"github-actions[bot]"})

CONTROL_PLANE_PREFIXES = (
    ".github/workflows/",
    ".github/codex/",
    ".github/prompts/",
    "scripts/agent_protocol/",
)

CONTROL_PLANE_FILES = frozenset(
    {
        "AGENTS.md",
        "docs/agent-workflow/PROTOCOL.md",
        "docs/architecture/PRODUCT_NORTH_STAR.md",
    }
)

PUSH_CREDENTIAL_KEYS = frozenset(
    {
        "GITHUB_TOKEN",
        "GH_TOKEN",
        "INPUT_GITHUB_TOKEN",
        "GIT_ASKPASS",
        "GIT_CONFIG_COUNT",
    }
)

APPROVED_TEST_SUITES: dict[str, tuple[str, ...]] = {
    "protocol": ("python", "-m", "pytest", "tests/test_agent_protocol", "-q"),
}

REQUIRED_CHECK_CONTEXTS = frozenset({"gates"})

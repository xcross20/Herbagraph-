# HerbaGraph Agent Collaboration Protocol

## Purpose

GitHub issues, pull requests, reviews, and commit SHAs are the durable communication channel between the Founder, Architect, and Grok Implementer.

No agent should rely on an unrecorded chat message as the sole source of product intent or approval.

## Workflow states

`VISION_NEEDED` -> `READY_FOR_IMPLEMENTER` -> `IMPLEMENTING` -> `READY_FOR_ARCHITECT` -> `CHANGES_REQUIRED` or `ARCHITECT_APPROVED` -> `OWNER_APPROVAL` -> `MERGED`

A task may move backward when new evidence exposes a design conflict.

## Founder to Architect

The Founder provides the goal, user problem, priorities, constraints, and unresolved judgment calls. The Architect converts them into a GitHub issue or specification with measurable acceptance criteria.

## Architect to Grok

Use this handoff in the issue:

```markdown
HERBAGRAPH_HANDOFF
Task: HG-###
Status: READY_FOR_IMPLEMENTER
Target branch: integration/agent

Objective:
...

User-visible outcome:
...

Current behavior:
...

Required behavior:
...

Invariants:
- ...

Acceptance tests:
- [ ] ...

Out of scope:
- ...

Founder decisions required:
- None
```

## Grok to Architect

Grok opens a PR and posts:

```markdown
HERBAGRAPH_IMPLEMENTATION_REPORT
Task: HG-###
Status: READY_FOR_ARCHITECT
Commit: <full SHA>

Implemented:
- ...

Files changed:
- ...

Tests run:
- command: result

Migrations:
- None

Security/privacy impact:
- None

Known limitations:
- ...

Questions:
- None
```

The report must describe what the code actually does, not merely repeat the intended specification.

## Architect review

The Architect reviews the exact commit SHA and posts:

```markdown
HERBAGRAPH_ARCHITECT_REVIEW
Task: HG-###
Reviewed commit: <full SHA>
Status: CHANGES_REQUIRED

BLOCKING:
1. ...

SHOULD-FIX:
1. ...

NOTED:
1. ...

Required regression tests:
- [ ] ...

Next owner: GROK
```

When no blockers remain:

```markdown
HERBAGRAPH_ARCHITECT_REVIEW
Task: HG-###
Reviewed commit: <full SHA>
Status: ARCHITECT_APPROVED
Unresolved blocking findings: 0
Next owner: FOUNDER
```

Approval is invalidated by any later code change.

## Automation contract

GitHub Actions workflow: `.github/workflows/herbagraph-agent-loop.yml`.

### Triggers

The workflow uses `pull_request_target` so the running YAML and orchestrator always come from `integration/agent`. Untrusted PR code is checked out into a separate `untrusted/` worktree with `persist-credentials: false`. Model steps never receive `GITHUB_TOKEN`.

A PR event (`opened`, `synchronize`, `reopened`, `labeled`, `ready_for_review`) or `workflow_dispatch` may start the loop only when **all** of these are true:

- base branch is `integration/agent`;
- head is a same-repository `grok/**` branch;
- the PR has the `agent-loop` label;
- a `HERBAGRAPH_IMPLEMENTATION_REPORT` in the PR body or comments names the **current** 40-character head SHA.

`grok/mvp-baseline-red-tests` (PR #6) is explicitly excluded from rollout.

Fork PRs never receive agent secrets (`pull_request` only; never `pull_request_target`).

### Idempotency

- Concurrency group: `herbagraph-agent-loop-<pr>` (cancels older SHA runs).
- Review comments are upserted with `<!-- herbagraph-architect-review idempotency=<pr>-<sha> -->`.
- Duplicate deliveries for the same SHA update or no-op the same comment.
- Live PR head is re-read before every comment, label, or push. A mismatch exits with no write.

### Cycle limit and recovery

- A correction cycle is a `CHANGES_REQUIRED` review plus a matching `HERBAGRAPH_CORRECTION_REPORT`.
- After three completed cycles, a further `CHANGES_REQUIRED` stops automation and applies `founder-decision-required`.
- A review whose `Reviewed commit` is not the current head SHA never triggers Grok edits.
- Missing `OPENAI_API_KEY` or `XAI_API_KEY` halt automation with a visible founder-decision comment. The workflow does not create secrets.

### Job isolation

- Architect job: `contents: read`, Codex `permission-profile: :read-only`, `OPENAI_API_KEY` only.
- Correction job: Grok edits the untrusted worktree without push credentials. A trusted post-model step validates the patch, runs allowlisted tests, commits, and pushes without `--force`.
- Control-plane paths (workflow, protocol helpers, AGENTS.md, prompts/schemas) cannot be edited by a correction.
- A digest-bound review artifact from the trusted run is required to trigger Grok. `github-actions[bot]` alone is not sufficient.
- Pending required checks defer with no write. Failed required checks are `CHANGES_REQUIRED`. Missing/untrusted checks escalate to the founder.
- Approval never merges or deploys.
- The loop workflow is installed from protected `main`. See `docs/architecture/adr-0007-agent-loop-bootstrap.md`.

### Labels

`agent-loop`, `ready-for-architect`, `changes-required`, `architect-approved`, `founder-decision-required`.

### Dry-run

```bash
python -m pytest tests/test_agent_protocol -q
python scripts/agent_protocol/dry_run.py
```

`workflow_dispatch` with `dry_run=true` runs the same fixture path without calling Codex or Grok.

## Branch strategy

- Autonomous implementation branches start from current `integration/agent`.
- Grok branches use `grok/<issue>-<slug>`.
- Architect proposal branches use `architect/<issue>-<slug>`.
- Implementation PRs target `integration/agent`.
- Only an owner-approved promotion PR targets `main`.
- Delete short-lived branches after merge; keep decisions in issues, PRs, and architecture records.

## Decision records

Create an architecture decision record when a change:

- changes the Case data model or source of truth;
- introduces a new evidence relationship;
- changes safety or epistemic governance;
- changes LLM authority;
- changes authentication, PHI handling, or audit behavior;
- replaces an existing subsystem;
- adds a new external clinical, laboratory, ordering, or commerce integration.

Use `docs/architecture/decisions/ADR-####-short-title.md` with Context, Decision, Alternatives, Consequences, Rollback, and Owner Approval.

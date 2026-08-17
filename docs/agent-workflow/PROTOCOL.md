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

- A PR event or explicit label may trigger an Architect run.
- The trigger must include repository, PR number, head SHA, linked task, and requested action.
- Use a stable conversation key per issue or PR.
- Use an idempotency key derived from PR number and head SHA.
- Grok may poll GitHub comments or consume webhooks for Architect responses.
- Stop after three automated correction cycles and escalate to the Founder.
- Never automate merge, deployment, production migration, or secret creation.

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

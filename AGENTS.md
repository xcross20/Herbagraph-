# HerbaGraph Agent Operating Contract

This repository is governed by the HerbaGraph product vision and evidence-discipline rules below. These instructions apply repository-wide unless a more specific AGENTS.md adds stricter rules.

## Roles

- Founder / Vision Owner: sets product vision, risk tolerance, scope, and final release approval.
- Architect: converts the vision into specifications, evaluates system-wide consequences, reviews implementation, and may block changes that violate the product model.
- Implementer (including Grok): writes code, tests it, reports limitations, and responds to review findings. The Implementer does not redefine product intent silently.
- GitHub: the durable source of truth for tasks, decisions, diffs, reviews, and approvals.

## Product North Star

HerbaGraph is an explainable biological reasoning platform. It must preserve a transparent chain from concern and evidence to investigation, intervention synthesis, and monitoring without presenting disease probability or a diagnosis.

The core loop is:

CONCERN -> DISCOVERY -> INVESTIGATION -> EVIDENCE -> INTERVENTION -> MONITORING -> UPDATED CASE

Guided Discovery is additive. It sits above the existing laboratory analysis engine and must not replace or duplicate that engine.

## Non-negotiable reasoning invariants

1. The Case is the longitudinal source of truth. Chat is an interface over the Case.
2. Patient-reported facts, interpretations, hypotheses, test results, and system inferences are distinct data types.
3. Absence of evidence is not evidence of absence.
4. A test may support, weaken, resolve, partially assess, or not address an investigation branch.
5. A test that does not directly assess a branch cannot close that branch.
6. Unrelated tests must not be attached as inconclusive evidence.
7. Corrections are append-only: preserve the old fact or claim as inactive/superseded and link the replacement.
8. Rebuilds must never resurrect inactive or superseded state.
9. Replaying a turn must be idempotent; it must not duplicate findings, gaps, workup, timeline events, or evidence.
10. User-facing completeness or confidence must not be represented as disease probability.
11. LLMs may extract, organize, summarize, and verbalize allowed reasoning. They may not invent diagnoses, citations, test results, or clinical certainty.
12. Labs continue through the existing parser, normalizer, evidence, safety, and reporting pipeline.
13. Non-lab investigations are coverage-aware evidence objects, even when their parsers are not yet implemented.
14. Every material conclusion must be explainable from persisted provenance.

## Safety and regulatory boundaries

- Do not diagnose.
- Do not present HerbaGraph as replacing professional medical judgment.
- Preserve safety escalation and emergency-routing behavior.
- Do not weaken disclaimers or evidence limitations.
- Do not expose protected health information in logs, prompts, fixtures, commits, issues, or PRs.
- Never commit secrets, credentials, access tokens, production exports, or real patient records.
- Changes involving authentication, authorization, encryption, PHI handling, medical safety logic, or production migrations require Founder approval.

## Branch and PR model

- `main`: owner-approved and releasable only.
- `integration/agent`: staging lane for reviewed autonomous work.
- `grok/<issue>-<slug>`: implementation branches.
- `architect/<issue>-<slug>`: architecture or specification branches.
- `agent/<slug>`: automation-created foundation or maintenance branches.

Agents must not push directly to `main`. Implementation PRs target `integration/agent`. Promotion PRs from `integration/agent` to `main` require Founder approval.

Each PR must identify the exact issue/specification, current commit SHA, changed behavior, tests run, known limitations, migrations, security implications, and rollback approach.

## Required implementation sequence

1. Read the linked issue and applicable architecture decision records.
2. Inspect the current code path before proposing a replacement.
3. Restate acceptance criteria and invariants.
4. Implement the smallest coherent change.
5. Add unit and hostile-path integration tests.
6. Run relevant tests and report exact commands/results.
7. Open a PR using the repository template.
8. Request Architect review.
9. Address findings without silently changing scope.
10. Escalate unresolved product decisions to the Founder.

## Code Review Rules

### Release blockers

Flag a change as blocking when it can:

- corrupt, duplicate, contaminate, delete, or resurrect longitudinal Case state;
- attach evidence to an unrelated investigation branch;
- close a branch using non-addressing evidence;
- convert missing coverage into negative or inconclusive clinical evidence;
- leak PHI, secrets, or credentials;
- bypass safety escalation, provenance, authorization, audit, or owner scoping;
- present diagnostic certainty or disease probability;
- deploy or migrate production state without an explicit owner-approved plan.

### Required hostile-path tests

For Discovery and investigation-state changes, include tests for:

- normal EMG does not address small-fiber function and cannot close that branch;
- unrelated EMG is not attached to a biliary branch;
- repeated turn and non-informational follow-up do not create duplicate rows;
- correction leaves the old row inactive, links the replacement, and survives rebuild;
- concurrent writes cannot create duplicate case branches or gaps;
- LLM output with malformed-but-recoverable shapes does not corrupt persisted state;
- safety state persists correctly across follow-up turns.

### Review output

Architect reviews should classify findings as:

- BLOCKING: must be fixed before merge;
- SHOULD-FIX: important but may be explicitly deferred;
- NOTED: informational or future work.

Approval applies only to the reviewed commit SHA. Any later code change requires another review pass.

## Definition of Done

A task is complete only when:

- acceptance criteria are demonstrably satisfied;
- applicable tests pass;
- migrations and rollback are documented;
- known limitations are explicit;
- the PR contains no unrelated changes;
- Architect review has no unresolved BLOCKING findings;
- Founder approval is present when required.

---
name: engineering-operating-manual
description: >
  Run the Engineering Operating Manual pipeline: PM → Architect → Staff →
  Implementer → QA → Reviewer → SRE → Tech Lead. Use when the user runs
  /engineering-operating-manual, /hats, "wear the hats", "operating manual",
  or asks to plan, spec, design, risk-map, implement, test, review, or ship
  software with role discipline. Also load for any HerbaGraph coding session
  that is not a one-line typo.
metadata:
  short-description: "Hundred-person hat pipeline for shipping software"
---

# Engineering Operating Manual

You are one operator wearing eight hats. **Never collapse hats.** Sequence, artifacts, and forbidden lists are the disagreement a hundred-person team would have provided.

## Source of truth (do not paraphrase away)

Read these before producing artifacts:

- `references/engineering-operating-manual.md`
- `references/ENGINEERING-OPERATING-MANUAL-REFERENCE.md`

Hat procedures (same folder tree):

| Order | Hat | Skill | Reference |
|---|---|---|---|
| 1 | PM | `/pm-hat` | `references/1-pm-hat.agent.md` |
| 2 | Architect | `/architect-hat` | `references/2-architect-hat.agent.md` |
| 3 | Staff / risk | `/staff-hat` | `references/3-staff-hat.agent.md` |
| 4 | Implementer | `/implementer-hat` | `references/4-implementer-hat.agent.md` |
| 5 | QA | `/qa-hat` | `references/5-qa-hat.agent.md` |
| 6 | Reviewer | `/reviewer-hat` | `references/6-reviewer-hat.agent.md` |
| 7 | SRE | `/sre-hat` | `references/7-sre-hat.agent.md` |
| 8 | Tech Lead | `/techlead-hat` | `references/8-techlead-hat.agent.md` |

Loop (Implementer+QA only): `/engineering-ops-loop` → `references/9-loop.agent.md`

Always-on while writing code: `/clean-code` → `references/clean-code.instructions.md`

Design-only: `/design-hat` → `references/design.prompt.md`

On HerbaGraph, also obey `.grok/skills/herbagraph-ops/SKILL.md` for catalog/CI/reseed gates. Hats first, HerbaGraph gates at QA/SRE.

## Laws

- Sequence: one hat at a time, in order.
- Artifacts: each hat writes a surface the next hat can attack. A handoff that lives only in your head is not a handoff.
- Forbidden lists keep hats from collapsing.
- Definition of done cannot be waived alone: every acceptance claim has a once-red test; top risk has mitigation + test + tripwire; cold review has a written verdict; rollback stated with what it strands.

## Scale

- Two-way door, tiny: 90-second PM spec (problem, 3 claims, door class) then implement + test.
- One-way door (schema, public API, auth contract, persisted data): full pipeline, written ADRs.

## Invocation

- `/engineering-operating-manual` — run the full pipeline on the current request.
- `/pm-hat` … `/techlead-hat` — wear one hat only.
- `/engineering-ops-loop` — implement/test/fix until green (never weaken tests).

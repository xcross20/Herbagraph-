---
name: architect-hat
description: >
  Architect Hat — data model, graded seams, door-sorted decisions, ADRs.
  Forbidden: writing production code or silently reopening the spec. Use when
  the user runs /architect-hat, asks for a design, ADR, seams, or architecture.
metadata:
  short-description: "Architect hat: shape, seams, ADRs"
---

# Architect Hat

Read `../engineering-operating-manual/references/2-architect-hat.agent.md` and Part II of `../engineering-operating-manual/references/engineering-operating-manual.md`. Consume the PM spec.

## Forbidden

- No production code. Pseudocode and interface sketches only.
- Do not silently reopen the spec. If it is wrong, send it back to the PM hat with a written amendment.
- No strawman alternatives in an ADR.

## Procedure

1. **Data first.** Entities, relationships, cardinalities, lifecycles. Limiting cases: zero items, one user with a million records, duplicate natural keys, deleted parent with live children.
2. **Grade seams.** Own truth condition? Testable alone? Replaceable? Failing seams only on purpose, in the ADR.
3. **Sort decisions by door.** Two-way: default, five minutes. One-way: two real alternatives, kill-fact hunt, written ADR.
4. **Pre-empt hotspots.** Every external call: timeout + failure behavior. Every piece of state: one owner. Every async boundary: duplicate / missing / out-of-order answer.

## Artifacts

```
## DESIGN: [title]
**Data model:** [...]
**Seams:** [each graded pass/fail]
**Decisions:** [decision | door | choice | why]
```

Plus one ADR per one-way door (context, decision, real alternatives, consequences binned verified/recalled/guess, revisit-if).

End with: "Design complete. Next: Staff hat for the risk map."

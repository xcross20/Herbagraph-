---
name: implementer-hat
description: >
  Implementer Hat — write boring, verifiable code in atomic commits.
  Forbidden: silent spec changes and unreviewable diffs. Use when the user
  runs /implementer-hat or asks to implement a spec. Also load /clean-code.
metadata:
  short-description: "Implementer hat: clean code as verification"
---

# Implementer Hat

Read `../engineering-operating-manual/references/4-implementer-hat.agent.md`, `../engineering-operating-manual/references/clean-code.instructions.md`, and Part IV of the manual.

Consume the spec, design, and risk map. Produce code.

## Forbidden

- No silent spec changes — send them back to the PM hat in writing.
- Do not walk through one-way doors the design did not open.
- Do not mark your own work done.
- No diffs that reshape AND rebehave. Refactor first, behavior after.

## Rules

1. Names are claims. Booleans are predicates. Quantities have units.
2. One function, one thing, one altitude.
3. Illegal states unrepresentable; validate loudly once at the edge.
4. Error handling is designed. Catch-log-continue is a bug wearing safety equipment.
5. Comments carry WHY only.
6. Duplication beats the wrong abstraction.
7. Boring wins.
8. Atomic commits: one claim each.

House style over general preference. Out-of-scope notes go on a list, not into the diff.

End with: "Implementation complete: [N] commits. Out-of-scope notes: [list]. Next: QA hat."

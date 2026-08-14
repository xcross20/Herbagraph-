---
name: clean-code
description: >
  Clean-code rules from the Engineering Operating Manual. Clean code is a
  verification strategy, not an aesthetic. Use whenever writing or editing
  application code (Python, JS, TS, or any implementation). Triggers:
  /clean-code, implement, refactor, "write the function."
metadata:
  short-description: "Clean code as a verification strategy"
---

# Clean code

Read `../engineering-operating-manual/references/clean-code.instructions.md`. Apply on every code edit.

- **Names are claims.** Booleans read as predicates (`is_expired`). Quantities carry units (`timeout_ms`). If an edit changes behavior, rename anything the change made into a lie.
- **One function, one thing, one altitude.**
- **Illegal states unrepresentable.** Prefer types/shapes that make invalid combinations unwritable.
- **Validate loudly once, at the edge.** The interior trusts its inputs.
- **No catch without a theory.** Never catch-log-continue.
- **Comments carry WHY only.**
- **Duplication beats the wrong abstraction.** Abstract only when divergence would be a bug.
- **Boring wins.**
- **Match house style.** Improvements ship as their own diffs.
- **One claim per commit.** Refactor commits never change behavior.
- **Security floor:** neutralize inputs that reach a query, shell, path, template, or formula. No secrets in code, logs, tests, or error messages.

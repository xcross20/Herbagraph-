---
applyTo: "**/*.{py,js,ts,jsx,tsx,java,go,rb,cs,cpp,c,rs,kt,swift,php,scala}"
---
# Clean-Code Rules (Implementer Hat — apply to all code generation and edits)

Clean code is a verification strategy, not an aesthetic. Every rule exists to make correctness checkable by a hostile reader; when a rule would make verification harder, the rule loses.

- **Names are claims.** The reader must predict the behavior from the name and be right. Booleans read as predicates (`is_expired`, not `status`). Quantities carry units (`timeout_ms`). No near-synonym pairs (`user_data` + `user_info`) in one scope. If an edit changes behavior, rename anything the change made into a lie.

- **One function, one thing, one level of abstraction.** If "this function is correct" can't be stated without describing its callers, the boundary is wrong. Push detail down.

- **Illegal states unrepresentable.** Prefer types/shapes that make invalid combinations unwritable over runtime checks that catch them.

- **Validate loudly once, at the edge.** Fail at the point of entry with what/where/what-input. The interior trusts its inputs — no defensive re-checking four layers deep.

- **No catch without a theory.** Catch only where the failure can be handled meaningfully. Never catch-log-continue — it converts loud failures into silent corruption. Every acquired resource has a guaranteed release path; every early return leaves state consistent.

- **Comments carry WHY only:** the non-obvious choice, the invariant the next person must not break, the external fact this depends on, the buried body. Never restate the code.

- **Duplication beats the wrong abstraction.** Two occurrences: duplicate. Abstract only when divergence between the copies would be a bug.

- **Boring wins.** Prefer obviously-correct over impressive. If it took a minute to convince yourself, it costs the reviewer five and the 3 a.m. debugger twenty.

- **Match house style** in this codebase over general best practice — consistency is a verification aid. Improvements ship as their own diffs, never as stowaways in a feature change.

- **Diff discipline:** one claim per commit; refactor commits never change behavior; behavior commits never reshape; suggested commit messages state the claim + the why that isn't in the diff.

- **Security floor:** every input reaching a query, shell, path, template, or formula goes through the corresponding neutralizer. No secrets in code, logs, tests, or error messages.

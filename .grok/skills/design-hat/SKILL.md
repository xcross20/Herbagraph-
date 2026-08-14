---
name: design-hat
description: >
  Run the Architect hat on a spec: data model, graded seams, door-sorted
  decisions, ADRs. Use when the user runs /design-hat, pastes a spec and
  asks for a design, or invokes the design.prompt workflow.
metadata:
  short-description: "Architect pass over a pasted spec"
---

# Design hat

Read `../engineering-operating-manual/references/design.prompt.md` and wear `/architect-hat`.

Take the current spec and produce:

1. **Data model** — entities, relationships, cardinalities, lifecycles. Limiting cases: zero, one-with-a-million, duplicate keys, deleted-parent.
2. **Seam list** — graded. Failing seams noted as on-purpose.
3. **Door-sorted decisions** — two-way get a default; one-way get two real alternatives + kill-fact hunt + ADR.
4. **ADRs for one-way doors** — consequences binned verified / recalled / guess.

Write no production code. If the spec is wrong, send it back to `/pm-hat` with a proposed amendment.

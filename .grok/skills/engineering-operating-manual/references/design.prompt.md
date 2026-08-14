---
description: "Run the Architect hat on a spec: data model, graded seams, door-sorted decisions, ADRs."
---

Act as the Architect hat from the Engineering Operating Manual.

Take the spec below and produce:
1. **Data model** — entities, relationships, cardinalities, lifecycles. Interrogate with limiting cases: zero, one-with-a-million, duplicate keys, deleted-parent.
2. **Seam list** — each boundary graded: does each side have its own truth condition? can each side be tested alone? is replacement possible? Failing seams noted as on-purpose.
3. **Door-sorted decisions** — two-way doors get a default; one-way doors get two real alternatives + kill-fact hunt + written ADR.
4. **ADRs for one-way doors** — context with actual numbers, decision, alternatives with real reasons, consequences binned (verified/recalled/guess), revisit conditions.

Write no production code. If the spec is wrong, send it back explicitly with a proposed amendment.

**Spec (paste below or reference from workspace):**
{input}

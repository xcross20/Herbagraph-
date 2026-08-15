# Master technology specification

Source: `~/Downloads/herbagraph_master_tech.md` (and the matching `.docx`).

HerbaGraph Discovery is a persistent investigation workspace. The Case is the source of truth. This repo implements that spec as a **modular monolith** (FastAPI + static frontend). A Next.js rewrite is a later two-way door, not a prerequisite.

Implementation phases from the spec:

| Phase | Status in this repo |
|---|---|
| 0 Foundation (Case/Turn) | Partial — Case, Turn, findings, hypotheses, outcomes exist |
| 1 Atlas Discovery shell | In progress — three-panel workspace on `/me.html#discovery` and `/clinic.html#discovery` |
| 2 Consultation engine | Partial — turn orchestrator, safety, intake, NBA |
| 3 Longitudinal snapshot | Not started as a versioned Patient Snapshot table |
| 4 Investigation engine | Partial — map versions + confidence increasers |
| 5–12 Voice, Gold Label, lab ordering, FHIR | Not started / deferred |

Gold Label commerce, imaging diagnosis, and hunting 90% confidence remain non-goals until explicitly requested.

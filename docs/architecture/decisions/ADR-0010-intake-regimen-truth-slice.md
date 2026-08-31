# ADR-0010: IntakeSession and Regimen Truth Slice Boundary

- **Status:** Proposed
- **Date:** 2026-08-20
- **Amends:** ADR-0008, ADR-0009
- **Issue:** #65 successor (Regimen Truth implementation)
- **Decision owners:** Founder, Health AI Architecture
- **Independent review:** Required before acceptance; report SHA for review after this commit

---

## Context

ADR-0008 established the five-service Personal Evidence modular monolith. ADR-0009 amended it with unresolved exposure truth, first-class objectives, RegimenIntelligence seam, RegimenCompiler future boundary, and eight hostile cases.

Before Slice 1 implementation begins, two gaps require explicit decisions:

1. **Where does the user's current regimen enter the system?** ADR-0008 starts with `ProductCapture` (label photo, barcode, manual entry). But the user needs a structured way to describe what they currently take, why, and what they want to achieve — before any product identity is resolved.

2. **What is the scope of the first implementation slice?** The architecture documents cover all five services and the amendments. The implementation branch needs a clear, enforceable boundary: what to build first, and what is explicitly out of scope.

---

## Decision 1 — IntakeSession: First-Class Intake Concept

### Problem

The current architecture begins with `ProductCapture` — a photo, barcode, or manual entry of a specific product. This is correct for adding a new product, but it does not address the user's initial question: *"Here is what I currently take and what I am trying to achieve."*

Starting with product capture forces the user into a product-by-product entry workflow before objectives are established. It also lacks a session concept — there is no bounded intake event to audit, replay, or correct.

### Decision

Add `IntakeSession` as a first-class bounded concept preceding product capture.

An `IntakeSession` is a purpose-specific, time-bounded session for collecting:

- what the user currently takes (by self-reported name, dose, frequency, route)
- what health objectives the user is pursuing
- constraints or "must avoid" goals
- user confidence in their own data

An `IntakeSession` is NOT:

- a Discovery Case turn (different purpose, different data model)
- a product identity record (it precedes identity resolution)
- an exposure record (it records intent and self-report, not what was actually taken)
- a research enrollment form (different consent model)

### Intake-to-Regimen Flow

```
IntakeSession (draft)
  └── IntakeResponse (per item: product_name_raw, dose, frequency, route, confidence)
  └── IntakeObjective (per goal: original_wording, desired_direction, priority, constraints)
        └── [on submit] CaseObjective (linked, status = active)
IntakeSession (submitted)
  └── parse IntakeResponses → proposed RegimenItem drafts
  └── [user review] confirm/correct each draft
  └── [identity capture] ProductCapture → ProductIdentity
  └── [on confirm] RegimenItem (status = confirmed)
  └── [on publish] RegimenVersion (published)
```

### Key invariants

1. `IntakeSession` is immutable after submission. Corrections create a new session or an `IntakeAmendment` event — they do not mutate submitted data.
2. `IntakeResponse.product_name_raw` is the user's verbatim self-report. It is NOT a `ProductIdentity.product_name` — it may be a brand name, a generic description, or a garbled OCR result.
3. An `IntakeSession` may reference products by self-reported name before any `ProductCapture` or `ProductIdentity` exists.
4. `IntakeObjective` records with `status = confirmed` create `CaseObjective` records on submit. `CaseObjective` is the authoritative objective record going forward.
5. `IntakeSession` does NOT create `ExposureEvent` records. Exposure recording is a separate workflow.
6. A submitted `IntakeSession` may not be deleted if it has been used to create a `RegimenVersion`.

### Schema summary

`pe_intake_sessions`: `id`, `case_id`, `owner_id`, `status`, `purpose`, `started_at`, `submitted_at`, `source_intake_session_id`, `case_objective_ids` (JSONB), `provenance`, timestamps.

`pe_intake_responses`: `id`, `intake_session_id`, `concept`, `raw_value`, `normalized_value`, `unit`, `confidence`, `product_name_raw`, `brand_raw`, `notes`, `position`, `source_command_id`, timestamps.

`pe_intake_objectives`: `id`, `intake_session_id`, `original_wording`, `normalized_concept`, `desired_direction`, `priority`, `measurable_outcome` (JSONB), `time_horizon`, `constraints` (JSONB), `status`, `linked_case_objective_id`, timestamps.

`pe_intake_amendments` (future): captures correction events for submitted sessions.

---

## Decision 2 — Slice 1 Scope: Intake and Regimen Truth Only

### Out-of-scope for Slice 1

The following are explicitly excluded from the Slice 1 implementation branch:

| Excluded | Reason |
|---|---|
| **Signals** | Requires resolved exposure identity and temporal ordering. Cannot be meaningfully generated before exact regimen is established. |
| **Experiments** | Requires exact intervention identity, eligibility gate, and protocol governance. Out of scope for regimen foundation. |
| **Attribution** | Requires experiment protocol, adherence data, and confounder assessment. Not applicable until experiments exist. |
| **Wearable ingestion** | No device integration, no time-series normalization, no device reliability contract. |
| **Agent-control infrastructure** | The qualified-agent OS (ADR-0008, Issue #67) is a separate implementation stream. Slice 1 does not add new agent roles, certification rules, or autonomous loop infrastructure. |
| **RegimenIntelligence optimization** | The `RegimenIntelligence` seam and relationship taxonomy (ADR-0009 Amendment 3) are established in the architecture. Slice 1 does not implement the relationship detection logic or conflict flagging engine. |
| **RegimenCompiler** | Future boundary (ADR-0009 Amendment 4). Not implemented in Slice 1. |
| **Passport** | Requires `PersonalEvidenceObject` and attribution analyses. Not applicable until experiments exist. |
| **Research mode** | Requires purpose consent, NIH endpoints, and deidentified export. Explicitly blocked until consented research is authorized. |

### Slice 1 feature checklist

| Feature | Status |
|---|---|
| `IntakeSession` CRUD and submission | In scope |
| `IntakeResponse` capture and parsing | In scope |
| `IntakeObjective` → `CaseObjective` linkage | In scope |
| `ProductCapture` (photo, barcode, manual) | In scope |
| `ProductIdentity` confirmation workflow | In scope |
| `RegimenVersion` publication | In scope |
| `RegimenItem` CRUD, stop, supersession | In scope |
| Correction flows (append-only) | In scope |
| `RegimenIntelligence` seam (contracts only, no optimization) | Architecture only; no implementation |
| `CaseObjective` schema (from Amendment 2) | Architecture only; no implementation |
| Workspace projection (regimen display) | In scope |
| Feature flags (`PERSONAL_EVIDENCE_REGIMEN_V1`) | In scope |

### Slice 1 acceptance criteria

- A user can complete an `IntakeSession`, submitting self-reported products and objectives.
- Submitted `IntakeObjective` records with `status = confirmed` create linked `CaseObjective` records.
- `IntakeResponse` records are parsed into proposed `RegimenItem` drafts.
- A user can add a product via photo, barcode, or manual entry (`ProductCapture`).
- OCR/candidate extraction produces field-level uncertainty visible to the user.
- User confirmation creates a `ProductIdentity` record with `identity_status = user_confirmed`.
- Confirmed items are published as a `RegimenVersion`.
- Corrections create new versions without deleting history.
- Stopping an item transitions `RegimenItem.status` to `stopped`, preserving exposure history.
- All mutations are idempotent with semantic keys.
- All writes require owner authorization and Case version.
- `IntakeSession` data is not used for causal inference or recommendation in Slice 1.
- RegimenIntelligence and RegimenCompiler are not implemented.

---

## Consequences

### Positive

- Users have a structured, auditable intake workflow before product identity is resolved.
- Intake and regimen are separable from observation, experiment, and attribution.
- The intake-to-regimen flow is testable in isolation.
- Clear scope prevents feature creep into Signals/Experiments/Attribution during the regimen foundation.
- Architecture amendments (ADR-0009) are preserved and extended.

### Negative

- `IntakeSession` adds a new top-level domain concept that must be maintained alongside `DiscoveryCase`.
- Intake responses must be parsed into structured data without an LLM in the first implementation (LLM parsing requires the agent-control infrastructure, which is out of scope).

### Implementation note

The first `IntakeSession` implementation uses structured form fields (dropdowns, number inputs, text) rather than free-text LLM parsing. This avoids the agent-control dependency and ensures deterministic field extraction. LLM-assisted intake parsing can be added in a later slice with the agent infrastructure in place.

---

## Summary of Changes

This ADR, together with ADR-0009, constitutes the complete architecture for Slice 1 (Intake and Regimen Truth). The key documents are:

- `PLATFORM_ARCHITECTURE.md` — updated with `IntakeSession`, expanded `RegimenItem` relationship semantics, updated Slice 1 description, API resources, event contract, and observability.
- `FIVE_SERVICE_FRONTEND_BACKEND_MAP.md` — updated package seams and Service 1 (Regimen) to include IntakeSession frontend.
- `ADR-0009` — Founder amendments 1–4 and hostile cases HC-1 through HC-8.
- `ADR-0008` — base modular monolith decision (superseded by ADR-0009 for amendments).

---

## Acceptance Evidence

This ADR is accepted when:

- [ ] `PLATFORM_ARCHITECTURE.md` reflects IntakeSession, expanded RegimenItem, updated Slice 1 scope, and updated API resources
- [ ] `FIVE_SERVICE_FRONTEND_BACKEND_MAP.md` reflects intake package seam and intake frontend
- [ ] `ADR-0010` is committed with clear in-scope / out-of-scope checklist
- [ ] Slice 1 implementation branch is created from the frozen architecture SHA
- [ ] Implementation does not include Signals, Experiments, Attribution, wearable ingestion, or agent-control infrastructure
- [ ] Independent Judge returns PASS on the complete architecture (ADR-0008 + ADR-0009 + ADR-0010)
- [ ] Founder authorizes Slice 1 implementation from the frozen architecture SHA

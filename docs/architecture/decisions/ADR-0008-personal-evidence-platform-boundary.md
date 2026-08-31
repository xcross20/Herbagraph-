# ADR-0008: Extend HerbaGraph as a Personal Evidence modular monolith

- **Status:** Proposed
- **Date:** 2026-08-20
- **Issue:** #65
- **Decision owners:** Founder, Health AI Architecture
- **Independent review:** Required before acceptance

## Context

HerbaGraph already has a FastAPI application, PostgreSQL/Alembic persistence, Celery/Redis workers, static JavaScript workspaces, a longitudinal Discovery Case, evidence pipelines, and an autonomous GitHub workflow. The five proposed services—Regimen, Signals, Experiments, Attribution, and Passport—need shared identity, time, provenance, consent, safety, and Case-version semantics.

A framework rewrite or five deployable microservices would increase migration risk before demand or NIH feasibility has been demonstrated. Adding all new concepts directly to `DiscoveryCase` would create a different failure: an oversized model that conflates investigation, actual exposure, experiment protocol, analysis, and publication.

## Decision

Build one new bounded package, `app/personal_evidence/`, inside the existing FastAPI modular monolith.

It owns:

- exact product identity candidates and confirmations;
- immutable regimen versions;
- actual exposure, outcome, and context events;
- candidate signals;
- safety-bounded protocol state;
- versioned attribution analyses;
- Personal Evidence Objects and Passport projections;
- purpose-specific consent references;
- coherent Personal Evidence projections tied to canonical Case versions.

Keep:

- FastAPI deployment and `app/main.py`;
- `app/api/v1/router.py` as the router assembly seam;
- PostgreSQL/Alembic as canonical transactional storage;
- Celery/Redis for bounded asynchronous work;
- `DiscoveryCase` and Discovery Map as investigation truth;
- existing evidence, lab, upload, authentication, authorization, audit, and safety primitives where their semantic contracts match;
- static `workspace-app.js` and `ask-app.js` as initial frontend shells;
- `integration/agent` staging, `grok/**` implementation branches, exact-SHA review, feature flags, and Founder release gates.

Change:

- add additive `pe_*` tables rather than overloading discovery models;
- add `/api/v1/personal-evidence/*` commands and coherent read projections;
- add a `My Evidence` workspace section and extract small JS modules incrementally;
- make Ask issue the same typed commands as the workspace;
- require semantic idempotency, expected Case version, typed missingness, immutable corrections, and atomic projection snapshots;
- add purpose-specific product/research consent and research-access revocation;
- add qualified-agent certification and fail-closed assignment.

## Consequences

### Positive

- One deployable unit and transaction boundary during Phase I/MVP.
- Existing HerbaGraph value is reused.
- Shared Case and Personal Evidence semantics prevent five disconnected products.
- Each service can ship as a flagged vertical slice.
- Extraction to separate services remains possible after measured scale or isolation needs.

### Negative

- Module boundaries require active enforcement.
- Static JavaScript needs disciplined extraction as complexity grows.
- Worker tasks and projections must be version-aware.
- Existing composition seed data is insufficient as a commercial identity catalog.

## Rejected alternatives

1. **Rewrite the frontend in Next.js now.** Rejected because it does not prove the founding customer or feasibility hypothesis and delays end-to-end learning.
2. **Create five microservices.** Rejected because distributed consistency, auth, observability, and versioning costs arrive before scale evidence.
3. **Store state in chat or local storage.** Rejected because neither is canonical, auditable health truth.
4. **Add columns to DiscoveryCase for every service.** Rejected because investigation state, exposure history, protocol, analysis, and published evidence have distinct lifecycles.
5. **Launch Signals first.** Rejected because patterns computed before exact identity and typed time can be polished and wrong.

## First slice

Regimen Truth:

`capture/manual input -> candidate identity -> visible field uncertainty -> user confirmation -> immutable regimen version -> correction -> coherent workspace/Ask projection`

No Signals, experiments, causal attribution, research enrollment, or production activation is included.

## Extraction triggers

Reconsider service separation only when evidence shows one or more of:

- materially different security or regulatory boundary;
- independent scaling dominates operations;
- deployment cadence creates persistent blocking;
- provider-specific failure requires isolation;
- transaction volume makes the monolith unable to meet measured objectives.

## Acceptance evidence

- architecture and service maps reviewed at an immutable SHA;
- red-first contracts exist for identity, idempotency, missingness, snapshot coherence, consent, and correction;
- first implementation remains behind disabled-by-default flags;
- migration and rollback are proven before UAT;
- Independent Judge returns PASS;
- Founder separately authorizes any merge, pilot, research activation, or production release.

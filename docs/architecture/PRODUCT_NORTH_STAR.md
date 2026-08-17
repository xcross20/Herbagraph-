# HerbaGraph Product North Star

## Product thesis

HerbaGraph helps a person or clinician understand what is known, what remains unexplained, what prior work actually evaluated, and what evidence would most usefully change the investigation.

It is not a symptom chatbot, a diagnosis generator, or a supplement recommender. It is a longitudinal, explainable investigation and biological reasoning system.

## Core product loop

1. Concern: capture the person's story in their own words.
2. Discovery: ask one useful question at a time while preserving safety.
3. Investigation: organize plausible investigation families and unresolved gaps without assigning disease probability.
4. Evidence: ingest labs, records, imaging, EMG, biopsy, hearing tests, and other prior work according to what they actually assess.
5. Intervention: synthesize evidence-supported options through the existing lab, literature, and safety systems.
6. Monitoring: compare later observations and evidence without claiming causality.
7. Updated Case: carry the verified longitudinal record into the next visit.

## Architectural layers

### Layer 1: Longitudinal Case

The durable record of active and historical findings, interpretations, workup, branches, gaps, evidence, corrections, decisions, and monitoring events.

### Layer 2: Guided Discovery

The adaptive conversation interface. It reads the Case, proposes constrained mutations, passes safety and epistemic governors, persists accepted mutations, then verbalizes the selected next action.

### Layer 3: Investigation Map

A coverage-aware view of open branches, supporting evidence, weakening evidence, non-addressing evidence, contradictions, and unresolved gaps.

### Layer 4: Existing laboratory engine

The established lab parser, normalization, biomarker/pathway reasoning, literature, safety, intervention, reporting, and longitudinal comparison capabilities. Guided Discovery routes to this layer; it does not duplicate it.

### Layer 5: Intervention and Monitoring

Evidence-supported synthesis, safety screening, user/clinician discussion framing, response tracking, and follow-up updates to the Case.

## Primary users

- Individuals with multi-system, persistent, or unexplained concerns.
- Clinicians who need a coherent prior-workup inventory and investigation map.
- Researchers and integrative practitioners who value provenance and evidence limitations.

## MVP success scenario

Input:

> For six months, my feet have burned at night. My doctor says my blood work is normal.

The system must:

- create or resume the correct Case;
- capture duration, timing, distribution, laterality, triggers, associated findings, safety findings, medications, conditions, and prior workup;
- distinguish patient statements from system interpretations;
- organize investigation families without diagnosing;
- identify what “normal blood work” did and did not evaluate;
- understand that a normal EMG does not directly assess small-fiber density/function;
- keep the small-fiber branch open when evidence is non-addressing;
- identify the highest-value next information or evaluation;
- route applicable labs through the existing lab workspace;
- update the map automatically when evidence arrives;
- preserve corrections and longitudinal history;
- progress toward evidence-informed intervention synthesis and monitoring.

## Release gates

Guided Discovery is not complete until all of these are true:

- Case persistence is idempotent across repeated turns.
- Corrections preserve and link history.
- Inactive facts never re-enter active snapshots.
- Evidence cannot contaminate unrelated branches.
- Non-addressing evidence cannot close a branch.
- Investigation-map versions are reproducible from persisted state.
- New lab evidence updates the same Case and map.
- Safety escalation persists across turns.
- The user can see why a branch is open and what could change it.
- No user-facing field implies disease probability or diagnosis.

## Founder decisions reserved

The Founder retains final authority over:

- product positioning and intended users;
- medical/regulatory risk tolerance;
- monetization and Gold Label integration;
- new data sources and ordering partners;
- production deployment;
- breaking schema changes and migrations;
- material security, privacy, or PHI-handling changes;
- promotion from `integration/agent` to `main`.

## Current strategic priority

Build one trustworthy longitudinal investigation before broadening condition coverage. The burning-feet/normal-EMG and gallbladder/unrelated-EMG cases are mandatory hostile-path gates.

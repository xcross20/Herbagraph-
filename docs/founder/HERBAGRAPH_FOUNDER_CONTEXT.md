# HerbaGraph Founder Context and Product Intent

**Status:** Founder-context handoff for designers, researchers, architects, implementers, and reviewers  
**Authority:** Interpretive product context; approved specifications, ADRs, and explicit later Founder decisions control when they conflict  
**Audience:** Humans, Codex, Grok Build, and future engineering or research agents  
**Privacy:** This document intentionally excludes the Founder’s unrelated personal information, personal medical history, credentials, and real patient data

## 1. Why this document exists

HerbaGraph has developed through long-form product, clinical-reasoning, design, architecture, reliability, and commercialization conversations. A technical specification can describe what to build while still omitting the intent that lets a new designer or researcher make good decisions when the specification is silent.

This document transfers that intent. It explains the product’s purpose, intended experience, strategic moat, standards of truth, and decision boundaries. It is not a substitute for inspecting the repository, current issue, exact PR SHA, tests, or deployment state.

Every agent beginning material HerbaGraph work should read, in order:

1. `AGENTS.md` and any applicable nested instructions.
2. This Founder Context.
3. `docs/architecture/PRODUCT_NORTH_STAR.md`.
4. The Discovery Engine master technical specification when present on the working branch.
5. `docs/agent-workflow/PROTOCOL.md`.
6. Applicable ADRs, issues, PRs, review threads, and checks.

GitHub and committed repository documents are durable memory. Chat and terminal prompts are transport only.

## 2. The founding insight

Many people with persistent, multi-system, or unexplained concerns are not suffering from a total absence of information. They are suffering from fragmentation:

- symptoms are recorded in separate encounters;
- normal and negative results are remembered poorly or reduced to “everything was normal”;
- the scope of a prior test is confused with what it did not evaluate;
- each new clinician sees an incomplete slice of the investigation;
- useful uncertainty is collapsed into either reassurance or premature certainty;
- interventions accumulate without a durable account of rationale, constraints, response, or failure;
- the patient must repeatedly reconstruct the case from memory.

HerbaGraph should turn this fragmented journey into a durable, explainable investigation. It should help a person or clinician see what is known, what remains unresolved, what prior evidence actually addressed, and what next information would most efficiently change the map.

The product must feel like an intelligent investigation partner, not a symptom checker, diagnosis generator, generic supplement recommender, or static lab dashboard.

## 3. Product promise

For a supported use case, HerbaGraph should accept a concern and prior evidence, build a non-diagnostic Investigation Map, explain what the evidence does and does not address, incorporate supported laboratory information, surface traceable and appropriately qualified options, and preserve the case correctly over time.

The product loop is:

> CONCERN → DISCOVERY → INVESTIGATION → EVIDENCE → INTERVENTION → MONITORING → UPDATED CASE

The user should not need to understand graph theory, clinical informatics, or evidence taxonomies to benefit from that loop. The experience should be conversational and simple at the surface while rigorous and inspectable underneath.

## 4. Who HerbaGraph is for

Primary users include:

- people with persistent, multi-system, or unexplained concerns;
- people who have completed several tests but still do not understand what was evaluated;
- clinicians who need a coherent prior-workup inventory and investigation map;
- integrative practitioners who need evidence discipline rather than indiscriminate intervention lists;
- researchers or expert reviewers who need provenance and explicit limitations.

The initial product can serve a narrow, supervised population. Broad condition coverage is less important than proving one trustworthy longitudinal investigation.

## 5. The intended user experience

HerbaGraph should feel like an atlas with a persistent guide.

The conversation layer should:

- let the user begin in natural language or voice;
- ask one useful question at a time;
- explain why a question matters when helpful;
- remember verified information so the user does not repeatedly retell the story;
- distinguish user statements from system interpretations;
- identify urgent safety concerns without dramatization or diagnosis;
- help gather the smallest amount of information that materially changes the investigation;
- expose uncertainty honestly instead of hiding it behind confident prose.

The visual investigation layer should make it easy to see:

- active concerns and findings;
- investigation families or branches;
- evidence that supports, weakens, resolves, partially assesses, or does not address a branch;
- prior workups and their actual coverage;
- contradictions and missing information;
- the highest-value next action;
- the rationale and provenance behind every material conclusion;
- what changed over time.

The UI should progressively disclose complexity. A user can receive a simple explanation, while a clinician or researcher can inspect evidence, coverage, rationale, dates, versions, and sources.

## 6. The Discovery Engine is the strategic moat

HerbaGraph’s moat is not merely an LLM, an embedding index, a list of herbs, or a visualization. Models and commodity retrieval systems will improve and become broadly available.

The durable moat is a high-integrity learning system that accumulates structured investigation state:

- normalized concerns and findings;
- longitudinal changes and corrections;
- test and document coverage semantics;
- negative and non-addressing results;
- unresolved gaps;
- hypothesis or branch evolution;
- contradictions;
- evidence provenance and confidence;
- intervention rationale, constraints, and response;
- monitoring outcomes;
- the sequence of questions or actions that most efficiently changed the case.

Over time, this can reveal reusable patterns such as:

- which questions have the highest information gain for a given presentation;
- which tests are commonly misinterpreted as ruling out something they do not assess;
- which evidence combinations open, weaken, close, or reopen investigation branches;
- where users and clinicians experience recurring coverage gaps;
- which interventions appear useful under which evidence and safety constraints;
- where scientific knowledge is contradictory, sparse, or population-limited.

This moat only exists if the underlying data is truthful. Corrupted identity, silent duplication, false branch closure, resurrected corrections, invented citations, or unmarked missing data destroy both the current product and the future discovery asset.

Therefore, data integrity, scientific-output integrity, reliability, and end-to-end gates are moat-building work—not engineering overhead.

## 7. Investigation Map philosophy

An Investigation Map is not a ranked disease-probability list. It is a structured view of plausible investigation families, observed evidence, coverage, gaps, and next actions.

Core principles:

1. A branch may be open without being likely.
2. Missing evaluation is not negative evidence.
3. A normal result only speaks to what the test validly assesses.
4. Non-addressing evidence must not weaken or close a branch.
5. An unrelated test must not be attached merely because it exists in the same case.
6. Contradictory evidence should remain visible and qualified.
7. Closure requires an explicit, governed reason and may later be reopened by new evidence.
8. The map must be reproducible from persisted state.

The canonical hostile examples are intentional teaching cases:

- Burning feet plus a normal EMG: a normal EMG does not directly evaluate small-fiber density or function, so the small-fiber investigation cannot be closed on that basis.
- A biliary or gallbladder concern plus an EMG: the EMG is unrelated and must not be attached as inconclusive evidence to that branch.

## 8. Durable Case and epistemic types

The Case is the longitudinal source of truth. Chat is an interface over the Case, not the Case itself.

The system must keep separate:

- patient-reported facts;
- imported observations and test results;
- system interpretations;
- hypotheses or investigation branches;
- coverage claims;
- evidence relationships;
- recommendations or options;
- monitoring observations;
- safety events;
- corrections and superseded history.

These distinctions should survive persistence, retrieval, summarization, export, and regeneration. The LLM may propose structured mutations, but deterministic validation and governors decide what becomes durable truth.

Corrections are append-only. The original record remains available for audit, becomes inactive or superseded, and links to its replacement. Active projections and user-facing summaries must never resurrect superseded state.

Replay and retries must be semantically idempotent. Stable identity is based on approved domain identity—not mutable presentation text, active status, or accidental row creation order.

## 9. Evidence and scientific reasoning

Every material scientific output should answer:

- What is the claim?
- What source supports it?
- What kind of evidence is the source?
- How directly does it apply to this person, biomarker, pathway, botanical, intervention, dose, or outcome?
- What are the limitations or contradictions?
- What remains unknown?

Evidence confidence must never be cosmetically inflated. Citation presence is not equivalent to evidentiary strength. Mechanistic evidence, observational associations, randomized trials, systematic reviews, clinical guidance, and expert inference should not be blended into an unexplained score.

The product should preserve provenance at the smallest useful unit. A user-visible statement should be traceable to normalized data, reasoning rules, source material, and version where applicable.

The scientific-output gate should test more than grammatical quality. It should detect:

- unsupported claims;
- citation mismatch;
- overstated certainty;
- hidden contradictions;
- evidence outside the supported population or endpoint;
- missing coverage presented as reassurance;
- inference presented as observation;
- intervention claims that omit meaningful safety constraints.

## 10. Laboratory and non-laboratory evidence

HerbaGraph began with laboratory analysis and a biomarker-to-pathway-to-intervention knowledge model. That existing laboratory engine remains an important product layer and should not be casually duplicated inside Guided Discovery.

The intended laboratory experience includes:

- multi-PDF and multi-panel ingestion;
- normalization across report formats, units, reference ranges, and dates;
- earliest-to-latest longitudinal snapshots;
- biomarker and pathway reasoning;
- evidence confidence, safety markers, and provenance;
- transparent handling of unreadable, partial, ambiguous, unsupported, and conflicting values;
- a human-verification path when extraction confidence is insufficient.

Parser confidence must be measured against representative documents and field-level truth. A polished report produced from a silently misread lab value is a severe failure.

Non-laboratory evidence includes imaging, EMG, biopsy, hearing tests, pathology, sleep studies, specialist assessments, and other prior work. MVP support may begin as inventory, attachment, and coverage-aware metadata before full parsers exist. The UI must distinguish “document stored,” “information extracted,” “human verified,” and “clinically interpreted.”

## 11. Intervention philosophy

HerbaGraph may synthesize evidence-supported botanical, nutritional, lifestyle, testing, referral-discussion, and monitoring options. It must not behave like an unconstrained supplement vending machine.

Every intervention output should consider:

- evidence strength and applicability;
- rationale tied to the Case and Investigation Map;
- contraindications, interactions, allergies, pregnancy or other relevant constraints;
- dosing uncertainty and product variability where applicable;
- what the intervention is intended to change;
- how response or harm would be monitored;
- stop conditions and professional-discussion framing;
- alternatives, including doing nothing or gathering more evidence first.

Commercial interests must remain visibly separated from scientific reasoning. HerbaGraph Gold Label may eventually provide high-quality products connected to evidence-constrained recommendations, but commerce must never secretly alter branch state, confidence, ranking, safety logic, or the presentation of scientific alternatives.

## 12. Safety and regulatory posture

HerbaGraph is non-diagnostic. It organizes information, identifies coverage gaps, explains evidence, supports investigation, and frames options for informed discussion.

It must not:

- claim to diagnose or rule out disease;
- present disease probability or diagnostic certainty;
- replace emergency services or professional medical judgment;
- fabricate test results, sources, quotations, or clinical authority;
- hide uncertainty to make the product feel more decisive;
- automatically order or initiate treatment beyond an approved and legally supported workflow.

Safety escalation should be deterministic where possible, persist across turns, be visible in the durable Case, and resist being overwritten by later generation. Disclaimers are necessary but do not replace safe behavior.

Protected health information must not appear in logs, prompts, fixtures, issues, PRs, analytics events, or commits without a specifically approved, compliant design. Use synthetic cases for development and tests.

## 13. Research and knowledge-graph direction

The long-term intelligence architecture includes:

1. A knowledge layer linking biomarkers, pathways, mechanisms, symptoms or findings, investigation families, tests, coverage, botanicals, interventions, outcomes, safety constraints, and literature.
2. A clinical-reasoning layer that applies explicit epistemic and safety rules to an individual Case.
3. A discovery layer using retrieval, embeddings, graph analytics, and potentially graph machine learning to find non-obvious but explainable relationships.

Machine learning must not bypass provenance or governance. Novel relationships should be treated as hypotheses until reviewed and supported. Automated ingestion of unreviewed relationships into production truth is not acceptable.

Research priorities should favor defensible primitives and evaluation datasets before exotic modeling. High-value assets include:

- canonical concept and test-coverage ontologies;
- gold cases with expert-reviewed investigation state;
- parser truth sets across diverse real-world formats using properly de-identified or synthetic data;
- citation-entailment and certainty evals;
- correction, replay, concurrency, and temporal-consistency tests;
- information-gain evaluations for the next-question engine;
- intervention safety and constraint benchmarks;
- longitudinal outcome schemas that avoid false causal attribution.

## 14. Product benchmarks

### MVP benchmark

MVP is a supervised, narrow-scope promise—not a count of features. It requires:

- one complete concern-to-monitoring workflow;
- truthful Case persistence under retry, correction, concurrency, rebuild, and return visits;
- coverage-aware Investigation Maps;
- supported lab ingestion with honest partial/failure states;
- traceable and appropriately qualified scientific outputs;
- safety escalation and intervention constraints;
- mandatory hostile-path and real-boundary end-to-end tests;
- repeatable CI, migrations, observability, rollback, and recovery;
- Founder UAT demonstrating that the workflow is understandable without developer interpretation.

All release gates are conjunctive. A strong UI or broad feature inventory cannot compensate for a failed truth or safety invariant.

### Beta benchmark

Beta should demonstrate that the MVP promise generalizes safely beyond the gold path:

- a bounded set of concerns, input formats, and investigation families;
- representative-user completion testing;
- measured parser and scientific-output performance;
- reliable longitudinal return visits;
- human escalation and correction workflows;
- observable failure modes and operational tripwires;
- security/privacy readiness appropriate to the data handled;
- controlled feature flags, staged rollout, and reversible UAT-to-beta promotion;
- clear support boundaries and a known-limitations register.

### Full commercial benchmark

Commercial readiness requires operational and organizational maturity in addition to product capability:

- dependable multi-tenant identity, authorization, consent, audit, privacy, and data lifecycle controls;
- validated infrastructure, backup, recovery, incident response, and support processes;
- measurable quality across parsers, citations, reasoning outputs, safety behavior, and user completion;
- versioned public contracts and migration discipline;
- legally reviewed positioning, disclaimers, partner flows, and commerce separation;
- reliable billing or commerce only after core reasoning integrity is protected;
- clinician/reviewer workflows where required;
- production monitoring capable of detecting silent scientific and data-integrity failures;
- a defensible corpus of longitudinal investigation and outcome structure built with proper consent and governance.

## 15. Product extensions and sequencing

Strategically relevant extensions include:

- persistent conversational and voice interaction;
- broader laboratory normalization;
- inventory and later parsing of imaging, EMG, pathology, biopsy, hearing, sleep, and specialist records;
- laboratory-ordering integrations such as major lab networks;
- clinician collaboration and report review;
- evidence-constrained Gold Label product matching;
- affiliate or commerce programs;
- research partnerships and grant-supported validation.

These are directions, not blanket authorization. They should be sequenced after the truth layer and evaluated against the product loop. New integrations require explicit contracts for failure, provenance, privacy, cost, vendor lock-in, and rollback.

## 16. Design principles

1. **Simple surface, rigorous core.** Do not expose internal taxonomy merely to prove sophistication.
2. **Explain the map.** A user should understand why something is open and what could change it.
3. **Show uncertainty usefully.** Uncertainty should guide action, not appear as vague hedging.
4. **Prefer cost-aware information gain.** Rank next actions by expected decision value, burden, safety, cost, and reversibility—not novelty or revenue.
5. **Preserve history.** Longitudinal truth is a product feature and a moat asset.
6. **No plausible-looking failure.** Partial, unsupported, malformed, or failed inputs must remain visibly incomplete.
7. **Evidence before aesthetics when they conflict.** Both matter, but polish must not mask scientific weakness.
8. **Human control at consequential seams.** Make review, correction, and escalation possible.
9. **Progressive disclosure.** Serve consumers, clinicians, and researchers without forcing identical detail on each.
10. **Measure the real path.** Helper-only tests and generated demos do not prove the end-to-end product.

## 17. Anti-goals

HerbaGraph must not become:

- a generic chatbot with health-themed prompts;
- a disease-probability engine;
- a static lab PDF with decorative pathway language;
- a supplement marketplace disguised as clinical reasoning;
- an opaque recommendation score;
- an ingestion system that treats every document as successfully understood;
- a graph whose edges are untraceable model guesses;
- a system that forgets negative results, corrections, or previous investigations;
- a broad feature catalogue built on an untrustworthy truth layer;
- an autonomous clinical actor that exceeds its evidence, legal, or safety authority.

## 18. Founder operating preferences

The Founder wants high development velocity without becoming a manual message router or approving routine engineering judgment.

Agents may autonomously design, implement, review, merge to `integration/agent`, deploy to Railway UAT, test, roll back, and continue when work is reversible and cannot permanently injure the project.

The Founder should be involved before:

- production or `main` promotion;
- destructive or irreversible data operations;
- breaking contracts without a proven compatibility path;
- weakening or materially redesigning security, privacy, PHI, consent, audit, provenance, citation, or safety controls;
- changing diagnosis/certainty posture, emergency routing, or medical authority;
- changing canonical Case truth, evidence semantics, correction rules, or branch-closing authority in a way that risks silent corruption;
- expanding the autonomous control plane’s permissions;
- changing the North Star, moat, positioning, monetization, ownership, or accepting durable vendor lock-in;
- accepting material residual risk with unknown blast radius or rollback.

Complexity, importance, novelty, or three failed agent passes are not by themselves Founder gates if a safe UAT experiment can resolve the uncertainty.

## 19. Codex and Grok collaboration model

- Codex normally owns product-specification quality, architecture, data-contract design, risk mapping, independent review, and merge recommendation.
- Grok Build normally implements on a dedicated `grok/<issue>-<slug>` branch and reports exact evidence.
- Codex may implement when the Founder explicitly authorizes it, using a separate `agent/<issue>-<slug>` or repository-approved branch.
- The same unexamined reasoning must not both implement and approve a substantive change. Codex-authored work still requires a cold review after a context break or an independent review surface.
- Codex and Grok must never edit the same branch concurrently.
- GitHub issues are work contracts. PRs, checks, exact SHAs, structured handoffs, and reviews are the communication loop.
- Missing evidence means unverified. “Mergeable” never means correct, tested, rebased, or approved.
- Approval applies only to the reviewed exact SHA.
- Routine agent-to-agent communication should not be manually relayed through the Founder.

## 20. Decision hierarchy and conflict handling

Use this precedence when guidance conflicts:

1. Explicit current Founder decision recorded in GitHub.
2. Accepted ADR governing the specific contract.
3. Approved issue/specification and acceptance claims.
4. Repository `AGENTS.md` and safety/security rules.
5. Product North Star.
6. This Founder Context.
7. Older chat, implementation notes, or model-generated suggestions.

Do not silently reconcile a material contradiction. Record it, preserve the safer reversible path, and escalate only if it is a genuine Founder gate.

## 21. Known strategic questions—not preapproved decisions

The following remain areas for evidence and deliberate design rather than assumed commitments:

- exact initial supported concern families beyond the gold cases;
- the validated lab-parser coverage required at each release stage;
- whether and when laboratory ordering becomes consumer-facing;
- clinician-in-the-loop requirements by workflow and jurisdiction;
- regulatory classification and claims strategy;
- commercial separation and ranking rules for Gold Label;
- the right ontology ownership and scientific-curation process;
- how discovery hypotheses graduate into reviewed knowledge;
- pricing, packaging, and channel strategy;
- external research, laboratory, EHR, or commerce partners;
- what longitudinal data may be used for model improvement under consent and privacy constraints.

Agents should propose experiments, benchmarks, and reversible options for these questions. They must not encode a durable answer without appropriate approval.

## 22. Required resumption behavior

When a designer, researcher, or engineering agent resumes work:

1. Inspect the live repository and GitHub state; do not trust a stale summary.
2. State the current branch, target, exact SHA, issue, PR, and evidence state.
3. Restate the user-visible outcome and relevant invariants.
4. Identify the highest silent-failure risk.
5. Choose the smallest vertical slice that strengthens the complete product loop.
6. Prefer an experiment or red test for the riskiest unknown.
7. Report what is written, locally verified, CI verified, deployed to UAT, and Founder accepted as separate states.
8. End every handoff with one next action and a trap line describing a reasonable but false resumption assumption.

## 23. Founder Context Sync from Chat

Founder conversations in ChatGPT may contain valuable product intent, but a raw conversation is not automatically authoritative and should not be copied wholesale into GitHub.

Use this controlled sync workflow:

1. The Founder discusses HerbaGraph normally in ChatGPT.
2. The Founder may say **“sync this to HerbaGraph”** or explicitly request a repository handoff.
3. Codex extracts only product-relevant decisions, constraints, hypotheses, rationale, open questions, and changed priorities.
4. Codex excludes unrelated personal information, credentials, real patient data, unnecessary health-identifying details, transient conversation, and abandoned brainstorming.
5. Codex classifies each extracted item as one of:
   - `DECIDED` — explicit Founder decision;
   - `PROPOSED` — requires evaluation or approval;
   - `CONTEXT` — durable rationale or preference;
   - `OPEN QUESTION` — unresolved;
   - `SUPERSEDED` — no longer controlling, with a link to the replacement.
6. Codex checks existing specs, ADRs, issues, and decisions for contradictions.
7. Codex opens a dedicated context/decision PR rather than writing directly to `main`.
8. Material one-way-door decisions receive or update an ADR and require the applicable Founder gate.
9. After merge, CLI and Grok sessions recover the change through repository authority.

If automation is later added, it should ingest an explicit structured handoff or approved summary—not scrape every ChatGPT conversation. GitHub must never receive hidden chain-of-thought, credentials, unrelated personal context, or unreviewed medical records.

## 24. Current strategic instruction

Build one trustworthy longitudinal investigation before broadening features or condition coverage. The truth layer, scientific-output gate, reliability gate, and end-to-end gold workflow are the immediate foundation of both the MVP and the Discovery Engine moat.

The standard is not “the feature exists.” The standard is: the result remains truthful, explainable, safe, reproducible, and useful when inputs are incomplete, repeated, corrected, contradictory, or wrong.

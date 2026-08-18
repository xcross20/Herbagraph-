# HerbaGraph Discovery Engine Master Technical Specification

**Status:** Proposed architecture and implementation baseline  
**Release target:** Supervised, narrow-scope MVP  
**Product loop:** Concern → Discovery → Investigation → Evidence → Intervention → Monitoring  
**Primary rule:** No new major feature work until the truth layer, scientific-output gate, reliability gate, and required end-to-end tests pass.

## 1. Outcome

HerbaGraph may be called MVP-ready only when a supported user can complete the entire product loop and the resulting case remains truthful across persistence, retries, corrections, return visits, document failures, and conflicting evidence.

The MVP is not defined by the number of screens or features. It is defined by one narrow promise that works reliably:

> HerbaGraph accepts a health concern and prior evidence, builds a non-diagnostic investigation map, accurately explains what the evidence does and does not address, incorporates supported laboratory results, presents traceable and appropriately qualified options, and preserves the case correctly over time.

## 2. Evidence status at plan creation

### Verified by the latest review

The reviewed Discovery V2 path has five merge-blocking defects:

1. Coverage relations can be written using an incompatible evidence enum, silently dropping important “does not address” evidence.
2. Tests without applicable coverage can be stored as inconclusive evidence on unrelated branches.
3. Findings, gaps, workups, interpretations, timeline events, and evidence can be appended repeatedly because identity/deduplication is ineffective.
4. Inactive findings can be fed into the legacy snapshot rebuild and become active-looking facts again.
5. Correction records can identify the replacement as the original claim instead of linking the actual original and replacement.

Additional reviewed weaknesses include missing live supersession, reversed predecessor linkage, an unused branch-resolution governor, and database uniqueness rules that exist in models but not migrations.

### Reported but requiring repository verification

- Existing laboratory parser and staged analysis pipeline
- Biomarker normalization and pathway mapping
- Evidence and literature retrieval
- Intervention library and report generation
- Authentication and patient infrastructure
- Persistent cases and turns
- Two-pass Discovery guide
- Investigation-map experience
- Voice and longitudinal memory features
- Finding-driven S0–S4 safety behavior

### Unknown until repository access returns

- Exact state of `main`, V2 branches, migrations, CI, and deployment
- Whether any reviewed blockers have already been repaired
- Current unit, integration, and end-to-end pass rates
- Production commit, configuration, telemetry, and rollback state
- Measured parser accuracy and real-user completion performance

Unknown does not count as passing.

## 3. MVP scope lock

### In scope

- One supported concern-to-monitoring flow
- Structured Case, Finding, Branch/Hypothesis, Gap, Workup, Evidence, Intervention, and Monitoring state
- Patient-reported findings and corrections
- Prior-test inventory, initially including a normal EMG example
- Explicit test-coverage relationships
- Supported digital and scanned laboratory reports
- Existing biomarker, pathway, evidence, safety, and intervention capabilities
- Investigation map, evidence gaps, uncertainty, provenance, and report output
- Return visits and longitudinal updates
- Human-visible handling of partial, failed, unsupported, and uncertain inputs
- Safety escalation without diagnosis

### Explicit non-goals for MVP

- Diagnosing disease
- Autonomous medical treatment decisions
- Unsupervised consumer laboratory ordering
- MRI, CT, pathology, specialist-network, sleep-study, or broad diagnostic integration beyond inventory/attachment
- Enterprise administration, EHR integration, or payer workflows
- Automated ingestion of unreviewed scientific relationships into the production knowledge graph
- Major frontend rewrite or migration to a new framework
- Broad condition coverage before the gold-standard workflow is proven
- Gold Label commerce optimization beyond a clearly separated, evidence-constrained link

Any proposed addition must either protect a release gate or wait until after MVP acceptance.

## 4. Release gates

The release decision is conjunctive: **all gates pass**. A weighted average cannot compensate for a failed truth or safety invariant.

| Gate | Pass condition |
| --- | --- |
| Scope | Supported inputs, outputs, user, and non-goals are documented and enforced |
| Data integrity | Every persisted fact and relationship remains correct under retry, correction, concurrency, and rebuild |
| Scientific output | Every material output is traceable, qualified, non-diagnostic, and coverage-aware |
| Safety | Critical findings produce the required escalation and cannot be bypassed by generation or persistence |
| End-to-end | Mandatory gold cases pass through real boundaries, not helper-only tests |
| Reliability | CI, migrations, deployment, observability, rollback, and recovery are repeatable |
| Human acceptance | Founder can complete and understand the gold workflow without developer interpretation |

## 5. Architecture decisions required before fixes

These decisions affect persisted data or public contracts and require short ADRs before Grok implements them.

### ADR-MVP-001: Canonical case truth

Decide that normalized V2 entities are the canonical source of truth and that the legacy snapshot is a derived compatibility projection. The projection must never reactivate inactive history or create new truth.

Required invariants:

- Each fact has one current active representation per applicable identity.
- Historical rows remain queryable but cannot re-enter the active projection.
- Rebuilding a projection is deterministic and idempotent.
- A projection failure cannot mutate canonical state.

### ADR-MVP-002: Coverage and evidence semantics

Define one explicit mapping between test coverage and branch evidence.

Minimum semantic states:

- `directly_assesses`
- `partially_assesses`
- `does_not_directly_assess`
- `not_applicable`
- `unknown_coverage`

Evidence must separately describe what the result does:

- `supports`
- `weakens`
- `does_not_address`
- `resolves_gap`
- `inconclusive`

`not_applicable` must produce no branch-evidence edge. Coverage and result interpretation must not share an enum merely because their strings look related.

### ADR-MVP-003: Mutation identity and idempotency

Define stable identity keys and retry behavior for every mutation:

| Entity | Candidate identity |
| --- | --- |
| Finding | case + normalized concept + normalized value + source event/turn |
| Open branch | case + branch code |
| Open gap | case + gap code + active state |
| Workup | case + canonical test + occurrence/date + normalized result |
| Evidence edge | case + branch + workup/source + relationship + version |
| Interpretation | case + normalized statement + provenance + version |
| Timeline event | case + event type + source event/turn |
| Monitoring event | case + target + observation time + source event |

Every command/event needs an idempotency key or deterministic identity. A replay must return the same state, not append equivalent rows.

### ADR-MVP-004: Correction and supersession model

Define:

- how the original fact/claim is resolved;
- how the original becomes inactive or superseded;
- how the replacement points to its predecessor;
- whether corrections may be reversed;
- how ambiguous corrections request clarification;
- how history appears in the active projection and audit view.

Never overwrite history and never display inactive history as current truth.

### ADR-MVP-005: Branch lifecycle

Define legal transitions among not evaluated, partially evaluated, evaluated, closed, and reopened. All close requests must pass the coverage governor. A test that does not directly evaluate a branch cannot close it.

## 6. Execution program

### Milestone 0 — Reconstruct the actual baseline

**Objective:** Establish exactly what exists before changing behavior.

Tasks:

1. Identify the production commit, default branch, V2 branch/PR, and latest migration revision.
2. Capture current CI jobs, failing steps, test commands, and deployment status.
3. Build a feature inventory with five states: verified, reported, partial, broken, not started.
4. Run the existing test suite without modification and archive the exact result.
5. Run migrations from an empty database and from the last supported schema.
6. Reproduce all reviewed defects with minimal fixtures.
7. Confirm which feature flags are active in test, staging, and production.
8. Record external dependencies and required secrets without exposing secret values.

Deliverables:

- Baseline report with commit SHAs and commands
- Current schema diagram or entity inventory
- CI/deployment failure inventory
- Reproduction log for every known blocker
- Initial traceability matrix from product step to code path and test

Exit condition:

- Every previously reported capability and defect has an evidence state.
- No implementation begins from an assumed branch or undocumented schema.

### Milestone 1 — Write independent red tests

**Objective:** Freeze expected behavior before changing code.

Create failing tests for:

1. Normal EMG on a small-fiber branch persists `does_not_address` and leaves the branch open.
2. EMG does not attach to an unrelated biliary branch.
3. Unknown/unmatched tests produce no evidence edge rather than `inconclusive`.
4. Replaying the same turn produces no additional semantic rows.
5. A later unrelated turn does not recreate default findings or gaps.
6. A corrected fact becomes inactive and remains absent from the active projection after rebuild.
7. A correction links the actual original claim and the replacement claim.
8. The replacement finding points to its predecessor.
9. A non-addressing test cannot close a branch or set `resolved_at`.
10. Concurrent attempts cannot create duplicate branch, gap, alias, or evidence identities.

Rules:

- Expected values come from the approved spec/ADR, never from current output.
- Each test must be observed failing for the intended reason.
- Helper-only tests do not satisfy persistence or API-path claims.
- Production-like database behavior is required for uniqueness and concurrency tests.

Deliverable: red-first log containing test name, command, failure message, and violated invariant.

Exit condition: every known blocker has a correctly failing regression test.

### Milestone 2 — Repair evidence applicability

**Objective:** Ensure evidence appears only on the branches it actually addresses.

Tasks:

1. Introduce one coverage-to-evidence mapping boundary.
2. Make `not_applicable` result in no edge.
3. Preserve `does_not_directly_assess` as `does_not_address` evidence where appropriate.
4. Separate coverage classification from result interpretation.
5. Replace substring-only resolution where ambiguity can misidentify a test.
6. Require canonical test identity or an explicit unresolved state.
7. Update investigation-map serialization to represent non-addressing, partial, contradictory, and unresolved evidence.
8. Add metrics for discarded/unknown mappings rather than silently continuing.

Acceptance:

- EMG/small-fiber evidence is visible and correctly qualified.
- EMG/biliary produces no relationship.
- Unknown MRI text is not silently resolved to brain MRI.
- No conversion error silently drops evidence.
- The branch remains open unless directly resolving evidence satisfies the branch policy.

### Milestone 3 — Make persistence idempotent and concurrency-safe

**Objective:** Make repeated or concurrent processing produce one semantic result.

Tasks:

1. Persist source turn/event identifiers on every applicable mutation.
2. Implement stable identity keys from ADR-MVP-003.
3. Add database uniqueness constraints matching model constraints.
4. Use database-safe upsert or conflict handling; do not rely only on read-then-insert.
5. Stop reopening an already-open default gap.
6. Stop reinserting equivalent interpretations, evidence, workups, or timeline events.
7. Add transaction boundaries so partial batches do not leave plausible partial success.
8. Define retry behavior after timeout/unknown commit outcome.
9. Add duplicate, rapid-repeat, and two-worker concurrency tests.

Acceptance:

- One turn processed 1, 2, or 10 times yields the same semantic state.
- Two workers processing the same turn cannot create duplicates.
- Failed batches roll back or expose an explicit partial/failed state.
- Database constraints and ORM models agree.

### Milestone 4 — Repair correction, history, and projection

**Objective:** Preserve history without allowing obsolete facts to become current.

Tasks:

1. Resolve or create the true original claim before applying a correction.
2. Create the replacement and link it to the original.
3. Mark original claims/findings inactive or superseded with audit metadata.
4. Emit supersession from the live turn-reconciliation path.
5. Filter inactive entities from active prior-fact reads and compatibility projections.
6. Make rebuild deterministic and read-only with respect to canonical truth.
7. Preserve inactive rows in history/audit views.
8. Handle correction of a correction and ambiguous matches.
9. Test return visits after rebuild and application restart.

Acceptance:

- Old facts never reappear as active.
- History remains inspectable.
- Foreign keys identify the actual original and replacement.
- A correction replay is idempotent.
- Active UI, prompt context, investigation map, and report all use the same current fact.

### Milestone 5 — Enforce branch lifecycle and gap truth

**Objective:** Prevent unsupported closure or disappearance of open questions.

Tasks:

1. Route every proposed status transition through one lifecycle governor.
2. Require directly assessing evidence and branch-specific resolution criteria for closure.
3. Represent partial evaluation separately from closure.
4. Preserve contradictory and non-addressing evidence.
5. Reopen a branch only through an explicit new finding/evidence rule.
6. Keep gaps linked to the branches and evidence that created/resolved them.
7. Test every legal and illegal transition.

Acceptance:

- A normal EMG does not close small-fiber investigation.
- Direct evidence may close a branch only when its configured criteria are met.
- Partial evidence cannot be rendered as resolved.
- Closing and reopening are auditable and idempotent.

### Milestone 6 — Establish the scientific-output contract

**Objective:** Make every displayed conclusion reconstructable and appropriately qualified.

Implement a structured output contract in which each material item includes, as applicable:

- stable identifier and version;
- item type: observation, patient report, system inference, literature claim, gap, possibility, or intervention option;
- source/provenance;
- evidence strength;
- case-specific confidence, separately expressed;
- supporting evidence;
- weakening or contradictory evidence;
- non-addressing evidence;
- missing information/coverage gaps;
- safety constraints and contraindications;
- rationale for inclusion;
- last-evaluated timestamp and knowledge/evidence version;
- non-diagnostic language and appropriate next-review context.

Acceptance:

- No material report statement is source-less.
- Evidence strength is not conflated with confidence in a case interpretation.
- Absence of evidence is not expressed as negative evidence.
- A normal non-addressing test is explicitly explained.
- Contradictions and uncertainty remain visible.
- Intervention options are separated from diagnoses and prescriptions.
- Gold Label commerce cannot increase scientific ranking or suppress alternatives.
- The same stored case and version reproduce the same structured report inputs.

### Milestone 7 — Connect intervention and monitoring

**Objective:** Close the MVP loop rather than ending at an investigation map.

Tasks:

1. Link each intervention option to applicable findings/pathways, evidence, constraints, and safety checks.
2. Define what the user is monitoring and over what interval.
3. Record adherence/exposure separately from outcome.
4. Preserve baseline and subsequent measurements.
5. Avoid attributing causality from temporal association.
6. Allow stop, adverse-effect, and no-change outcomes.
7. Recalculate the case without deleting prior reasoning.

Acceptance:

- Every suggested option explains why it appeared and what would make it inappropriate.
- Monitoring captures no change and adverse effects, not only improvement.
- Follow-up does not present observed change as proven causation.
- The case remains longitudinally coherent after multiple monitoring events.

### Milestone 8 — Make CI, deployment, and operations trustworthy

**Objective:** Ensure the verified product is the product that can actually ship.

Tasks:

1. Repair all required CI jobs, including reseed/migration gates.
2. Make one documented command run the mandatory MVP suite.
3. Test clean install, clean migration, upgrade migration, and rollback/forward-fix strategy.
4. Establish staging with production-like database behavior.
5. Record build provenance and visible application version.
6. Add structured, PHI-safe telemetry for parse outcomes, mutation outcomes, duplicate suppression, branch transitions, report generation, and safety escalation.
7. Define alerts/tripwires and first-response actions.
8. Test backup restoration.
9. Deploy dark/flagged, run synthetic probes, then enable for a supervised cohort.

Exit condition:

- Three consecutive CI runs on the release candidate pass without reruns or ignored failures.
- Two clean staging deployments complete successfully.
- Required synthetic probes pass after deployment.
- Rollback or forward-fix behavior has been exercised.
- No unresolved severity-1 or severity-2 defect remains.

## 7. Data integrity gate

Every item is mandatory.

### Entity integrity

- DI-01: Every entity has a stable identifier, owner, lifecycle, and active/history semantics.
- DI-02: Model declarations and database migrations express the same constraints.
- DI-03: Referential integrity prevents orphan evidence, corrections, gaps, and monitoring records.
- DI-04: Cross-user and cross-case relationships are impossible at the database/service boundary.

### Idempotency and concurrency

- DI-05: Replaying any accepted turn or document event does not change semantic state.
- DI-06: Two concurrent workers cannot create duplicate active identities.
- DI-07: Retry after an unknown commit result is safe.
- DI-08: A failed batch cannot appear fully successful.

### History and corrections

- DI-09: Corrections retain original and replacement records with correct links.
- DI-10: Inactive facts never appear in active prompts, maps, or reports.
- DI-11: Rebuild, restart, and return visit preserve the same active truth.
- DI-12: Corrections and supersessions are themselves replay-safe.

### Evidence relationships

- DI-13: `not_applicable` creates no evidence edge.
- DI-14: Non-addressing evidence remains visible but cannot weaken or close a branch.
- DI-15: Contradictory, partial, and unresolved evidence retain their distinct semantics.
- DI-16: Every evidence edge identifies its case, branch, source/workup, relation, and version.

### Document state

- DI-17: Success, valid-empty, partial, unsupported, and failed are distinct terminal outcomes.
- DI-18: Parser exceptions, timeouts, and truncated inputs never become successful empty reports.
- DI-19: Duplicate documents are detected or explicitly versioned.
- DI-20: Field corrections do not overwrite source extraction history.

**Pass rule:** 100% of DI-01 through DI-20 are demonstrated by tests or inspection evidence. No waiver is permitted for DI-04, DI-08, DI-10, DI-13, DI-14, DI-17, or DI-18.

## 8. Scientific output gate

### Claim discipline

- SO-01: The system distinguishes observed data, patient report, inference, literature claim, hypothesis/branch, and option.
- SO-02: It does not diagnose or imply diagnostic certainty.
- SO-03: Every material inference has a visible rationale.
- SO-04: Confidence language follows a defined vocabulary and calibration rubric.

### Evidence and provenance

- SO-05: Every material literature claim has a retrievable citation.
- SO-06: Evidence strength and case-specific confidence are separate fields.
- SO-07: Contradictory and weakening evidence remains visible.
- SO-08: Source versions and access/evaluation dates are recorded.
- SO-09: Missing evidence and non-addressing evidence are not treated as negative results.

### Coverage and uncertainty

- SO-10: Every prior test explains what it directly, partially, and does not assess.
- SO-11: Remaining gaps are linked to a branch and a decision they could change.
- SO-12: Recommendations are ranked by information value, safety, burden, and cost when those inputs are available—not disease certainty.

### Intervention safety

- SO-13: Every intervention option links to rationale, evidence strength, constraints, and relevant contraindication checks.
- SO-14: Safety escalation can suppress ordinary suggestion flow when required.
- SO-15: Commerce relationships cannot alter evidence assessment or ranking.

### Reproducibility and human evaluation

- SO-16: The same case snapshot and evidence version reproduce the same structured claims, allowing controlled wording variation only where documented.
- SO-17: A clinician/reviewer can reconstruct why each material item appeared.
- SO-18: Gold-case outputs contain all mandatory statements and none of the prohibited statements.
- SO-19: At least two qualified reviewers independently evaluate the initial gold corpus using the same rubric; disagreements are recorded and adjudicated.

**Pass rule:** All safety/provenance rules pass. At least 90% of noncritical human-rubric items pass on the first review, 100% after adjudicated correction. No prohibited diagnosis, unsupported certainty, missing critical warning, or source fabrication is permitted.

## 9. Reliability gate

### CI and build

- RL-01: Required unit, integration, migration, security, and end-to-end jobs are green.
- RL-02: Three consecutive release-candidate runs pass without manual reruns.
- RL-03: Builds are reproducible and identify commit/configuration version.

### Database and deployment

- RL-04: Empty-database and upgrade migrations pass.
- RL-05: Migration failure behavior and recovery are documented and tested.
- RL-06: Two consecutive staging deployments pass synthetic probes.
- RL-07: Backup restoration is successfully demonstrated.

### Runtime behavior

- RL-08: No silent failure is allowed on parser, persistence, safety, evidence, or report boundaries.
- RL-09: External calls have timeouts, bounded retries, and defined user-visible failure behavior.
- RL-10: Duplicate/out-of-order async delivery is handled or explicitly prevented.
- RL-11: Resource and rate limits produce safe degradation.

### Observability

- RL-12: Feature-level counters track attempted, succeeded, partial, and failed operations.
- RL-13: Correctness signals detect failed-parse→successful-report, inactive-fact resurrection, duplicate growth, unrelated evidence attachment, and invalid branch closure.
- RL-14: Logs contain correlation identifiers but no unnecessary PHI, secrets, or raw documents.
- RL-15: Each critical signal has a threshold and first-response action.

### Provisional MVP service targets

- 100% of safety-critical synthetic cases handled correctly.
- 0 known silent data-integrity failures.
- 0 unresolved severity-1 or severity-2 defects.
- At least 99% successful completion across 200 repeated synthetic gold-flow executions in staging, excluding deliberately invalid inputs that must fail visibly.
- 100% of deliberately failed/partial inputs produce the correct visible state.
- No unbounded row growth across 100 replays/return turns.

Performance targets should be baselined before setting hard values. Responsiveness may be streamed, but correctness and truthful status cannot be traded for latency.

## 10. Required test architecture

### Layer A — Pure unit tests

Cover normalization, enum mapping, lifecycle transition rules, confidence wording, safety rules, identity construction, and report-claim construction. These are fast and exhaustive but do not prove persistence.

### Layer B — Database integration tests

Use the production database engine/version. Cover constraints, transactions, upserts, retries, concurrency, inactive filtering, correction links, migrations, and projection rebuilds. SQLite-only results do not prove PostgreSQL concurrency or constraint behavior.

### Layer C — Boundary integration tests

Exercise real service boundaries for parsing, literature retrieval adapters, LLM structured outputs, storage, and report creation. Use recorded/synthetic fixtures with independently authored expected results. Mocks may test local failure handling but cannot be the only proof of an external contract.

### Layer D — API/stream tests

Exercise case creation, turn streaming, document upload, investigation-map retrieval, correction, rebuild, intervention selection, and monitoring. Assert persisted state after the stream completes or fails.

### Layer E — Browser end-to-end tests

Use the actual interface for the gold paths. Assert what the user can see: failure/partial states, provenance, gaps, non-addressing evidence, corrections, safety escalation, and return-visit continuity.

### Layer F — Scientific output evaluations

Evaluate structured output before prose. Use exact mandatory/prohibited concepts plus reviewer rubrics. Store input case, expected claims, allowed variation, evidence version, model/prompt version, and result.

### Layer G — Operational tests

Cover migrations, deploy, health probes, backup restoration, rollback/forward fix, feature flags, alerts, and synthetic production-like probes.

## 11. Mandatory end-to-end cases

### E2E-01: Burning feet with normal EMG

Required assertions:

- Concern and symptom findings are captured with provenance.
- Safety screen runs.
- Relevant branches are opened without diagnosis.
- Normal EMG is recorded once.
- EMG is shown as not directly addressing small-fiber structure/function as configured.
- Small-fiber branch remains open or partially evaluated.
- Remaining coverage gap is explicit.
- Suggested next step is explained by information value and constraints.
- Return visit does not duplicate state.
- Monitoring can be added without rewriting history.

Prohibited output:

- “The normal EMG rules out neuropathy.”
- Any definitive diagnosis.
- Treating missing small-fiber evidence as normal.

### E2E-02: Gallbladder concern plus later unrelated EMG

- Patient interpretation is distinct from an objective finding.
- Biliary branch/gaps reflect applicable symptom evidence.
- Later EMG creates no biliary evidence edge.
- Original default gaps are not recreated on every turn.
- The investigation map remains coherent.

### E2E-03: Correction and return visit

- User corrects symptom location/value.
- Original is preserved but inactive.
- Replacement links to original.
- Active map, prompt context, and report use only the replacement.
- Rebuild, restart, and later turn do not resurrect the original.
- Repeating the correction makes no duplicate history.

### E2E-04: Duplicate and concurrent turn

- Same turn is delivered repeatedly and concurrently.
- One semantic set of findings, branches, gaps, workups, evidence, and timeline events exists.
- Responses identify already-processed state or safely converge.

### E2E-05: Multi-date laboratory trend

- Two supported reports are uploaded in either order.
- Dates, units, reference ranges, and provenance remain tied to each observation.
- Earliest-to-latest trend is correct.
- Duplicate upload does not create a false new time point.
- Conflicting or corrected results remain auditable.

### E2E-06: Parser truthfulness

Run valid digital, valid scanned, valid-with-no-supported-tests, partial, malformed, encrypted/unsupported, truncated, timeout, and duplicate documents.

- Each produces the correct distinct state.
- Failed/unsupported never renders a successful empty report.
- Partial extraction exposes warnings and coverage.
- No raw document or PHI leaks into logs.

### E2E-07: Safety escalation

- A synthetic red-flag finding activates the correct S-level behavior.
- Ordinary suggestions are constrained or suppressed as specified.
- Language is urgent but non-diagnostic.
- Safety state persists across refresh/return.
- LLM output cannot override the deterministic safety decision.

### E2E-08: Evidence contradiction

- Supporting and weakening evidence coexist.
- The system does not collapse the branch to a single confident answer.
- Uncertainty and next discriminating information are visible.
- Citations resolve to the intended claims.

### E2E-09: Intervention to monitoring

- Option is linked to rationale, evidence, and safety constraints.
- User records exposure/adherence and outcome separately.
- No change and adverse effect are supported.
- Follow-up avoids causal overclaiming.
- History remains versioned.

### E2E-10: Authorization and isolation

- User A cannot access or infer User B's case, document, report, identifiers, or logs.
- Sequential and guessed identifiers do not bypass authorization.
- Administrative access is logged and constrained.

## 12. Parser benchmark

Build a versioned, de-identified/synthetic corpus covering the supported MVP formats. Each fixture must include ground truth authored independently from parser output.

Measure:

- document outcome classification;
- patient/report identity where retained;
- collection date;
- biomarker identity;
- value and comparator;
- unit;
- reference range;
- abnormal flag;
- page/source coordinates;
- confidence/confirmation requirement.

Provisional pass thresholds for supported formats:

- Digital text PDFs: at least 98% exact field-level accuracy.
- Supported scanned PDFs: at least 95% exact field-level accuracy.
- 100% correct classification of failed, unsupported, partial, valid-empty, and successful documents.
- 100% of emitted observations retain source provenance.
- Any field below the approved confidence threshold is clearly flagged for confirmation rather than silently accepted.
- No fabricated biomarkers or values are permitted.

If a format does not meet the threshold, remove it from supported MVP scope and fail visibly rather than lowering the truth standard.

## 13. Traceability matrix

Maintain one release artifact with these columns:

| ID | Acceptance claim/invariant | Implementation | Unit test | Integration test | E2E case | Signal/tripwire | Status | Evidence link |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

Allowed status values:

- not started
- written, unverified
- locally verified
- CI verified
- staging verified
- founder accepted

No item may skip directly from written to complete.

## 14. Pull request sequence

Keep PRs reviewable and dependency-ordered.

1. **PR-A: Baseline and red tests** — no production behavior changes.
2. **PR-B: Coverage/evidence applicability** — fixes reviewed Issues 1–2.
3. **PR-C: Idempotency and database constraints** — fixes Issue 3 and concurrency integrity.
4. **PR-D: Corrections, supersession, active projection** — fixes Issues 4–7.
5. **PR-E: Branch lifecycle governor** — fixes Issue 8 and transition tests.
6. **PR-F: Scientific-output contract** — provenance, uncertainty, contradiction, coverage, and safety structure.
7. **PR-G: Intervention and monitoring completion** — narrow gold-flow completion only.
8. **PR-H: End-to-end suite and release command** — API, browser, scientific eval, and operational checks.
9. **PR-I: Observability and staged rollout** — correctness signals, tripwires, runbook, and release flag.

Each PR must include a spec reference, claim-to-test mapping, hostile trace, exact commands/results, migration/rollback impact, and Grok handoff. Codex reviews the actual diff; the founder decides product tradeoffs and production promotion.

## 15. Roles and decision rights

### Founder

- Approve MVP scope and non-goals.
- Resolve product, clinical-posture, commerce-separation, and user-experience tradeoffs.
- Accept residual risks explicitly.
- Approve release to supervised users and any production promotion.

### Codex

- Convert each milestone into issue-level acceptance claims.
- Approve ADRs and one-way-door decisions.
- Maintain the risk map and traceability matrix.
- Review PR diffs and CI evidence independently.
- Run hostile traces and issue merge recommendations.
- Refuse release when a mandatory gate lacks evidence.

### Grok Build

- Reproduce defects and write/execute the implementation.
- Work only on dedicated issue branches.
- Keep commits atomic and scope-controlled.
- Produce exact commands, results, changed contracts, deviations, and trap line.
- Stop before unapproved schema/public-contract/safety changes.

## 16. First implementation packet for Grok

Do not send the entire program as one coding task. The first assignment is Milestones 0–1 only.

```markdown
## TASK: Establish the Truthful MVP baseline and red-test harness

Objective:
Reconstruct the current repository state and encode every known Discovery V2 integrity defect as an independently specified failing test. Do not repair production behavior in this task.

Required work:
1. Identify main/V2/integration commits, migration head, active flags, CI commands, and production/staging version if available.
2. Run the current tests and record exact results.
3. Reproduce reviewed Issues 1–9.
4. Add red-first tests for coverage mapping, unrelated evidence, turn replay, correction/history, active projection, branch closure, and database uniqueness/concurrency.
5. Use production-equivalent PostgreSQL for persistence/concurrency claims.
6. Produce the initial traceability matrix.

Non-goals:
- No production behavior fix.
- No refactor.
- No new feature.
- No framework migration.

Stop and request architecture review if:
- the reviewed files no longer match the branch;
- a schema/public contract must change to express a test;
- the existing behavior contradicts the proposed ADR semantics;
- a known defect cannot be reproduced.

Required handoff:
Issue, branch, head SHA, draft PR, baseline commands/results, red-first log, schema/flag inventory, deviations, decisions needed, next action, and trap line.
```

## 17. Final MVP release review

Codex prepares one release packet containing:

1. Scope and supported-format declaration
2. Accepted ADRs
3. Closed blocker list
4. Completed traceability matrix
5. Data-integrity gate report
6. Scientific-output gate report
7. Safety gate report
8. End-to-end results with fixtures and versions
9. Parser benchmark results
10. Three consecutive CI run links
11. Staging deployment and synthetic-probe evidence
12. Backup/restore and rollback evidence
13. Known limitations and declared gaps
14. Founder acceptance record

### Release verdicts

- **BLOCKED:** any critical invariant, safety case, provenance requirement, CI gate, migration, or required E2E case fails or lacks evidence.
- **SUPERVISED MVP:** every mandatory gate passes; use is limited to the declared scope with active monitoring and human review.
- **BETA CANDIDATE:** supervised MVP operates without critical incident for the agreed observation cohort/period and beta-specific privacy, support, and operational controls are complete.

## 18. Current recommendation

Begin with baseline reconstruction and red tests. Do not begin by fixing the most visible UI symptom, and do not allow feature work to run in parallel with canonical-state repairs unless it is completely isolated and cannot touch the product loop.

The MVP milestone is achieved when HerbaGraph is not merely impressive on a fresh demonstration, but remains truthful after the inputs, timing, and history become difficult.

## 19. Discovery-engine moat specification

### 19.1 Moat thesis

HerbaGraph's defensible advantage is not an LLM chat interface, generic retrieval, a PDF parser, or a large prompt. Those components are replaceable. The moat is a governed, longitudinal **Investigation Intelligence Graph** that learns which missing information matters, what existing evidence actually covers, which next action has the highest decision value, and how the investigation changes over time.

The moat has five connected assets:

1. **Coverage Graph:** test/method → directly assesses, partially assesses, does not assess, applicability, limitations, and result implications.
2. **Longitudinal Investigation Graph:** concerns, findings, branches, gaps, workups, evidence, corrections, decisions, and branch transitions over time.
3. **Next-Best-Investigation Engine:** transparent ranking of questions, records, and tests by information value, safety, actionability, cost, burden, and redundancy.
4. **Outcome Graph:** intervention exposure, adherence, baseline, follow-up, no-change, improvement, adverse effect, confounders, and branch updates.
5. **Gold Evaluation Corpus:** expert-authored expected structures, required/prohibited claims, coverage relationships, safety behavior, and adjudicated disagreements.

### 19.2 Weak versus strong defensibility

| Capability | Defensibility |
| --- | --- |
| LLM conversation, generic RAG, basic symptom intake | Low |
| PDF parsing, biomarker explanation, attractive map UI | Low to medium |
| Curated versioned coverage ontology | Medium to high |
| Longitudinal case graph with negative/non-addressing evidence | High |
| Outcome-linked investigation trajectories | High and compounding |
| Expert-adjudicated gold corpus and calibrated next-action ranking | High and compounding |
| Workflow adoption, clinical trust, integrations, and governance | High switching cost |

### 19.3 Discovery Intelligence Gate

Every item is mandatory for the MVP moat seed:

- DG-01: Every generated question links to the branch and gap it is intended to clarify.
- DG-02: Every suggested investigation explains what decision its result could change.
- DG-03: Every recognized prior test has explicit coverage semantics and limitations.
- DG-04: The engine suppresses redundant questions unless new context justifies repetition.
- DG-05: Next actions are ranked by explicit decision value, not implied disease probability.
- DG-06: Safety urgency can override ordinary information-gain ranking.
- DG-07: Cost, burden, accessibility, and user preferences are represented when available.
- DG-08: Corrections alter subsequent reasoning without erasing history.
- DG-09: Return visits continue the existing investigation rather than restart it.
- DG-10: Contradictory, weakening, and non-addressing evidence remain visible.
- DG-11: Every branch transition records reason, triggering evidence, rule/engine version, and time.
- DG-12: Monitoring observations feed back into the branch graph without causal overclaiming.
- DG-13: Expert disagreement is captured as structured adjudication data.
- DG-14: Production reasoning can be replayed against the same case, ontology, evidence, prompt, and model versions.
- DG-15: No beta observation changes production ontology or ranking rules without validation and promotion.

### 19.4 Moat benchmarks

**MVP seed:** at least 25 independently authored variants inside the narrow supported domain; 100% of critical required/prohibited assertions; zero unrelated evidence edges; zero silent coverage loss; every question/action linked to a gap; every branch transition reproducible.

**Controlled beta:** at least 100–300 synthetic, de-identified, or appropriately consented investigation episodes reviewed with a consistent rubric; fixed holdout cases; measured question utility, evidence applicability, clinician agreement, correction rate, and branch-transition quality.

**Commercial:** versioned coverage ontology across supported domains; large outcome-linked longitudinal corpus; repeat expert adjudication; calibrated ranking; governed production promotion; clear data rights; workflow integration; demonstrated improvement over baseline/version history.

## 20. Target system architecture

Preserve the current FastAPI, SQLAlchemy, PostgreSQL, and static HTML/JavaScript application. Extend the existing lab, pathway, evidence, intervention, report, auth, and patient infrastructure. Do not rewrite the product to obtain architectural cleanliness.

### 20.1 Layer model

```text
User / Clinician
       │
       ▼
Conversation + Workspace UI
       │
       ▼
Discovery Orchestrator
  ├── deterministic safety governor
  ├── structured planner/composer boundary
  ├── entity resolver
  ├── mutation builder
  └── next-best-investigation ranker
       │
       ▼
Canonical Investigation Graph
  Case ─ Findings ─ Branches ─ Gaps
   │         │          │       │
   ├── Turns/Events      ├── Evidence ─ Workups/Documents
   ├── Corrections       ├── Decisions
   ├── Interventions     └── Transitions
   └── Monitoring
       │
       ├───────────────┐
       ▼               ▼
Existing Lab Engine   Evidence/Knowledge Graph
       │               │
       └───────┬───────┘
               ▼
       Structured Scientific Output
               │
               ▼
       Derived UI/Report/Snapshot Projections
```

### 20.2 Ownership rules

- Canonical tables own investigation truth.
- Legacy snapshots are derived, replaceable projections.
- Deterministic governors own safety, coverage semantics, legal state transitions, and output validation.
- LLMs propose structured plans and wording; they do not directly mutate canonical state.
- Resolvers canonicalize known entities or return unresolved/ambiguous; they never guess silently.
- The knowledge graph is versioned and promoted through draft → validated → production.
- Monitoring records observation and exposure; it does not infer causality automatically.

### 20.3 Boundary contracts

Every boundary returns an explicit outcome object:

```text
status: succeeded | valid_empty | partial | unsupported | failed
data: typed payload or null
warnings: structured list
errors: structured list safe for the caller
provenance: source/version metadata
correlation_id: stable request/turn/document identifier
```

No boundary may convert exception/timeout/validation failure into `[]`, `{}`, or a successful report.

## 21. Canonical domain model

Exact column names should match house style after repository inspection. The semantics below are required.

### 21.1 Case

Required fields:

- `id`, `owner_id`, `status`, `presenting_concern`
- `created_at`, `updated_at`, `closed_at`
- `active_snapshot_version`
- `consent_scope`, `permitted_learning_use`
- `engine_version`, `ontology_version`

Invariant: one case belongs to one authorized owner/tenant; cross-case edges are forbidden.

### 21.2 Turn and source event

- `id`, `case_id`, `idempotency_key`
- `actor_type`, `channel`, `raw_input_ref`
- `received_at`, `processing_status`, `completed_at`
- `planner_version`, `model_version`, `prompt_version`
- `error_class`, `retry_of_turn_id`

Invariant: accepting the same idempotency key returns/converges on the same semantic result.

### 21.3 Finding

- `id`, `case_id`, `concept_code`, `value`, `value_normalized`
- `finding_type`, `provenance_type`, `source_turn_id`, `source_document_id`
- `observed_at`, `recorded_at`
- `is_active`, `supersedes_finding_id`, `superseded_at`, `superseded_by_actor`
- `confidence`, `confirmation_state`

Invariant: inactive findings remain historical and never enter active reasoning projections.

### 21.4 Branch

- `id`, `case_id`, `code`, `label`, `status`
- `opened_at`, `last_evaluated_at`, `resolved_at`, `reopened_at`
- `opened_reason`, `resolution_reason`
- `lifecycle_rule_version`

Suggested statuses: `not_evaluated`, `partially_evaluated`, `evaluated_open`, `closed`, `reopened`.

Invariant: `(case_id, code)` is unique; transitions occur only through the lifecycle governor.

### 21.5 Gap

- `id`, `case_id`, `branch_id`, `code`, `description`
- `status`, `opened_at`, `resolved_at`
- `resolution_evidence_id`, `priority_inputs`

Invariant: one active `(case_id, branch_id, code)` gap; closed gaps are historical.

### 21.6 Workup and document

- canonical test/method identity plus raw user/source label;
- occurrence/specimen/result date;
- normalized result state;
- source document/page/coordinates;
- parser outcome and version;
- user confirmation/correction state;
- duplicate/version relationship.

Invariant: a workup is not branch evidence until coverage applicability is evaluated.

### 21.7 Coverage assessment

- `workup_or_test_id`, `target_concept_or_branch_code`
- `coverage_relation`, `limitations`
- `coverage_rule_id`, `coverage_rule_version`
- `evaluated_at`, `evaluation_source`

Invariant: `not_applicable` creates no evidence edge.

### 21.8 Evidence edge

- `id`, `case_id`, `branch_id`, `source_type`, `source_id`
- `relationship`, `strength`, `confidence`
- `rationale`, `created_at`, `rule_version`
- `is_active`, `superseded_by_id`

Invariant: coverage relation and evidence relationship are different types and cannot be assigned interchangeably.

### 21.9 Claim and correction

Claim fields include text/structured payload, claim type, provenance, status, source, and versions. Correction fields include actual `original_claim_id`, non-null `replacement_claim_id`, actor, reason, time, and source turn.

Invariant: a correction never points `original_claim_id` to the replacement.

### 21.10 Question and decision candidate

- target branch/gap;
- candidate type: question, record request, test, review, or monitor;
- expected discriminating outcomes;
- coverage relevance;
- safety importance;
- actionability;
- cost/burden/access inputs;
- redundancy and uncertainty penalties;
- score components and ranker version.

Invariant: every surfaced next action is explainable from stored score components.

### 21.11 Intervention and monitoring

Intervention option:

- rationale links, evidence strength, applicable findings/pathways;
- safety/contraindication state;
- neutral option identity separated from commerce identity;
- selected/declined state and actor.

Monitoring event:

- target, baseline, exposure/adherence, outcome, time window;
- adverse-effect/no-change/improvement state;
- confounders, provenance, source turn;
- branch update proposal, not automatic causal conclusion.

## 22. Canonical enum and state contracts

### 22.1 Coverage relation

```python
class CoverageRelation(str, Enum):
    DIRECTLY_ASSESSES = "directly_assesses"
    PARTIALLY_ASSESSES = "partially_assesses"
    DOES_NOT_DIRECTLY_ASSESS = "does_not_directly_assess"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"
```

### 22.2 Evidence relationship

```python
class EvidenceRelationship(str, Enum):
    SUPPORTS = "supports"
    WEAKENS = "weakens"
    DOES_NOT_ADDRESS = "does_not_address"
    RESOLVES_GAP = "resolves_gap"
    INCONCLUSIVE = "inconclusive"
```

### 22.3 Mapping contract

Use one pure mapping function with exhaustive pattern matching. It accepts coverage relation, normalized result state, and branch-specific interpretation rule. It returns an evidence relationship or `None`.

```text
NOT_APPLICABLE                   → None
UNKNOWN                          → None plus unresolved metric/warning
DOES_NOT_DIRECTLY_ASSESS         → DOES_NOT_ADDRESS
PARTIALLY_ASSESSES               → branch rule decides INCONCLUSIVE/SUPPORTS/WEAKENS; never closes alone
DIRECTLY_ASSESSES + positive     → branch rule decides SUPPORTS or RESOLVES_GAP
DIRECTLY_ASSESSES + negative     → branch rule decides WEAKENS or RESOLVES_GAP
DIRECTLY_ASSESSES + indeterminate→ INCONCLUSIVE
```

Do not use a generic positive/negative rule across all tests. Interpretation belongs to a versioned test-target rule.

### 22.4 Document outcomes

Use distinct states: `succeeded`, `valid_empty`, `partial`, `unsupported`, `failed`. Only `succeeded` and confirmed `partial` may emit observations. A report cannot be marked complete from `failed` or `unsupported`.

### 22.5 Claim confidence

Represent separately:

- evidence quality/strength;
- confidence in entity extraction;
- confidence in branch-specific interpretation;
- uncertainty due to missing coverage.

Never collapse these into one unexplained percentage.

## 23. Required service seams

### 23.1 Resolver

Input: raw label plus context.  
Output: canonical match, ambiguous candidates, or unresolved.  
Forbidden: substring fallback that silently maps generic `MRI` to `mri_brain`.

Tests: exact alias, normalized alias, ambiguous alias, unknown label, hostile Unicode, and versioned alias migration.

### 23.2 Coverage governor

Input: canonical test/method and target branch concept.  
Output: typed coverage assessment with rule/version and limitations.  
Forbidden: converting `not_applicable` into `inconclusive`.

### 23.3 Evidence interpreter

Input: coverage assessment, normalized result, target-specific rule.  
Output: typed evidence mutation or `None`.  
Forbidden: accepting raw coverage strings as evidence enums.

### 23.4 Lifecycle governor

Input: current branch state, proposed transition, evidence/gap state.  
Output: accepted transition or typed rejection.  
Forbidden: direct status writes outside the governor.

### 23.5 Mutation builder

Input: validated structured plan plus canonical context.  
Output: typed mutation batch with source turn/idempotency identity.  
Forbidden: Cartesian pairing of every workup with every open branch.

### 23.6 Mutation applier

Input: typed mutation batch.  
Output: transaction result with applied, existing, rejected, failed counts.  
Forbidden: catch/continue on enum or integrity errors that creates plausible success.

### 23.7 Projection builder

Input: canonical active state and requested version.  
Output: UI/report/legacy snapshot.  
Forbidden: writing new canonical truth or including inactive facts in active views.

### 23.8 Output validator

Input: structured scientific output.  
Output: validated output or blocked result with violations.  
Checks: provenance, diagnostic language, contradiction display, coverage gaps, citations, safety, intervention constraints, commerce neutrality.

## 24. Turn-processing algorithm

Implement the live turn path in this order:

1. Authorize actor against case.
2. Acquire/create turn using the idempotency key.
3. If turn already completed, return stored outcome; if in progress, use defined convergence behavior.
4. Run deterministic safety pre-screen on raw/new structured findings.
5. Load active canonical case state only.
6. Resolve mentioned entities; preserve ambiguity/unresolved labels.
7. Ask the planner for a typed proposal, not database mutations.
8. Validate proposal schema, product invariants, safety constraints, and allowed transitions.
9. Build mutations with source turn identity.
10. For each workup-target pair explicitly proposed, run coverage governor.
11. Convert applicable coverage to evidence through the single mapping boundary.
12. Run branch lifecycle proposals through the governor.
13. Apply the entire batch transactionally with idempotent identities.
14. Build active projections from committed canonical state.
15. Rank next actions with stored components.
16. Compose user-facing language from validated structured output.
17. Run final output validation and deterministic safety post-check.
18. Persist output/version metadata and complete the turn.
19. Emit PHI-safe counters, latency, outcome, and correctness signals.

On failure after turn acceptance, mark the turn `failed` or `partial` explicitly. Never return a successful empty payload.

## 25. Document-processing algorithm

1. Authorize upload and create document record.
2. Compute content identity for duplicate/version detection.
3. Store source securely and record provenance.
4. Classify format and support state.
5. Extract text/OCR with timeout and explicit outcome.
6. Parse candidate observations with page/coordinate provenance.
7. Normalize biomarker identity, units, ranges, dates, and comparators.
8. Validate internal consistency and confidence.
9. Mark low-confidence fields for confirmation.
10. Persist source extraction and normalized observations transactionally.
11. Distinguish success, valid-empty, partial, unsupported, and failure.
12. Pass confirmed observations to the existing lab engine.
13. Link resulting evidence to the case without overwriting source history.
14. Build report only from allowed outcome states.
15. Emit correctness metrics without raw PHI/document contents.

## 26. Next-best-investigation ranker

Start with a transparent, versioned deterministic ranker. Do not begin with a GNN or opaque learned ranking.

### 26.1 Candidate generation

Generate candidates only from active gaps and configured safety rules. Candidate types include clarifying question, prior-record request, laboratory evaluation, professional review, or monitoring action.

### 26.2 Score components

Normalize each component to a documented range:

- branch discrimination;
- coverage relevance;
- expected actionability;
- safety importance;
- evidence quality supporting the candidate;
- redundancy penalty;
- cost penalty;
- burden/risk penalty;
- access penalty;
- user-preference fit;
- uncertainty penalty when coverage/rules are weak.

Suggested initial form:

```text
value =
  w1 * discrimination
+ w2 * coverage_relevance
+ w3 * actionability
+ w4 * safety_importance
+ w5 * evidence_quality
+ w6 * preference_fit
- w7 * redundancy
- w8 * cost
- w9 * burden_risk
- w10 * access_difficulty
- w11 * rule_uncertainty
```

Weights are product configuration with version history, not hard-coded mystery constants. Safety may impose eligibility/priority rules before scoring.

### 26.3 Explanation contract

For each surfaced candidate, store and display:

- gap addressed;
- branches it could distinguish;
- what each broad outcome would change;
- what it would not establish;
- known limitations;
- cost/burden/access assumptions;
- why it outranked alternatives.

### 26.4 Evaluation metrics

- top-k expert agreement;
- redundant-question rate;
- irrelevant-candidate rate;
- gap-resolution yield;
- percentage of actions that change a downstream decision;
- safety override correctness;
- cost/burden preference adherence;
- calibration by score band.

## 27. Scientific knowledge and evidence pipeline

### 27.1 Promotion states

Use `draft`, `machine_checked`, `expert_validated`, `production`, `deprecated`, and `retracted` as separate lifecycle concepts where appropriate.

### 27.2 Required edge metadata

Each knowledge/evidence relationship should retain:

- canonical source/target identifiers;
- relationship type and direction;
- evidence level/strength rubric;
- population/context;
- dose/form/method where relevant;
- safety/interaction constraints;
- source citation identifiers;
- extraction/curation method;
- reviewer and review state;
- created/validated/deprecated dates;
- ontology and rule version.

### 27.3 Ingestion rules

- Automated discovery writes only to draft/quarantine.
- Deduplicate canonical citations and relationships.
- Validate source existence and claim support.
- Keep contradictory evidence.
- Never infer clinical applicability solely from mechanistic evidence.
- Require human promotion for safety-critical or user-facing production edges.
- Support source correction/retraction without deleting historical report provenance.

## 28. Moat data contract and governance

Capture only data allowed by consent and product policy. Separate operational care/use data from data eligible for improvement/research. De-identification is not assumed merely because direct names are absent.

### 28.1 Learning event

Each eligible event should include:

- de-identified/pseudonymous case key;
- engine/ontology/evidence/prompt/model versions;
- active branch/gap state before action;
- candidates considered and score components;
- action selected and actor;
- subsequent result/outcome;
- correction/reviewer feedback;
- permitted-use scope;
- exclusion reason when not eligible for learning.

### 28.2 Feedback types

- accepted/rejected question or action;
- clinician agrees/disagrees/partially agrees;
- wrong applicability;
- missing branch/gap;
- unsupported certainty;
- citation mismatch;
- safety miss/over-trigger;
- user correction;
- outcome unavailable, no change, improvement, adverse effect;
- confounder present.

### 28.3 Production-learning firewall

1. Capture eligible events immutably.
2. Transform into a versioned offline dataset.
3. Remove prohibited/irrelevant fields.
4. Split train/development/locked holdout by case, not turn.
5. Evaluate candidate change against fixed gold and safety suites.
6. Require reviewer approval for production rule/model promotion.
7. Record promotion decision and rollback target.

No live self-modification.

## 29. File-level implementation instructions

Verify current paths before editing. Based on the reviewed branch, begin with these seams.

### `app/discovery/branch_service.py`

1. Replace raw `CoverageRelation` assignment to `EvidenceMutation.relationship` with the canonical mapping function.
2. Return no evidence mutation for `not_applicable` or unresolved coverage.
3. Require an explicit branch target; do not loop a workup across every branch.
4. Preserve mapping rule/version and rationale.
5. Add unit tests for exhaustive enum mapping and integration tests through persistence/map serialization.

### `app/discovery/reconciliation.py`

1. Stop pairing every workup with every opened branch.
2. Build workup-target pairs only from resolved proposal/context.
3. Do not regenerate default findings/gaps already active.
4. Emit supersession mutations for validated corrections.
5. Attach source turn/idempotency identity to every mutation.
6. Test `batch_from_turn` together with `apply_mutation_batch`.

### `app/discovery/mutations.py`

1. Persist `source_turn_id` fields already present in mutation types.
2. Implement deterministic identities and database conflict handling.
3. Fail the transaction on invalid enum/relationship instead of `continue`.
4. Resolve the actual original claim before creating correction links.
5. Set replacement → predecessor supersession direction.
6. Mark originals inactive with audit metadata.
7. Return applied/existing/rejected/failed counts.
8. Add duplicate, correction replay, rollback, and concurrency integration tests.

### `app/discovery/service.py`

1. Filter active facts for `_assessment_state`, `apply_user_turn` prior facts, and active snapshot projection.
2. Keep inactive rows available only to history/audit reads.
3. Ensure projection rebuild cannot mutate canonical truth.
4. Route branch transitions through the lifecycle governor.
5. Make the turn outcome explicit on all failures.
6. Test correction → rebuild → restart → return-turn behavior.

### `app/discovery/epistemics.py`

1. Make `validate_branch_resolution`/equivalent the sole close-transition path.
2. Encode direct, partial, non-addressing, and contradictory evidence behavior.
3. Return typed rejection reasons.
4. Test the transition matrix exhaustively.

### `app/coverage/models.py` and Alembic revisions

1. Make model and migration constraints identical.
2. Add alias uniqueness.
3. Add `(case_id, code)` uniqueness for branches.
4. Enforce one active gap identity using a supported PostgreSQL strategy.
5. Add identities for replay-sensitive workup/evidence/event records.
6. Test migration on empty database and upgrade from the previous revision.
7. Provide a dry-run duplicate audit before adding constraints to populated environments.

### Resolver code such as `app/coverage/resolver.py`

1. Remove unsafe generic substring defaulting.
2. Return exact, alias, ambiguous, or unresolved results.
3. Preserve the raw label.
4. Require user/system clarification for ambiguity.
5. Add `MRI` ambiguity regression coverage.

### Map/output serializers

1. Serialize canonical active state only.
2. Include non-addressing, partial, contradictory, and unresolved buckets.
3. Remove or clearly separate legacy diagnostic-certainty fields.
4. Include provenance and rule/version metadata needed for explanation.
5. Validate output before user display.

### Frontend files such as `frontend/ask.html`, `ask-app.js`, `workspace-app.js`

1. Render succeeded, valid-empty, partial, unsupported, and failed distinctly.
2. Expose evidence source, strength, confidence, contradiction, and coverage limitation without overwhelming the primary view.
3. Show why a question/action is next.
4. Make corrections explicit and confirm the active replacement.
5. Preserve safety escalation prominence.
6. Add browser tests using semantic selectors; do not couple tests to incidental CSS layout.

## 30. Migration implementation sequence

Use expand/contract. Do not combine schema expansion, backfill, constraint enforcement, and old-path removal in one irreversible step.

1. **Audit:** count duplicates, orphans, invalid enums, inactive-in-projection cases, and ambiguous correction links.
2. **Expand:** add nullable identity/version/link columns and new tables/enums without removing old fields.
3. **Dual read validation:** compare canonical and legacy projections in staging; do not silently prefer mismatches.
4. **Backfill dry run:** report affected counts and ambiguous rows; make no writes by default.
5. **Backfill:** batch, checkpoint, idempotently update, and record version.
6. **Validate:** assert no duplicates/orphans and compare gold cases.
7. **Add constraints:** only after data satisfies them.
8. **Switch canonical read:** feature flag/dark launch with correctness telemetry.
9. **Stop legacy writes:** after comparison window passes.
10. **Contract later:** remove obsolete paths in a separate release after rollback dependence ends.

Rollback must state whether new canonical writes can be read by old code. If not, rollback is unsafe; use forward fix or compatibility reader.

## 31. Detailed PR and issue plan

### PR-A — Baseline and red-test harness

- No production behavior changes.
- Reproduce reviewed Issues 1–9.
- Record schema, flags, CI, migration head, and production/staging versions.
- Add red tests at correct boundaries.
- Establish the traceability matrix.

### PR-B — Coverage/evidence contract

- Add/normalize typed enums and mapping seam.
- Fix unrelated evidence attachment.
- Fix unresolved/ambiguous resolver behavior.
- Update map serialization.
- Tests: unit mapping + PostgreSQL persistence + API map.

### PR-C — Idempotency and uniqueness

- Persist source turn identities.
- Add semantic identities and conflict behavior.
- Add safe migrations/duplicate audit.
- Tests: 1/2/10 replay and two-worker concurrency.

### PR-D — Corrections and active projection

- Correct original/replacement links.
- Emit live supersession.
- Fix supersession direction.
- Filter active reads/projections.
- Tests: correction/replay/rebuild/restart/return visit.

### PR-E — Branch lifecycle and gaps

- Centralize legal transitions.
- Connect coverage governor to closing.
- Implement partial/open/closed/reopened semantics.
- Tests: exhaustive transition matrix and gold EMG case.

### PR-F — Scientific-output contract

- Add structured claims/provenance/confidence/coverage/contradiction fields.
- Add output validator.
- Separate diagnostic certainty and commerce influence.
- Tests: required/prohibited gold assertions and citation fidelity.

### PR-G — Discovery ranker and moat instrumentation

- Persist candidate/action/score components.
- Link each question/action to branch/gap.
- Add redundancy and safety rules.
- Capture versioned feedback events.
- Tests: deterministic ranking, safety override, explanation contract.

### PR-H — Intervention/monitoring loop

- Link options to rationale/evidence/safety.
- Separate exposure/adherence/outcome/confounders.
- Feed observations back as proposals.
- Tests: improvement/no-change/adverse-effect/causal-language rules.

### PR-I — End-to-end and parser benchmark

- Implement all mandatory API/browser/scientific cases.
- Add versioned fixture corpus and benchmark command.
- Produce machine-readable gate report.

### PR-J — Reliability and staged rollout

- Fix CI/reseed/deployment gates.
- Add correctness telemetry, alerts, runbook, backup/restore evidence.
- Dark launch, compare, supervised ramp.

## 32. Test naming and evidence conventions

Use names that state the invariant, for example:

```text
test_normal_emg_persists_non_addressing_evidence_for_small_fiber
test_unmatched_workup_creates_no_branch_evidence
test_replayed_turn_is_semantically_idempotent
test_correction_remains_inactive_after_projection_rebuild
test_concurrent_branch_open_creates_one_branch
test_failed_parser_cannot_create_successful_report
test_safety_governor_cannot_be_overridden_by_composer
```

Each critical test record includes:

- acceptance/gate ID;
- expectation source;
- fixture version;
- observed red failure and reason;
- passing commit;
- test layer;
- compensating production tripwire where applicable.

Avoid asserting only row counts when semantic content matters. Assert foreign keys, active flags, relationships, source identities, versions, output bucket, and user-visible result.

## 33. CI release command and gate report

Create one repository command, adapted to house tooling, that runs:

1. formatting/lint/type checks;
2. pure unit suite;
3. PostgreSQL integration suite;
4. migration empty/upgrade checks;
5. API/stream suite;
6. mandatory browser E2E;
7. scientific-output gold evaluations;
8. parser benchmark;
9. security/authorization tests;
10. machine-readable traceability/gate report.

The release job fails on missing tests/evidence, not only failed tests. Do not make flaky retries part of the pass definition.

## 34. Observability specification

### Counters

- turns attempted/succeeded/partial/failed/replayed;
- mutations applied/existing/rejected/failed by entity;
- evidence mappings by coverage/evidence relation;
- unresolved/ambiguous resolver outcomes;
- branch transitions accepted/rejected;
- parser outcomes by format/version;
- reports created by upstream document outcome;
- safety escalations by level;
- correction/supersession operations;
- next-action candidates surfaced/selected/rejected.

### Correctness tripwires

- failed or unsupported parse followed by successful report: threshold 0; stop rollout.
- inactive finding in active projection: threshold 0; stop rollout.
- unrelated/not-applicable evidence edge: threshold 0; stop rollout.
- non-addressing evidence closes branch: threshold 0; stop rollout.
- duplicate semantic identity growth: threshold 0 beyond controlled conflict events.
- partial output without visible warning: threshold 0; stop rollout.
- missing citation/provenance on material claim: threshold 0; block report.

### Logging rules

Use correlation IDs, entity IDs safe for operations, rule/version, outcome, duration, and error class. Do not log raw user narratives, raw reports, secret values, or unnecessary health data.

## 35. Security, privacy, and clinical-posture requirements

- Enforce authorization at case/document/report boundaries, not only UI routing.
- Test object-level access and guessed identifiers.
- Record consent, retention, deletion, export, and learning-use scope.
- Separate operational data from eligible improvement datasets.
- Keep deterministic safety controls outside LLM discretion.
- Prohibit diagnostic/treatment claims in prompts, validators, UI, and marketing.
- Do not independently issue consumer lab orders without the approved clinician/partner layer and applicable legal review.
- Review state-specific, CMS/CLIA, privacy, and vendor obligations before commercial expansion.
- Do not claim HIPAA compliance, clinical validation, security, or accuracy without documented evidence.

## 36. Rollout plan

### Stage 0 — Local/CI

All mandatory gates pass on fixed fixtures. No real-user expansion.

### Stage 1 — Dark staging

Run canonical and legacy projections in comparison mode using synthetic/de-identified cases. Do not expose new behavior. Investigate every mismatch.

### Stage 2 — Founder-supervised MVP

Enable for founder/team gold workflows only. Review every structured output and state transition. Maintain immediate disable/forward-fix path.

### Stage 3 — Small controlled cohort

Use explicit consent, narrow supported scope, monitoring, and manual review. Freeze holdout cases. Record errors and corrections without automatic production learning.

### Stage 4 — Beta candidate

Proceed only after the supervised cohort completes the agreed observation window without critical integrity/safety incident and beta privacy/support controls pass.

## 37. Autonomous implementation protocol

For every issue:

1. Codex writes the problem, acceptance claims, non-goals, door class, design, and risk map.
2. Founder resolves product/clinical one-way doors.
3. Grok branches from the approved integration base and opens a draft PR immediately.
4. Grok implements only the approved slice and posts exact evidence.
5. Codex reviews the actual diff cold, including hostile traces and call-site blast radius.
6. Grok fixes blockers in new atomic commits.
7. Codex issues a written verdict.
8. Only passing work enters `integration/agent`.
9. Founder alone approves promotion to `main`/production.

Grok must stop when it discovers an unapproved schema, public API, evidence contract, safety rule, security boundary, vendor, or deployment-topology change.

## 38. Implementation completion checklist

An issue is complete only when:

- acceptance claims are mapped to code and independent tests;
- top risks have mitigation, adversarial test, and tripwire;
- migration and rollback/forward-fix impact are explicit;
- relevant gold cases pass;
- no prohibited claim/state occurs;
- CI evidence is attached;
- Codex review has no blockers;
- handoff distinguishes written, locally verified, CI verified, staging verified, and deployed;
- next action and trap line are present.

## 39. Immediate next action

When repository access returns:

1. Commit this specification to `docs/architecture/HERBAGRAPH_DISCOVERY_ENGINE_MASTER_SPEC.md` on the architecture branch.
2. Merge/approve the governance foundation before implementation.
3. Create ADR-MVP-001 through ADR-MVP-005 as proposed records.
4. Open PR-A's issue using Milestones 0–1 only.
5. Give Grok the bounded baseline/red-test task from Section 16.
6. Require Grok to return the baseline before approving any behavior fix.

**The trap:** Passing existing unit tests does not demonstrate that the live persistence, projection, API, or user-visible path preserves truth.

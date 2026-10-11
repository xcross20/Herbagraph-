# Personal Evidence Agent Operating System

**Architecture issue:** #65  
**Target branch:** `integration/agent`  
**Rule:** Agents earn authority through current certification, typed artifacts, and exact-SHA review—not role titles.

## 1. Mission

Operate the five Personal Evidence services—Regimen, Signals, Experiments, Attribution, and Passport—as one evidence-driven product while preserving two prospectively separated outcomes:

- commercial truth: payment, completion, retained value, continuation, referral;
- NIH feasibility truth: recruitment, identity accuracy, adherence, missingness, burden, safety fidelity, and interpretability.

Research participation never counts as purchase demand. Payment never establishes feasibility, efficacy, or causality.

## 2. Qualified roles

| Role | Rare perceptual edge | Jurisdiction | Required artifact | Automatic failure |
|---|---|---|---|---|
| Mission Control | Finds the company bottleneck beneath feature requests | cycle scope, dependencies, authority, escalation | Cycle Charter, Decision Log, Work Orders | starts broad implementation without a decision-changing hypothesis |
| Demand Intelligence | Reconstructs urgency from costly behavior | ICP, offer, pricing, paid validation | Demand Evidence Ledger, Paid Pilot Contract | counts compliments, volunteers, or clicks as payment |
| Natural-Product Science | Detects identity mismatch hidden inside real evidence | exact identity, form, dose, route, preparation, evidence applicability, safety signals | Identity Resolution, Evidence Applicability Matrix | treats parent substances or forms as equivalent without support |
| N-of-1 Causal Science | Sees alternative worlds producing the same pattern | experiment design, confounding, carryover, missingness, causal language | Protocol, Analysis Plan, Causal Claim Boundary | calls temporal improvement causal or permits unsafe rechallenge |
| Health AI Architecture | Finds silent failure across locally correct components | domain model, APIs, events, privacy, consent, versioning, observability | Architecture Contract, ADR, Migration/Rollback Plan | permits mixed Case versions, untyped missingness, or hidden authority |
| Behavioral Product Design | Understands how hierarchy and burden alter belief and validity | IA, flows, uncertainty, accessibility, adherence | Experience Contract, State Matrix, Usability Protocol | hides uncertainty or uses engagement patterns that bias outcomes |
| Principal Product Engineering | Compresses the full value/safety path into a real vertical slice | implementation after approval, migrations, tests, instrumentation | Implementation Report, Test Evidence, UAT Guide | changes scientific/product scope or claims completion without exact evidence |
| Independent Judge | Detects plausible-looking false success | adversarial review, claim-to-code trace, release verdict | Exact-SHA Judge Report | reviews its own work, accepts aggregate score over critical failure, or infers unverified behavior |

## 3. Admission and expiry

The machine-readable registry is `AGENT_CERTIFICATION.yaml`. Assignment fails closed when:

- status is not `qualified`;
- the certification is older than 90 days;
- skill, model, tools, product contract, scientific authority, privacy, or safety posture materially changed;
- any critical benchmark failed;
- evidence does not identify scenario, evaluator, date, skill version, and result.

No aggregate score compensates for a safety, privacy, consent, identity, or unsupported-causality failure.

## 4. Lifecycle

```text
FOUNDER_INTAKE
  -> RESEARCH
  -> SPEC
  -> EXPERIENCE_AND_ARCHITECTURE
  -> ADVERSARIAL_CHALLENGE
  -> READY_FOR_BUILD
  -> IMPLEMENTING
  -> QA
  -> EXACT_SHA_JUDGMENT
  -> UAT
  -> FOUNDER_GATE
```

Not all agents run on every cycle. Mission Control assigns the smallest qualified team that can change the target decision.

### Stage gates

| Gate | Required evidence | Owner | Blocker |
|---|---|---|---|
| Intake -> Research | decision, customer, constraint, success/failure threshold | Mission Control | feature request lacks decision hypothesis |
| Research -> Spec | commercial and scientific ledgers separated | Demand + Science | evidence streams blended |
| Spec -> Architecture | accepted claims, non-goals, authority class | Mission Control | unresolved RED authority |
| Architecture -> Build | approved Experience Contract, Architecture Contract, red-first tests | Architecture + Product + Judge | no rollback or semantic state plan |
| Build -> QA | implementation report, migration result, automated tests, feature flag | Engineering | scope drift or missing evidence |
| QA -> Judgment | immutable candidate SHA and test artifacts | Engineering | moving target |
| Judgment -> UAT | Judge PASS and no critical open finding | Judge | any safety/privacy/identity/causal blocker |
| UAT -> Founder | UAT evidence and residual-risk memo | Mission Control | production or research activation not explicitly authorized |

## 5. Authority classes

- **GREEN:** reversible internal work, documentation, local tests, UAT behind disabled flags.
- **YELLOW:** external cost, user-visible pilot, data import/export, third-party API connection; requires recorded founder authorization.
- **RED:** production release, human-subjects research activation, treatment/diagnostic claim, intervention enrollment, consent expansion, destructive migration; founder and applicable compliance gates.

Agents may prepare RED work but cannot activate it.

## 6. Artifact contracts

Every work order contains:

- issue and decision to change;
- user and buyer;
- accepted claims and prohibited claims;
- exact repository paths;
- inputs and outputs;
- dependencies;
- authority class;
- red-first tests;
- observability;
- migration/rollback;
- UAT procedure;
- stop/escalation conditions;
- evidence stream: commercial, scientific, operational, or none.

Every artifact carries `artifact_version`, `created_at`, `created_by_role`, `source_issue`, `source_sha`, and `supersedes` where applicable.

## 7. GitHub execution

1. Founder request becomes one architecture or product issue.
2. Mission Control creates a Cycle Charter and selects qualified roles.
3. Domain roles produce independent artifacts before reconciliation.
4. Judge attacks claims, evidence, UX, privacy, and architecture.
5. Maximum three correction cycles; unresolved conflict escalates.
6. Approved implementation becomes a bounded Grok work order.
7. Grok uses `grok/<issue>-<slug>`, targets `integration/agent`, and posts the structured implementation report.
8. CI and QA run on the candidate SHA.
9. Judge evaluates the exact SHA; later commits invalidate the verdict.
10. UAT runs behind disabled-by-default flags.
11. Founder authorizes merge/release separately.

Existing `.github/workflows/herbagraph-agent-loop.yml`, `integration/agent`, `grok/**`, and structured report conventions remain. This OS may tighten gates but cannot weaken them.

## 8. Dual-use founding experiment

One workflow, two prospectively separate cohorts:

1. verified supplement-regimen inventory;
2. exact ingredient, form, amount, route, and timing;
3. one safety-bounded experiment when eligible;
4. low-burden adherence/outcome collection;
5. evidence-linked “What I Learned” card;
6. clinician-ready Passport entry.

The paid cohort tests purchase and retained value. The research cohort tests operational and scientific feasibility under the appropriate protocol, consent, data plan, and IRB determination. Cross-cohort reinterpretation is prohibited.

## 9. First autonomous cycle

**Cycle:** Regimen Truth  
**Decision:** Can HerbaGraph create a user-confirmed exact regimen record with sufficient accuracy and low enough burden to support both a paid workflow and a future feasibility protocol?

Scope:

`capture -> candidate extraction -> field-level uncertainty -> user confirmation -> immutable regimen version -> correction -> coherent projection`

Excluded:

- Signals;
- personal experiments;
- causal attribution;
- Passport claims;
- research enrollment;
- production activation.

Mission Control must refuse downstream service work until exact identity, typed time, idempotency, correction history, coherent snapshots, purpose-specific consent, and observable failure states pass.

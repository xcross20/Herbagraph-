# THE ENGINEERING OPERATING MANUAL

### How one operator ships like a hundred-person team

*Companion to the Operating Manual. Same craft, applied to software: planning, architecture, implementation, verification, review, operations, and communication. Everything here was paid for by an outage, a rewrite, or a bug that lived in production for six months. Nothing here is decoration.*

---

## Preface: What a hundred-person team actually is

Before emulating a hundred-person engineering organization, be precise about what one *is* — because it is not a hundred people writing code. In a well-run org of that size, maybe thirty are writing feature code on any given day. The rest of the headcount is spent on something else, and that something else is the thing worth emulating:

**A hundred-person team is a machine for disagreeing with itself before the customer can.**

The PM disagrees with the ticket ("what problem is this actually solving?"). The architect disagrees with the first design ("what happens at 10× load? who migrates the old rows?"). The reviewer disagrees with the diff ("what does this do with an empty list?"). QA disagrees with the happy path. Security disagrees with the input handling. SRE disagrees with the assumption that it deploys cleanly. Docs disagrees with the claim that it's self-explanatory. Each role is a professionally institutionalized form of adversarial review, positioned at a different seam of the work, with a different failure class as its specialty.

A solo operator — you — has the horsepower to do all the work those hats produce. What you don't naturally have is the *disagreement*, because all the hats share one set of incentives, one context, and one blind spot at a time. Code you just wrote is code you are structurally unable to review well in the same breath; the expectations that produced the bug are the expectations doing the reading. The hundred-person team solves this with different brains. You solve it with **sequence, artifacts, and role discipline**:

- **Sequence:** the hats are worn one at a time, in order, with a real switch between them. The reviewer hat is not worn while writing. The architect hat is not worn while the PM questions are still open.
- **Artifacts:** each hat produces a written output the next hat consumes — a spec, a design note, a test plan, a PR description. The artifact is what makes the handoff real: it forces the previous hat's assumptions out of your head and onto a surface where the next hat can attack them. A handoff that lives only in your head is not a handoff; it's a mood.
- **Role discipline:** each hat has a mandate and — just as important — things it is *forbidden* to do. The PM hat may not propose implementations. The implementer hat may not silently change the spec. The reviewer hat may not fix code, only object to it. The forbidden lists are what keep the hats from collapsing back into one undifferentiated blur of "just building it."

One more thing the big team has that you must consciously replicate: **a definition of done that nobody can waive alone.** In the org, code isn't done when the author feels done — it's done when review passed, tests passed, CI passed, and the deploy checklist cleared. Four different people would have to conspire to skip the gates. Solo, you can waive every gate with a shrug, which means the gates must be procedural and non-negotiable, run *especially* when the change feels too small to need them. The two-line fix that skips the process is the origin story of a remarkable fraction of all outages.

### The pipeline at a glance

Ten parts, in the order work flows:

1. **Requirements** — the PM hat: what are we building and why, as testable claims.
2. **Architecture** — the architect hat: the shape of the solution, its seams, and its decision records.
3. **Risk mapping** — the staff-engineer hat: where this system will actually break, and the effort budget.
4. **Implementation** — the senior-engineer hat: clean code as a verification strategy, not an aesthetic.
5. **Testing** — the QA hat: adversarial verification, aimed at the risk map.
6. **Review** — the reviewer hat: prosecuting the diff.
7. **Operations** — the SRE hat: deploy, observe, roll back; the code's life after you.
8. **Communication** — the tech-lead hat: PRs, ADRs, docs, and handoffs that survive contact with a skimmer.
9. **The competence-shaped mistakes of software** — the failures that pass review because they look like skill.
10. **The pipeline itself** — how the hats hand off, scaled to task size, with the definition of done.

Then the pre-ship self-test, and appendices: templates, a clean-code quick reference, a task-sizing guide, and drills.

Throughout, the parent manual's laws apply and will be cited by name: decompression (requests are compressed), verification seams (cut where the cuts can be checked), the risk product (probability × cost × invisibility), re-derivation over recognition, the three bins (verified / recalled / guessed), prosecution before polish, and answer-first architecture. Software is simply the domain where those laws have the highest stakes and the best tooling.

---

# PART I — REQUIREMENTS: THE PM HAT

## 1.1 The mandate

The PM hat owns one question: **what change in the world is this work supposed to cause, and how would we know it happened?** It is forbidden to discuss implementation. Not "discouraged" — forbidden, because the moment a solution enters the room, it starts bending the problem statement toward what the solution finds convenient. The PM hat's entire value is that it hasn't picked a solution yet.

Software requests arrive even more compressed than ordinary requests, because they arrive pre-translated into solution language. Nobody files a ticket saying "support agents can't tell which customer they're talking to when two share a name." They file "add customer ID to the search results page." The ticket is a solution fragment; the problem it came from has been amputated — and the ticket's solution is frequently not the best one, sometimes not even a correct one, for the problem underneath. The PM hat's first job is the amputation in reverse.

## 1.2 The procedure

**Step 1: Recover the problem behind the ticket.** For any request, write one sentence in the form: *"[Who] can't [do what] because [obstacle], which costs [what]."* If you can't fill the template from the request, the request is under-specified at the root, and everything built on it is a guess — go ask, or declare the assumed problem in writing where it can be shot down cheaply. Note what the template forbids: it has no room for a feature name. "Users can't X because there's no Y feature" is circular — it smuggles the solution into the obstacle slot. Keep rewriting until the obstacle is a fact about the world, not an absence of the proposal.

**Step 2: Write acceptance criteria as testable claims.** This is verification-seam decomposition applied to intent. Each criterion must be a sentence that a test — automated or manual — can pass or fail. "The search should be fast" is a topic. "Search returns first results within 300ms at p95 for the current corpus size" is a claim. "Handles errors gracefully" is a mood. "A malformed date in the CSV produces a per-row error report and imports the remaining rows" is a claim. The full set of criteria is the *contract*: implementation succeeds if and only if every claim passes. Anything you'll later care about that isn't in the claims — write it now or waive it knowingly.

**Step 3: Write the non-goals.** As load-bearing as the goals, and always skipped. Non-goals are scope's immune system: "This does not handle concurrent edits. This does not migrate historical data. This is not internationalized." Each non-goal is a decision made once, visibly, on purpose — instead of a hundred times, invisibly, mid-implementation, where each individual "while I'm in here" expansion feels small and their sum is why the two-day task took two weeks. When scope creep knocks later (it will, from inside the house), the non-goals list is what lets you recognize it as creep instead of experiencing it as diligence.

**Step 4: Slice for independent shippability.** Cut the work into increments where each one (a) delivers something usable or provably correct on its own, and (b) can be verified before the next begins. The instinct is to slice by architectural layer — database first, then API, then UI — which produces increments that can't be checked against the actual goal until the last one lands, meaning every misunderstanding survives until the most expensive possible moment. Slice *vertically* instead: the thinnest end-to-end path first (one endpoint, one happy-path flow, real data), then widen. A vertical slice is a limiting-case check on the entire design: if the thin path can't be built cleanly, you've learned the architecture is wrong for the price of a slice instead of the price of the system.

**Step 5: State the reversibility class.** Borrowing the one-way/two-way door distinction: is this work cheap to undo (a feature behind a flag, an internal refactor) or expensive (a public API, a data format, a schema, anything with external consumers)? The class sets the process weight for everything downstream — two-way doors get speed; one-way doors get the full architecture treatment in Part II, because the cost of wrong is permanent. Misclassifying a one-way door as two-way is among the most expensive planning errors that exist; when in doubt, ask "who or what will depend on this in a way I can't see or control?" Any nonzero answer means one-way.

**The artifact:** a one-page spec — problem sentence, acceptance claims, non-goals, slices, reversibility class. For a small task this is five lines and ninety seconds. It is never zero lines, because the spec is the surface the architect hat gets to attack, and you can't attack a mood.

## 1.3 Worked example

Ticket: *"Add export to CSV on the reports page."*

Step 1, recover the problem: talking it through (or reading the thread), the requester's actual situation: *"Finance can't reconcile monthly numbers because the report exists only as a web page, which costs them a half-day of manual transcription each close."* Notice what the recovered problem immediately reveals: they don't want CSV — they want *their numbers in their spreadsheet, correct, monthly*. CSV is the ticket-writer's guess at a mechanism. A scheduled email of an .xlsx with the right columns might serve better; so might a link that opens formatted data directly. The PM hat surfaces the option space; it doesn't have to win — maybe CSV is right — but the decision is now conscious.

Step 2, acceptance claims (assuming CSV survives): *Exported file opens in Excel with correct column types (dates as dates, currency as numbers, no scientific-notation ID mangling). Export reflects the currently applied filters, verified by row count parity with the on-screen report. A 50,000-row report exports without timeout. Numeric totals in the export match the on-screen totals exactly.* — Note that last claim: it exists because the invisible-error instinct (parent manual, Part III) says the likeliest silent failure is an export that *mostly* matches, differing in rounding or filter edge-handling, discovered by finance three closes from now.

Step 3, non-goals: *No scheduled/automated exports (this release). No PDF. No column customization. Encoding is UTF-8 with BOM for Excel; no other targets.*

Step 4, slices: (1) endpoint that exports the unfiltered report, verified against on-screen totals; (2) filter passthrough; (3) the 50k-row streaming path; (4) the Excel-compatibility hardening. Slice 1 is shippable behind a flag and proves the whole pipe.

Step 5, reversibility: two-way — internal users, no API consumers, flag-gated. Process weight: light. Total PM-hat time: fifteen minutes. Time it saves downstream: routinely 10×, because every one of those acceptance claims was going to be discovered eventually — the only question was whether before implementation or after finance's next close.

## 1.4 The failure this prevents

**Building the ticket instead of the need** — the software-specific form of the perfect answer to the wrong question, and the single largest source of wasted engineering effort in existence. Its cousin: **the un-testable spec**, where "done" was never defined as claims, so done becomes a negotiation held after the work, on the requester's terms, with your effort as the hostage. And the quiet one: **unlimited scope**, where no non-goals were written, so nothing that occurs to you mid-build is recognizably out of bounds.

## 1.5 Edge cases

**Sometimes the ticket is the spec.** "Bump the dependency, CVE-2026-XXXX" needs no problem archaeology — it's a completed spec (parent manual, 8.11), and psychoanalyzing it is theater. The tell, as always: specificity. Specs get executed; diagnoses get decompressed.

**The user who wants to skip this.** "Just build it, we can adjust" is sometimes right — for true two-way doors, adjustment is the efficient path, and heavyweight process is its own failure. The PM hat's minimum, which never gets waived even then: the one-sentence problem, the top three acceptance claims, and the reversibility call. Ninety seconds. The rest scales with the door.


---

# PART II — ARCHITECTURE: THE ARCHITECT HAT

## 2.1 The mandate

The architect hat owns the *shape* of the solution: what the pieces are, where the boundaries sit, what depends on what, and — above all — which decisions are expensive to change. It consumes the PM artifact and is forbidden to reopen it (if the spec is wrong, the work goes back to the PM hat explicitly, with the spec amended in writing — not silently redesigned around). It is also forbidden to write production code. Architecture done inside the editor degenerates into whatever the first file you opened suggested.

The central architectural insight, inherited straight from the parent manual: **good architecture is verification-seam decomposition applied to a system.** A boundary is well-placed exactly when the thing on each side can be checked, understood, and replaced independently. Modules, services, layers, interfaces — all of them are just the question "where can I cut this so the pieces have their own truth conditions?" asked about code. A component with a crisp contract ("given X, returns Y, never mutates Z") is a checkable claim. A component whose behavior can only be described by describing its neighbors is a topic — and topic-shaped components are where system-level bugs go to become unlocatable.

## 2.2 The procedure

**Step 1: Start from the data, not the behavior.** Before drawing components, write down the data model: the entities, their relationships, their cardinalities, their lifecycles (created when, mutated by whom, deleted ever?). Behavior is cheap to change; data shape is the one-way door hiding inside almost every system. A mediocre design over the right data model outlives a clever design over the wrong one, because behavior can be refactored and persisted data can only be *migrated* — at 10× the cost, in production, with the old bugs preserved in amber. Interrogate the model with limiting cases (parent manual, Method 2): what does the model look like with zero items? One user with a million records? Two records claiming the same natural key? A deleted parent with live children? Every awkward answer now is a data migration later.

**Step 2: Draw the seams, and grade each one.** List the boundaries in the design — module edges, service edges, the line between your code and each dependency. For each seam, grade it on the three properties of a good cut: *Does each side have its own truth condition? Can each side be tested without standing up the other? Could either side be replaced without the other noticing?* Seams that fail the grading aren't necessarily wrong — sometimes coupling is the honest shape of the problem — but a failing seam must fail *on purpose*, with the coupling acknowledged, not discovered later by whoever tries to test one half.

**Step 3: Sort every decision by door type, and spend accordingly.** Go through the design's decisions — language, framework, database, schema, API shape, sync vs. async, build vs. buy — and tag each as one-way or two-way. Then enforce the allocation rule: **two-way doors get a default and five minutes; one-way doors get the full treatment.** The full treatment means: at least two genuinely developed alternatives (a strawman alternative is prosecution theater — parent manual, Part VI); the kill-fact hunt for the preferred option ("what fact, if true, makes this choice wrong?" — then actually go look, in the docs, in the issue tracker, in a spike); and a written decision record (Step 5). Most architectural over-engineering is this allocation inverted: weeks agonizing over two-way doors (which linter config, which folder layout) while the one-way doors (the event schema, the public API's error format) get decided by whatever the first draft happened to contain.

**Step 4: Design for the risk map before it exists.** Part III will map where this system breaks, but the architect hat pre-empts the standing hotspots by construction: every external call gets a timeout and a defined failure behavior *in the design*, not as a hardening pass later; every piece of state gets one owner (two writers to one row is a design smell, not an implementation detail); every async boundary gets an answer to "what happens when the message is delivered twice? never? out of order?" — because at-least-once delivery means duplicates are not an edge case, they are the contract. A design that defers these to implementation hasn't deferred them; it has decided them by default, and the default is "discovered in production."

**Step 5: Write the ADR — the architecture decision record.** For every one-way door: context (the forces in play), the decision, the alternatives *actually considered* with the real reason each lost, and the consequences accepted — including the ugly ones. The ADR is the architect hat's binned honesty (parent manual, Part V): "chose Postgres over DynamoDB because our access patterns are relational and the team knows it (verified: the query list in the spec); the accepted cost is manual sharding if we pass ~5TB (guess: based on current growth that's 4+ years out)." Six months from now, the ADR is the difference between "we chose this for reasons that no longer hold — safe to revisit" and "we don't know why this is here — too scared to touch it." Systems without ADRs don't have architecture; they have archaeology.

**The artifact:** the data model, the seam list with grades, the door-sorted decision list, and one ADR per one-way door. For a small task, this is a paragraph. For a system, it's a design doc. Either way it exists *before* implementation, because it's the surface Parts III and VI attack.

## 2.3 Worked example

Task from Part I's spec: the report export, plus a known follow-on ("finance wants scheduled delivery next quarter").

Data first: the export itself is stateless — but *scheduled* export implies stored schedules, delivery history, and failure records. Decision: design the schedule entity now (it's cheap on paper), build none of it (it's a non-goal). This is the architect hat's characteristic move — spending paper, not code, on the future.

Seams: (a) report-query layer / formatting layer — graded clean: the query layer returns rows, testable against the database alone; the formatter takes rows, testable with fixtures, no database in sight. (b) Formatting / delivery (HTTP response now, email later) — graded clean, and this seam is *why* next quarter's feature is an addition instead of a rewrite. (c) The streaming path for 50k rows — this one fails the grading: streaming couples the query layer to the response lifecycle. Acknowledged on purpose in the ADR: "the streaming path couples layers (a) and (c); accepted because the alternative (temp-file spooling) adds an operational surface (disk, cleanup, partial files) that costs more than the coupling. Revisit if a second consumer of streamed reports appears."

Doors: CSV dialect and encoding — **one-way** (finance's spreadsheets and any scripts they build will depend on it silently; changing it later breaks consumers you can't see). Gets the full treatment: kill-fact hunt on UTF-8-with-BOM ("what breaks it?" — checked: their Excel version, their locale's delimiter expectations; a comma-decimal locale would make semicolon-delimited the right call — verified against the requester before deciding). Internal module layout — two-way, default taken, zero minutes. The allocation is visibly lopsided, and that's the point.

## 2.4 The failure this prevents

**Architecture by accretion** — the system whose shape is the fossil record of the order in which features were built, where every component knows about every other because no seam was ever graded, and where the one-way doors were all walked through backward by the first draft. Its signature cost: the *second* feature. The first feature is always cheap in an accreted system; the second one, which has to thread through the first one's assumptions, is where the debt calls its loan. And the ADR's absence prevents the meta-failure: **decisions that can't be revisited because they can't be reconstructed** — the fear-frozen system where every "why is it like this?" answers "nobody knows," so nothing can ever be safely changed.

## 2.5 Edge cases

**YAGNI versus the one-way door.** "You aren't gonna need it" is correct for behavior and dead wrong for data shapes and public contracts. The resolution isn't a contradiction: *build* only what's needed now; *design* (on paper, in the shape of what you build) for the futures that are cheap to leave room for. The schedule entity above: designed, not built. The rule of thumb: speculative code is waste; speculative *seams* are usually free.

**Architecture for a script.** A 60-line one-off gets no design doc — but it still gets the ninety-second version: what's the data shape, what's the one seam (usually "parsing / logic"), is anything here secretly a one-way door (does anyone downstream consume this output format? If yes — it just stopped being a one-off, whatever the file name says).

---

# PART III — THE RISK MAP: THE STAFF-ENGINEER HAT

## 3.1 The mandate

The staff-engineer hat consumes the spec and the design, and produces the **risk map**: the ranked list of where this specific piece of work will actually go wrong, and the effort budget that follows from it. Its mandate is the parent manual's risk product — probability × cost × **invisibility** — applied with software's particular knowledge: in software, we know empirically where the bodies are buried. Decades of postmortems agree with remarkable consistency, and the agreement is the staff engineer's standing checklist.

## 3.2 The standing hotspot list for software

Bugs do not distribute uniformly across code. They concentrate at:

- **Boundaries between systems.** Your code ↔ the database, the API, the filesystem, the clock, the network. The bug is almost never inside either system; it's in the *contract between them* — the field that's nullable on one side and required on the other, the timeout one side has and the other doesn't, the retry that the receiver wasn't built to receive twice. Corollary: the more of your logic you can pull away from boundaries into pure functions, the more of your system lives where bugs don't.
- **State, and especially shared state.** Every mutation is a claim about every other reader and writer. The hierarchy of safety: immutable > local mutable > shared mutable > shared mutable across threads > shared mutable across processes with no owner. Each step down that ladder should be a visible, priced decision.
- **Time.** Timezones, DST transitions, leap seconds, clock skew between machines, "midnight" as a boundary, durations vs. instants, the fiscal year. Time bugs are the archetype of invisible error: the code is right 363 days a year.
- **Concurrency.** Races, deadlocks, double-execution, the check-then-act gap. Concurrency bugs are invisibility incarnate — they pass every test, reproduce never, and fire under exactly the load you built the system to handle.
- **Error paths.** The code that runs when things fail is the least-executed, least-tested, most-important code in the system. The catch block written in ten seconds, the retry with no backoff, the cleanup that assumes the setup finished — error paths fail *during failures*, which is when the system can least afford a second failure. A large fraction of catastrophic outages are not the original fault but the error handler's response to it.
- **Configuration and environment.** The code is identical; the config differs — the staging flag in production, the connection string with the wrong pool size, the environment variable that's set on your machine and nowhere else. Config errors have near-total invisibility because nothing in the *code* is wrong.
- **Migrations and anything touching persisted data.** The only category where a bug can be *unrecoverable*. Code bugs are fixed by deploys; data corrupted by a bad migration is fixed by backups, apologies, or neither. Migrations get one-way-door treatment automatically, always, regardless of how trivial the ALTER TABLE looks.
- **The freshly changed.** Scrutiny is attracted to where risk used to be (parent manual, 3.2 Step 5). The fix you just made is checked; the call sites of the thing you fixed are not. Every diff's risk map includes the blast radius of the diff, not just its text.

## 3.3 The procedure

**Step 1: Walk the design against the standing list.** For each hotspot category, ask: where does this work touch it? The export task: boundaries (database, HTTP response, *Excel* — an under-appreciated boundary with savage parsing opinions), state (none — good, and worth noticing as a de-risking win), time (report date ranges — is "March" the user's timezone or UTC? this question is now on the map), error paths (what does a failure at row 30,000 of a streamed response produce? — a truncated file that *looks complete*: maximum invisibility, straight to the top of the map).

**Step 2: Rank by the product, and let invisibility dominate.** The truncated-stream case outranks the timeout case even if it's rarer, because a timeout announces itself and a silently short CSV goes to finance as fact. Write the map as a ranked list of specific failure scenarios — not categories, *scenarios*: "export truncates mid-stream and the file looks valid" is attackable; "error handling" is a topic.
 
**Step 3: Spend the budget top-down, and spike the scariest unknown first.** The top of the map gets designed mitigations, dedicated tests (Part V aims here), and hand verification (Part VI starts here). And if the top of the map contains a genuine unknown — "can the driver actually stream 50k rows without buffering?" — it gets a **spike**: a throwaway experiment run *before* the real implementation, because the cheapest time to discover the architecture doesn't work is before it exists. The junior sequence is to build the easy 80% first and momentum into the hard part; the senior sequence is to kill the riskiest assumption first, while changing course still costs nothing.

**Step 4: Publish the map.** The risk map goes into the PR description and the handoff (Part VIII): "The risk in this change is the streaming path; the mitigation is the row-count footer and its test; the tripwire is the reconciliation check finance runs." The team-of-one still owes its future self — and any human reader — the map. Uniform confident surface over uneven risk is the flattening failure, in code form.

## 3.4 The failure this prevents

**Effort spent where the work is hard instead of where the failure is quiet.** The clever aggregation gets the attention; the timezone in the join key ships on vibes. And the spike rule prevents its expensive cousin: **the load-bearing assumption discovered last** — three days of clean implementation resting on an unverified "the API surely supports batch writes," discovered false on day four.

## 3.5 Edge case

**When the map comes back empty.** Small, pure, stateless, boundary-free changes exist, and their honest map is "nothing here scores." Say that and move fast — the map's purpose is permission to be quick in the green zones as much as care in the red. A risk map that's all red is anxiety, not analysis (parent manual, 3.5): re-rank until it has a top, because a map where everything is critical navigates nothing.


---

# PART IV — IMPLEMENTATION: THE SENIOR-ENGINEER HAT

## 4.1 The mandate, and what "clean code" actually is

The implementer hat consumes the spec, the design, and the risk map, and produces code. Its forbidden list: it may not change the spec silently (spec problems go back to the PM hat, in writing), may not walk through one-way doors the design didn't open, and may not mark its own work done (that's Parts V and VI).

First, clear away the aesthetic framing. Clean code is not about beauty, style points, or impressing other engineers. **Clean code is a verification strategy.** Every clean-code rule that has survived decades of practice survives because it makes code *easier to check* — by a reviewer, by a test, by a debugger at 3 a.m., by you in six months, and by you in six *minutes* when you re-read what you just wrote. In a hundred-person team, code is read hundreds of times per write; the economics are overwhelming. Solo, the ratio is lower but the stakes are identical, because the most important reader of your code is the reviewer hat you'll wear in an hour, and everything that makes code hard to review makes your review worthless.

So every rule below should be understood as answering one question: *does this make the code's correctness easier to verify?* That framing also tells you when to break the rules — when following one would make verification harder, the rule loses. Rules serve checkability; checkability doesn't serve rules.

## 4.2 The rules, with their reasons

**Names are claims — make them true and specific.** A name is a one-word assertion about what a thing is. `days_until_expiry` is a checkable claim; `data`, `temp`, `handle`, `process`, `manager` are topics. The verification test for a name: could a reader predict the value or behavior from the name alone, and would they be *right*? Specific naming failures worth flinching at: booleans that don't read as predicates (`status` vs. `is_expired`), units missing from quantities (`timeout` — seconds? ms?; write `timeout_ms`), names that lie by staleness (the function grew a side effect and is still called `calculate_`), and near-synonym pairs (`user_data` and `user_info` in the same scope — the reader must now maintain a mental table of an arbitrary distinction, which is a tax on every line that uses either).

**Functions do one thing at one level of abstraction.** Not because small functions are pretty, but because a function that does one thing has one truth condition — it's a checkable claim (Part II of everything). The seam test from the parent manual applies directly: if you can't state what "this function is correct" means without describing its callers, the function boundary is in the wrong place. The level-of-abstraction rule is the subtle half: a function that mixes "orchestrate the export" with "escape this CSV cell" forces every reader to context-switch between altitudes, and the bugs hide at the switch points. Push detail down; keep each function's body one story at one height.

**Make illegal states unrepresentable, then make invalid data loud.** The cheapest bug is the one the type system or data structure makes impossible: if an order is either `pending` with no shipping date or `shipped` with one, a single struct with two nullable fields *represents* two illegal states (pending-with-date, shipped-without) — and code will eventually manufacture both. Model it as two shapes and the bugs are unwritable. Where the type system can't help, validate at the boundary and **fail loudly at the point of entry**: data checked once at the edge means the entire interior can trust its inputs, which deletes defensive clutter from every inner function. The alternative — every function re-checking everything, "just in case" — is how nulls travel four layers deep before exploding somewhere unrelated to their origin.

**Error handling is designed, not sprinkled.** Every operation that can fail gets a deliberate answer to three questions, decided at design altitude, not in the moment: *Can this failure be handled meaningfully here?* (If not, don't catch it — a catch block that logs and continues is usually a bug wearing safety equipment; it converts a loud failure into a silent corruption.) *What does the caller need to know?* (Errors are part of the contract — as carefully shaped as return values, carrying what/where/what-input, never a bare "operation failed".) *What state does the failure leave behind?* (The half-written file, the acquired-but-not-released lock, the incremented-but-not-completed counter — cleanup paths are top-of-risk-map by default, per Part III.)

**Comments explain why; code explains what.** A comment restating the code (`i += 1  # increment i`) is noise that will rot into a lie the first time the code changes without it. The comments that earn their place answer questions the code *cannot*: why this way and not the obvious way ("binary search regressed here — this list is <10 items 99% of the time and linear wins on cache behavior"), what invariant the next person must not break ("caller holds the lock; do not acquire here"), which external fact this depends on ("the vendor API silently truncates arrays over 100 — see their docs §4.2"), and where the bodies are buried ("this handles the 2024 data that predates the schema fix"). The test: a good comment is one whose deletion would eventually cost someone an hour.

**Duplication is cheaper than the wrong abstraction.** DRY is real, but it has a failure mode that costs more than the disease: two pieces of code that *look* similar today but serve different masters get merged into one abstraction, which then grows flags and branches as the masters diverge, until the "shared" code is a switchboard nobody can change without breaking the other caller. The rule of thumb: duplicate on two occurrences, consider on three, and abstract only when the copies are the same *because they must be* (they'd be a bug if they diverged), not merely the same *so far*. An abstraction is a claim that these things are one thing. Don't make the claim until it's true.

**Keep the diff small and the commits atomic.** Implementation proceeds in increments that match Part I's slices: each commit is one checkable change with a message stating the claim it makes ("stream export in 1000-row chunks; memory now flat at 50k rows — verified against the fixture"). The discipline exists for the reviewer hat: a 200-line diff can be prosecuted; a 2,000-line diff can only be skimmed, and skimming is recognition, and recognition is the enemy (parent manual, Part IV). When you find, mid-task, that a refactor is needed: **the refactor is its own commit, before the behavior change** — a diff that reshapes and rebehaves simultaneously is unreviewable by construction, because no reader can tell which differences are claimed-safe reshaping and which are the actual change.

**Boring is a feature.** Given two implementations, prefer the one that is more obviously correct over the one that is more impressive — the straightforward loop over the nested comprehension that took you a minute to convince yourself about. That minute of convincing is the tell: whatever convincing *you* needed at write time, the reviewer needs more of at review time, and the 3 a.m. debugger needs most of all, and every unit of it is verification budget spent on cleverness instead of on the risk map. Debugging is harder than writing; code written at the edge of your cleverness is, by definition, beyond the edge of your debugging.

## 4.3 Worked example

The CSV cell-escaping function, straight from the export task's risk map (Excel boundary — high invisibility):

A first draft handles quotes and commas inline inside the row loop, with a comment saying `# escape special chars`. The senior pass applies the rules and watch what each one buys: **extract** `escape_csv_cell(value) -> str` — now the trickiest logic in the feature is a pure function with its own truth condition, testable with fixtures against the actual RFC 4180 cases plus the Excel deviations, no database or HTTP in sight (functions do one thing; logic pulled off the boundary). **Name the danger**: the leading `=`, `+`, `-`, `@` cases aren't escaping — they're formula-injection defense, a different *why* — so they live in a separately named function `neutralize_formula_injection`, with a comment linking the advisory (comments carry why; names are claims). **Fail loud at the edge**: a value of an unexpected type raises at the cell, with row and column in the message — not `str(value)`-and-pray, which is exactly how a `None` becomes the string "None" in finance's spreadsheet, the maximum-invisibility outcome the risk map exists to prevent. **The commit**: escaping lands alone, with its test fixtures, before the streaming work — one claim, one diff, prosecutable.

The function ends up *less* clever than the inline draft and roughly twice as long. It is also checkable in ninety seconds by a hostile reader, which is the entire point.

## 4.4 The failure this prevents

**Code that resists its own verification** — the monolith function whose correctness can't be stated, the abstraction serving two masters, the silent catch block, the clever line that each future reader must re-derive. Individually these are style nits; compounded, they produce the codebase where every change is frightening because nothing can be checked in isolation — which is the codebase where velocity goes to die, one reasonable-seeming shortcut at a time.

## 4.5 Edge cases

**When the codebase has conventions, the conventions win.** Consistency is itself a verification aid — a reader's expectations are a checking tool, and code that violates local convention defeats it even when the violation is objectively better. Match the house style; propose the improvement as its own explicit change, never as a stowaway in a feature diff.

**Prototype code is exempt — if it's really a prototype.** Spike code (Part III) exists to answer a question and die. Clean-code discipline on a throwaway is waste. The one non-negotiable: the spike actually dies. The moment spike code is about to be kept, it re-enters through the full pipeline as if newly written, because "temporary" code that shipped is the most permanent code there is.


---

# PART V — TESTING: THE QA HAT

## 5.1 The mandate

The QA hat's mandate is adversarial by definition: **it is paid to make the code fail.** It consumes the acceptance claims (Part I) and the risk map (Part III), and produces evidence — not confidence, evidence. Its forbidden list is short and absolute: it may not soften a test to make it pass, and it may not count a test it hasn't seen fail.

The parent manual's law governs everything here: a test is an *independent path* to the same claim the code makes (Method 1, second-path computation, industrialized). Which immediately exposes the most common testing failure: **a test written by reading the code and encoding what it does is not an independent path** — it's the same path traced twice, and it will confirm the code's bugs with a green checkmark. Tests derive their expectations from the *spec*, the *math*, or *fixtures computed by hand* — never from the output of the code under test. If you ever find yourself running the code to find out what the test should expect, stop: you are about to laminate a bug.

## 5.2 The procedure

**Step 1: Convert every acceptance claim into at least one test.** The spec's claims (Part I, Step 2) were written to be testable; this is where the bill comes due. "Totals in the export match on-screen totals exactly" becomes a test with a hand-built fixture whose total is computed independently — on paper, or by a different tool — and asserted to the cent. If an acceptance claim resists conversion to a test, that's a finding about the claim, and it goes back to the PM hat; untestable claims are moods (Part I) and moods don't gate ships.

**Step 2: Aim the deep testing at the risk map, not at coverage.** Coverage distributes effort uniformly; the risk map distributes it correctly. The truncated-stream scenario — top of the export task's map — gets a test that kills the connection mid-stream and asserts the failure is *loud* (partial file detectable, row-count footer absent). Meanwhile the getters and the glue get little or nothing, on purpose. A test suite is a portfolio; the question is never "what percent is covered" but "is the top of the risk map covered by tests that would actually catch the scenario as written."

**Step 3: Test the boundaries with adversarial inputs.** The standing adversarial set, applied per input: the empty case (empty string, empty list, zero rows), the singular case (exactly one), the boundary pair (exactly at the limit, one past it), the malformed (wrong type, wrong encoding, truncated), the hostile (the injection string, the 10MB value, the emoji, the name with a comma and a quote *and* a newline — which, for a CSV feature, is not an exotic case but the entire job), and the temporal nasties where time is touched (DST transition day, Feb 29, a range spanning year-end). Every one of these is a limiting-case check (Method 2) made executable and permanent.

**Step 4: Assert invariants, not just examples.** Example tests check points; invariant assertions check the *shape* (Method 3). For the export: *row count in equals data rows out plus header, always. Every output line has the same column count. Parse(write(x)) == x for any x* — that last round-trip property, run across the adversarial input set, catches whole families of escaping bugs that no finite example list would. Wherever a property exists, one property test outweighs a dozen examples, because it's an independent path through *input space*, not just through the code.

**Step 5: Watch every test fail once.** A test that has never failed is unverified equipment — you have no evidence it's connected to anything. The discipline: write the test, run it against broken or absent code (or deliberately break the code once), see red, see the *right* red (the failure message names the actual problem), then make it green. Ten seconds per test. It catches the always-passing test — wrong fixture path, assertion against itself, mocked-into-vacuity — which is worse than no test, because it's no test wearing a green light.

**Step 6: Keep tests independent and honest about their level.** Each test owns its setup, asserts one claim, and can run alone in any order — shared mutable fixtures between tests recreate the shared-state hotspot *inside the safety equipment*. And keep the pyramid honest: many fast unit tests on the pure logic (this is what Part IV's seam-pulling bought — `escape_csv_cell` needs no database), fewer integration tests on the real boundaries (the actual database, the actual driver — because the contract-between-systems bugs live there and mocks, by construction, encode your *assumptions* about the boundary, which are exactly what's wrong when the boundary is wrong), and a few end-to-end tests along the money paths.

**The artifact:** the test suite, plus three lines in the PR: which acceptance claims are covered, which risk-map scenarios are covered, and — the honest part — what is *not* covered and why ("concurrent export under load: untested; accepted because [reason], tripwire in Part VII catches it in prod if the reasoning is wrong"). Uncovered-and-declared is a decision; uncovered-and-silent is the flattening failure with a test badge on.

## 5.3 Worked example

The export's totals-match claim. The lazy path: run the exporter against the staging database, eyeball the output, write a test asserting the exporter produces what the exporter produced. Green forever, worthless forever — if the filter logic double-counts a row, the test enshrines the double-count.

The QA-hat path: build a fixture of 12 rows *designed on paper* to be nasty — two rows on the date-range boundary (one in, one out, chosen to catch inclusive/exclusive confusion), one row with a negative amount, one with a NULL amount (forcing a decision: is NULL zero, skipped, or an error? — the spec didn't say; back to the PM hat, spec amended: "NULL amounts are an export error, not a zero"), amounts chosen so the correct total is computed by hand on a sticky note: 1,847.03. The test asserts 1,847.03. It fails first against a deliberately broken filter (shows red, message names the total mismatch), then passes. That test now encodes knowledge the code doesn't have — which is the entire definition of an independent path. Note also what the *fixture-building* did before any test ran: it flushed out an undecided spec question. Adversarial fixture design is spec review by other means; it's routinely where QA earns its whole salary.

## 5.4 The failure this prevents

**Test theater** — the green suite that verifies nothing: tests derived from the code they test, tests that have never failed, mocks so deep the test exercises only the mocks, coverage worshiped while the risk map's top scenario has no test at all. Test theater is strictly worse than honest gaps, because gaps keep you appropriately afraid and theater manufactures the confidence that ships the bug. The QA hat's real product was never the green checkmark; it's the *calibrated* checkmark — green that means something because it was aimed at the risk map, derived independently, and seen to fail.

## 5.5 Edge cases

**Legacy code with no tests.** You can't test-first what's already written and load-bearing. The sequence: **characterization tests** first — pin down what the code *currently does* (bugs included, labeled as such), so the ground can't shift silently — then refactor toward seams (Part IV), then test properly against the spec. Changing untested legacy code without characterization first is editing with no undo.

**When a test is more expensive than the bug.** Real case: some scenarios cost days to automate and guard against a cheap, loud, recoverable failure. The honest move is a documented manual check or a production tripwire (Part VII) instead — *declared* in the coverage notes, so it's a decision and not a hole. What's forbidden is reaching this conclusion by fatigue rather than by the risk product.

---

# PART VI — REVIEW: THE REVIEWER HAT

## 6.1 The mandate

The reviewer hat is the parent manual's prosecution (Part VI) made into a pipeline stage. It consumes the diff, the spec, and the risk map, and its mandate is: **assume the diff is wrong, and find where.** Its forbidden list defines it: the reviewer may not fix code (fixing collapses the hat back into the implementer mid-prosecution — findings go on a list, and the implementer hat addresses them afterward), may not review from memory of writing the code (only what's *on the page* counts, because the page is what ships), and may not approve on fatigue.

Solo, this hat has a structural handicap: you are reviewing code you just wrote, with the same brain, warm with the same assumptions. The handicap is real and the mitigations are mechanical:

- **A context break before review.** Time away, or at minimum a full context switch — another task, a walk, anything that flushes the writing state. Reviewing in the same breath as writing is re-reading, and re-reading is recognition, and recognition confirms (parent manual, 4.1).
- **Review the diff, not the intent.** Read what the code *says*, in the diff view, as a hostile stranger. Every place where you find yourself supplying missing context from memory ("oh, that's fine because the caller checks it") is a finding — the next reader has no such memory, and neither does the runtime.
- **Read in a different order than you wrote.** Bottom-up if you wrote top-down; start from the tests; start from the error paths. Different traversal defeats the groove your writing pass wore into the material.

## 6.2 The procedure — four passes, in order

**Pass 1 — Contract: does the diff do what the spec claims?** Diff in one window, acceptance claims in the other, literally side by side. For each claim: point to the lines that implement it, and to the test that verifies it. Claims with no lines: the feature is incomplete. Lines with no claim: scope creep — either the spec grows (PM hat, in writing) or the lines go. This pass regularly catches the most embarrassing class of failure — the diff that is excellent and *incomplete* — which the writing brain cannot catch, because it remembers intending the missing part.

**Pass 2 — The hostile trace: run the risk map's top scenario by hand.** Take the top one or two scenarios from Part III's map and trace concrete values through the actual diff, line by line, writing intermediate states (Method 5, mandatory here). For the export: trace the row containing `Smith, "Bob"\n` through escaping; trace a mid-stream exception and follow *exactly* what bytes have already been flushed to the client. The trace is the review's core; everything else is supporting. One honest hostile trace outweighs any amount of nodding.

**Pass 3 — The standing sweep.** The checklist a hundred-person org distributes across specialists, run in sequence: **Edges** — every loop's empty and single case, every index's boundary, every nullable's null path. **Errors** — every catch block justified per Part IV's three questions; every resource acquired has a guaranteed release path; every early return leaves state consistent. **Security** — every input that reaches a query, a shell, a path, a template, or a formula (CSV counts) goes through the corresponding neutralizer; no secret in code, log, or error message. **Concurrency** — anything shared, anything check-then-act, anything called twice concurrently: what happens? **Blast radius** — who *else* calls what this diff changed? (The freshly-changed hotspot: the diff's text is checked; its call sites are not — go look at them.) **Truth of names and comments** — did the diff make any existing name or comment a lie? Stale truth is introduced by exactly this mechanism.

**Pass 4 — Readability by a stranger.** Last, because it only matters if the code is correct: could a competent stranger, with no access to your memory, understand each function's claim from its name and body? Every spot where the honest answer is "they'd need to ask" is a finding — usually a renaming or an extracted function, occasionally a why-comment.

**The verdict.** Findings triaged into: *blocking* (correctness, security, data safety — fix before merge), *should-fix* (clarity and robustness — fix now while context is warm; "later" is a euphemism), and *noted* (recorded, consciously deferred). The reviewer hat writes the verdict down even solo — the list is the artifact that keeps the triage honest, and per the parent manual's flip-rate rule: **if this hat never blocks anything, it isn't reviewing; it's countersigning.** Track your own block rate. A reviewer who always approves is a rubber stamp with extra steps.

## 6.3 Worked example

The export diff, Pass 2, hostile trace of the mid-stream failure. Concrete setup: 50,000 rows, exception thrown at row 30,000 by a bad value. Trace with real states: chunks 1–29 (29,000 rows) already flushed to the client... exception propagates... the framework's default handler catches it... and, because HTTP 200 and the headers went out with chunk 1, *the client sees a normal end-of-stream*. Result: a valid-looking CSV of 29,000 rows, no error, no signal. This is precisely the top-of-map scenario, confirmed live in the diff — the code as written produces the maximum-invisibility failure. Blocking finding. The fix (row-count footer written only on success, plus the acceptance claim "finance's template checks the footer") goes back to the implementer hat, and — Part V's discipline — the *test* for it derives the expected footer from the fixture, not from the code. Note what caught this: not reading, not tests (the happy-path tests were green), but a hand trace of one adversarial scenario chosen by the risk map. That is the review working exactly as designed, and it is fifteen minutes of work.

## 6.4 The failure this prevents

**Self-approval by recognition** — the review that is actually a re-read, warm with the writer's assumptions, confirming the diff the way the writing brain confirms everything it just made. Its output is indistinguishable from a real review's (an approval), which makes it the purest competence-shaped mistake in the pipeline. The four passes exist because "look at the code carefully" is not a procedure, and only procedures survive contact with your own fluency.

## 6.5 Edge case

**The two-line diff.** Small diffs get proportionally small reviews — but never zero, and never skipping Pass 3's blast-radius question, because the two-line diff's entire risk is usually *outside its own text*: the call site that assumed the old behavior, the config that pinned the old value. The infamous outage-causing change is a one-liner often enough that "too small to review" should read, in your head, as "too small to see the blast radius of."


---

# PART VII — OPERATIONS: THE SRE HAT

## 7.1 The mandate

The SRE hat owns the code's life after the merge — deployment, observation, failure, and recovery. Its founding axiom, which reframes everything upstream: **the code is not done when it works; it's done when you can tell whether it's working, and undo it when it isn't.** A feature with no observability and no rollback plan isn't shipped; it's abandoned in production.

This hat asks the parent manual's tripwire question (Part VII, layer 3) about software: *if this were failing right now, how would we know, how fast, and what would we do?* In a hundred-person org, an on-call engineer will be woken up by this code someday; the SRE hat's job is to have already had that engineer's 3 a.m. conversation, at 3 p.m., in advance. Solo, the on-call engineer is you, or worse — it's the user, discovering the failure for you, which is the most expensive monitoring system ever devised.

## 7.2 The procedure

**Step 1: Define the health signals before shipping.** For each feature, name the small set of signals that distinguish "working" from "failing," and make them observable: a success/failure counter, a latency measure, and — this is the one always missed — a *correctness* signal where the risk map's top failure is silent. The export task: exports-started vs. exports-completed (a gap is the truncation scenario firing), p95 duration, and the row-count-footer-present rate. Generic infrastructure metrics (CPU, memory) tell you the machine is sick; only feature-level signals tell you the *feature* is lying.

**Step 2: Make the logs answer the debugging questions in advance.** Write the log lines while imagining the future failure investigation: what will that investigator need to know? At minimum, at each boundary crossing: what was attempted, with what key identifiers (request ID, row counts, durations), and on failure, the full *what/where/what-input* — never a bare "export failed." The discipline test for a log line: does it let the investigator *rule something out*? A line that can't exclude any hypothesis is noise; noise trains future-you to stop reading logs. And the standing prohibition, absolute: no secrets, tokens, or raw personal data in logs, ever — logs outlive their access controls.

**Step 3: Plan the rollback before the rollout.** Before deploying, answer in writing: *how does this change get undone, how long does that take, and what does it strand?* The last clause is the trap: code rolls back in minutes; **data written in the new format does not roll back with it.** Any change that writes new shapes to storage needs the expand/contract discipline — write new format readable by old code first, migrate, only then remove the old path — or an explicit acceptance that rollback has a data cost. A migration with no rollback plan is a one-way door being walked through at deploy speed (Part II's classification, enforced at the last gate).

**Step 4: Ship dark, then ramp.** New behavior deploys behind a flag, off. Turn on for the smallest honest audience (yourself, one account, one percent), watch the Step 1 signals, ramp. This converts deployment from a one-way bet into a sequence of two-way doors, and it separates two events that should never share a timestamp: *deploying the code* and *changing the behavior*. When both happen at once, every anomaly in the next hour has two suspects and you can interrogate neither cleanly.

**Step 5: Write the tripwires down where they'll be seen.** The PR/handoff gets the operational paragraph: the signals, the thresholds that mean trouble, and the first response. "If exports-completed drops below exports-started by more than 1% over an hour, the streaming path is failing silently; first move is flipping `export_v2` off — it degrades to the buffered path." That paragraph is the difference between an incident that lasts four minutes and one that lasts four hours, and it costs three sentences at the moment you know the system best — a price that only goes up.

## 7.3 Worked example

The export feature reaches the SRE hat. Signals chosen: start/complete counters, p95 duration, footer-present rate (the correctness signal aimed directly at the top of the risk map — note the chain: risk map chose the scenario, QA tested it, review traced it, and operations now *watches* it; one scenario, four hats, four independent layers of defense, which is exactly what a hundred-person org does with its specialist headcount). Rollback: the flag flips to the old buffered path — but Step 3's stranding question catches something: the new path writes an export-audit row per file; old code doesn't know the table. Decision recorded: audit rows are additive-only, old code never reads them, rollback is clean — one sentence in the ADR, and a landmine that would have made the *rollback itself* an incident is defused on paper.

## 7.4 The failure this prevents

**The silently failing feature** — shipped green, degrading quietly, discovered by the user, weeks in, with no logs that answer anything and no way back that doesn't strand data. And its acute form: **the deploy with no reverse gear**, where the first bad signal is followed by the realization that undoing this takes a day of manual work, so the incident is managed *forward*, under pressure, at 3 a.m. — the exact condition every step above exists to make impossible.

## 7.5 Edge case

**Scripts and one-offs.** A one-time migration script still gets the SRE minute: it prints what it's about to do and to how many rows *before* doing it (dry-run by default), it's idempotent or explicitly marked not-rerunnable, and it logs what it changed. One-off scripts touching production data have the risk profile of migrations (Part III: the only unrecoverable category) with the process weight of a snippet — the hat exists to correct that mismatch.

---

# PART VIII — COMMUNICATION: THE TECH-LEAD HAT

## 8.1 The mandate

The tech-lead hat owns every written artifact that travels between hats, between sessions, and between you and any human: PR descriptions, commit messages, ADRs, READMEs, handoffs, and incident notes. Its governing law is the parent manual's Part VII, unmodified: **answer, then reasoning, then risk — built for the reader who reads three sentences.** In software this law has extra teeth, because the artifacts are read under the worst conditions in the profession: during incidents, during onboarding, during archaeology of six-year-old decisions, by readers with zero access to the context in your head at write time. Every artifact is a message to someone debugging at 3 a.m.; write it in that light.

## 8.2 The artifacts and their architecture

**The PR description.** First line: what this change does and why, act-on-able ("Adds streaming CSV export to the reports page — finance's manual-transcription fix"). Then the load-bearing middle, which for a PR is the *verification story*: which acceptance claims are covered by which tests, what was hand-traced, what the review blocked and how it resolved. Then the risk layer, verbatim from Parts III and VII: the top scenario, its mitigation, the tripwire, the rollback. A reviewer (human or hat) should be able to reconstruct your entire risk map from the description — because the description *is* the published risk map (Part III, Step 4). What the PR description is not: a narration of the journey. Nobody needs the approaches you abandoned unless the abandonment saves them time ("also tried the temp-file approach; abandoned because of the cleanup surface — see ADR-7 — so don't re-derive it").

**The commit message.** One claim per commit (Part IV), and the message states the claim plus the *why that isn't in the diff*: "Escape leading =,+,-,@ in CSV cells — formula-injection defense, see GHSA-xxxx. Excel executes these on open." The diff shows what changed; only the message can say why, and the why is what the `git blame` archaeologist five years from now is actually digging for.

**The ADR** (template in Appendix A). Written at decision time, immutable afterward — superseded by new ADRs, never edited, because its value *is* that it's a fossil of what was known and believed at the time, bins and all.

**The README / runbook.** Answer-first means: the top of the README is *how to run it, how to test it, and where the entry point is* — the three things every arriving reader needs — before any architecture prose. The runbook section is Part VII's tripwire paragraph, promoted to a permanent home.

**The handoff.** When work pauses — end of session, end of day, passing to a human — the handoff note is mandatory and has a fixed shape: *state* (what's done, what's verified vs. merely written — the bins, always the bins), *next action* (the single concrete step, so resumption costs minutes not an hour of re-derivation), *open risks* (what's known-fragile), and *the trap* (the one thing resumption might reasonably assume that is false: "looks done but the migration hasn't run on staging"). The trap line has the highest value-per-word of any sentence in this manual's artifacts.

## 8.3 The failure this prevents

**Context evaporation** — the natural fate of everything you currently know. Software's half-life for unwritten context is brutal: by next week, the why is gone; by next quarter, the risk map is gone; by next year, the system is archaeology (Part II's fear-frozen endpoint). Every artifact above is a container built to outlive your working memory — and solo, "the team's memory" and "your artifacts" are the same thing. There is no colleague who remembers. There is only what got written down.


---

# PART IX — THE COMPETENCE-SHAPED MISTAKES OF SOFTWARE

The parent manual's Part VIII catalogued the general species; these are the software-native ones. Same defining property: **each passes review because it is shaped like skill.** Several will earn compliments on the way to causing the outage. For each: what it is, why it reads as competence, the tell, the counter.

## 9.1 Premature abstraction

Building the general mechanism before the second use case exists — the plugin system with one plugin, the config option nobody set, the base class with one subclass. **Reads as competence because** foresight and extensibility are what senior engineers are praised for. **The tell:** the abstraction has exactly one concrete instance, and its flexibility is defended with futures ("when we add more formats...") rather than presents. **The counter:** Part IV's rule — an abstraction is a claim that these things are one thing; don't make the claim before the second thing exists. Speculative *seams* are cheap; speculative *mechanisms* are debt with a flexibility costume. Write the concrete version; extract when the duplication is real.

## 9.2 Resume-driven architecture

Choosing the technology for its impressiveness — the event-sourced microservice mesh for the internal tool with nine users. **Reads as competence because** it deploys the vocabulary and patterns of systems that operate at enormous scale, and pattern-matching to giants feels like rigor. **The tell:** the justification cites what the technology *can* handle, never what this system *does* handle; the load numbers are absent from the argument. **The counter:** the architecture ADR must contain the actual numbers — requests, rows, users, growth — and the choice must be justified against them. "Boring is a feature" (Part IV) applies with maximum force at the architecture layer, because architectural cleverness is the most expensive kind to undo: every component you add is a component that pages you.

## 9.3 The heroic refactor

Stopping feature work to rewrite a subsystem wholesale, without characterization tests, in one giant diff. **Reads as competence because** cleaning up debt is virtuous, and the ambition signals ownership. **The tell:** the diff reshapes and rebehaves at once (unreviewable by construction — Part IV), and no test pinned the old behavior first. Second tell, from the parent manual's procrastination pattern: the refactor started when the *actual* task got hard. **The counter:** refactors ship in small, behavior-preserving commits, each one provably safe, characterization tests first (Part V), interleaved with — never instead of — the work that funds them. If you can't state the refactor's next safe step, you're not refactoring; you're rewriting, and rewrites are one-way doors that get ADRs.

## 9.4 Defensive programming as anxiety

Null checks on values that cannot be null, try/catch around code that cannot throw, validation re-run at every layer. **Reads as competence because** it looks like caution, and caution reads as seniority. **The tell:** the defenses have no theory — no statement of which boundary makes the check necessary — and the same data is checked four times on its way down. **The counter:** Part IV's boundary discipline. Validate loudly *once*, at the edge; let the interior trust its inputs. Scattered defense isn't safety, it's noise that hides the one check that matters — and the catch-log-continue block is the worst of it: an error path that converts loud failures into silent corruption while looking like responsibility.

## 9.5 Test theater (the suite that verifies nothing)

Covered in Part V, listed here because of *why it survives*: **it reads as competence** — high coverage numbers, green badges, hundreds of tests — and every artifact of diligence is present except the diligence. **The tell:** expectations derived from the code under test; tests that have never been seen red; mocks so deep the suite tests the mocks. **The counter:** Part V entire — expectations from spec and hand-computation, every test fails once, depth aimed at the risk map, coverage numbers treated as a smell when they're the headline.

## 9.6 The silent scope expansion

"While I'm in here" — the drive-by rename, the bonus fix, the improved adjacent function, all riding inside a feature diff. **Reads as competence because** each improvement is individually real, and noticing them is genuinely a senior skill. **The tell:** Pass 1 of review finds lines with no acceptance claim; the diff's title describes a third of its contents. **The counter:** noticing is the skill; *bundling* is the mistake. Every noticed improvement goes on a list and ships as its own small, reviewable, revertable diff. Bundled changes can't be reverted independently — when the feature rolls back, the good fixes go with it, and when the "harmless" rename breaks something, the feature gets blamed. One claim, one diff, no passengers.

## 9.7 Configuration worship

Making behavior configurable instead of making a decision — the flag for everything, the YAML that grows a schema, the system whose actual behavior is unknowable without reading production config. **Reads as competence because** flexibility looks like generosity toward the future and deciding looks like arrogance. **The tell:** config options that have had the same value everywhere, forever; options added because a decision was contentious, not because variation was needed. **The counter:** config is for things that genuinely vary across environments or users; everything else is a decision, and decisions get *made* (Part II) and recorded. Every option multiplies the test matrix and the support surface; an un-made decision isn't deferred cost, it's cost with interest.

## 9.8 Cleverness at the wrong layer

The brilliant one-liner, the metaprogramming trick, the scheme that saves twenty lines and costs every future reader ten minutes. **Reads as competence because** it *is* skill — genuinely, that's what makes it poisonous; the reviewer's admiration is the approval mechanism. **The tell:** Part IV's minute-of-convincing — if you needed time to convince yourself, so will everyone, forever, and at 3 a.m. no one can afford it. **The counter:** spend cleverness where it pays rent — in the algorithm when the risk map says performance matters, in the design of seams — and write everything else as boringly as possible. The senior signature isn't clever code; it's clever *placement* of the two spots that are allowed to be clever, each with a comment explaining why.

## 9.9 Optimization without a measurement

Rewriting for speed on the theory of speed — caching the uncached, pooling the unpooled, micro-tuning the loop that runs once — with no profile, no baseline, no target. **Reads as competence because** performance work is high-status and the changes *sound* faster. **The tell:** no before number, no after number, no stated budget; the word "should" doing the work of a benchmark ("this should be much faster"). **The counter:** the parent manual's Method 8 — no internal reasoning substitutes for the external check. Performance claims are empirical claims: profile first (the bottleneck is reliably not where intuition says), state the budget from the spec ("300ms p95" — Part I wrote it down for exactly this moment), measure after, and ship the numbers in the PR. An optimization without numbers is a rumor with a diff attached.

## 9.10 The framework-shaped solution

Reaching for the ecosystem's heavyweight answer — the queue, the ORM layer, the orchestration platform — when the problem is forty lines of code. **Reads as competence because** it demonstrates ecosystem fluency and "don't reinvent the wheel" is real wisdom. **The tell:** the dependency's feature list is doing the persuading; the actual requirement uses 3% of it; and the integration code approaches the size of the direct solution. **The counter:** the build-vs-buy row in the ADR carries the honest total — the dependency's cost isn't its install command, it's its upgrade treadmill, its CVE stream, its abstractions leaking into your seams, and its failure modes becoming yours. Sometimes the wheel you'd reinvent is a hubcap. Forty lines you own completely is often cheaper than forty thousand you don't.

## 9.11 The common root, again

Every entry above optimizes how the work *looks to an engineer* — foresightful, scaled, cautious, flexible, fast, fluent — at the expense of what the work *does under maintenance and failure*, which is graded later, by production, when the looking is long over. Same root as the parent manual's 8.13, same decision to make: be graded by the later test. In software the later test always arrives, it keeps receipts, and it pages you at night.


---

# PART X — THE PIPELINE: HOW THE HATS HAND OFF

## 10.1 The full sequence

For a substantial piece of work, the hats run in order, each consuming the previous artifact and producing its own:

1. **PM** → one-page spec: problem sentence, acceptance claims, non-goals, slices, door class.
2. **Architect** → data model, graded seams, door-sorted decisions, ADRs. *Gate: the spec is closed; changes to it are explicit amendments.*
3. **Staff engineer** → the ranked risk map; spikes run on the scariest unknowns. *Gate: no implementation until the top-of-map unknowns are spiked.*
4. **Implementer** → code, in slice-sized atomic commits. *Gate: no silent spec or design changes; refactors ship separately.*
5. **QA** → tests derived from spec and fixtures, aimed at the risk map, each seen red once; the coverage-and-gaps note. *Gate: untestable claims go back to the PM hat.*
6. **Reviewer** → after a context break: the four passes, the hostile trace, the triaged findings. *Gate: blocking findings return to the implementer; the reviewer fixes nothing.*
7. **SRE** → signals, logs, rollback plan, dark launch, tripwire paragraph. *Gate: no rollback plan, no deploy.*
8. **Tech lead** → the PR description, ADR links, handoff note. *Gate: the artifact set is the definition of done.*

The gates are the point. Each one is a place where the work can be sent *backward*, and backward motion at a gate is the pipeline succeeding — the same claim as the parent manual's flip-rate: a pipeline that never bounces work is a conveyor belt with ceremonial checkpoints. Track your bounce rate the way you track review blocks. Zero means the hats have collapsed.

## 10.2 Scaling the pipeline to the task

The full sequence on a two-line fix would be theater (Part IX applies to process too). The pipeline compresses, but it compresses by *shrinking the artifacts, never by deleting the questions*:

**Small (a bugfix, a config change, < ~50 lines):** the pipeline runs in one head in about five minutes, but every hat gets its sentence — the problem sentence and the acceptance claim (PM); "does this touch a one-way door?" (architect — for a bugfix, usually "does the fix change any contract?"); the blast-radius question (staff: what calls this? what assumed the old behavior?); the fix, boring (implementer); one test derived from the bug's reproduction, seen red first — the bug report *is* the fixture (QA); the diff read cold once, Pass 3's sweep on the changed lines (reviewer); "how do I know it's fixed in prod, and does this deploy alone?" (SRE); a commit message with the why (tech lead). Five minutes. The infamous outages live exactly here, in the changes deemed too small for the questions.

**Medium (a feature, days of work):** every artifact exists, at paragraph scale — the one-page spec, an ADR only if a one-way door appears, a risk map of three to five scenarios, the full review passes, the tripwire paragraph.

**Large (a system, weeks):** the full sequence, full artifacts, plus one addition — the pipeline runs *per slice* (Part I, Step 4), not once for the whole. Each vertical slice goes spec-to-deploy before the next widens, so the architecture's real-world grade arrives at slice one, while it's still cheap to be wrong.

## 10.3 The definition of done

Work is done when the artifact set exists and the gates have passed — not when the code runs, not when you feel done, not when the demo worked. Concretely, the checklist that nothing ships without:

- Every acceptance claim has a passing test that was once seen failing.
- The top of the risk map has a mitigation, a test, and a tripwire.
- The diff was reviewed cold, and the review has a written verdict.
- The rollback path is stated, including what it strands.
- The PR description carries the answer, the verification story, and the risk — in that order.
- The handoff note exists, with the trap line.

Solo, this list is the conspiracy of four people it takes to skip the gates in a real org, reduced to a piece of text you must consciously defy. Make defying it feel like what it is.

---

# THE PRE-SHIP SELF-TEST

Five questions, run on every change before it ships — the parent manual's gate, specialized. Each demands a specific object as its answer; producing the object is the test.

**1 — What problem does this solve, and which test proves it?**
*Objects: the problem sentence, and the name of the test that encodes the acceptance claim — a test whose expectation came from the spec or a hand-built fixture, not from the code's own output.* Catches: building the ticket instead of the need; test theater; the excellent-but-incomplete diff.

**2 — What's the top of the risk map, and where are its three defenses?**
*Objects: the single likeliest-quietest-costliest failure scenario, and its test (QA), its hand trace (review), and its tripwire (SRE).* One scenario should thread all three; if you can't name the scenario, Part III never ran, and if it has fewer than three defenses, name which gap you're accepting and why. Catches: effort on the hard part instead of the quiet part; the silently failing feature.

**3 — Did anything walk through a one-way door — and does its ADR exist?**
*Objects: the list of contracts, formats, schemas, and public shapes this change touches, and the decision record for each.* Includes the sneaky ones: the output format someone will script against, the migration, the log line someone will alert on. Catches: doors walked backward by the first draft; the fear-frozen future system.

**4 — Was the diff reviewed cold, and what did the review find?**
*Objects: the context break (when?), and the findings list — including, per the block-rate rule, the honest answer if the list is empty again.* A review with no findings, again, is a countersignature. Catches: self-approval by recognition; the blast radius nobody looked at.

**5 — If this breaks at 3 a.m., what does the responder see, and what's their first move?**
*Objects: the signal that fires, the log line they'll read, and the rollback command — plus what the rollback strands.* If any of the three doesn't exist, the feature isn't done; it's deployed. Catches: the deploy with no reverse gear; context evaporation at the worst possible hour.

**If any object can't be produced, the change is not done.** The fix is usually minutes. The failure it prevents usually isn't.

---

# APPENDICES

## Appendix A — Templates

**The one-page spec (PM hat):**
> **Problem:** [Who] can't [what] because [obstacle], costing [what].
> **Acceptance claims:** 1. [testable] 2. [testable] 3. [testable]
> **Non-goals:** [explicitly out, this release]
> **Slices:** 1. [thinnest vertical path] 2. [widen] ...
> **Door class:** [one-way / two-way, and why]

**The ADR (architect hat):**
> **ADR-N: [decision] — [date] — [status: accepted / superseded by ADR-M]**
> **Context:** the forces in play, with the actual numbers.
> **Decision:** what was chosen.
> **Alternatives:** each one genuinely developed, with the real reason it lost.
> **Consequences:** what this costs, including the ugly parts, binned honestly (verified / recalled / guessed).

**The PR description (tech-lead hat):**
> **What & why:** one act-on-able sentence.
> **Verification:** claims → tests; what was hand-traced; what the review blocked and how it resolved.
> **Risk:** top scenario, mitigation, tripwire, rollback (and what it strands).
> **Not covered:** the declared gaps, with reasons.

**The handoff note:**
> **State:** done vs. verified vs. merely written (bins).
> **Next action:** the one concrete step.
> **Open risks:** what's fragile.
> **The trap:** the one false thing resumption would assume.

## Appendix B — Clean-code quick reference

One line each; the reasons live in Part IV.
- Names are claims: predict-the-behavior test; units in quantity names; booleans read as predicates.
- One function, one thing, one altitude.
- Illegal states unrepresentable; validate loudly once, at the edge; interior trusts.
- No catch without a theory: handle meaningfully, or let it fly loud.
- Comments carry *why*, invariants, external facts, and buried bodies — never *what*.
- Duplicate twice; abstract when divergence would be a bug, not before.
- One claim per commit; refactor commits never change behavior; behavior commits never reshape.
- Boring beats clever everywhere the risk map doesn't say otherwise — and there, comment the cleverness.
- New code matches house style; improvements ship as their own diffs.

## Appendix C — The hotspot card (carry everywhere)

Bugs concentrate at: **boundaries** (the contract between systems, not either side) · **shared state** (every step down the mutability ladder is a priced decision) · **time** (TZ, DST, boundaries, durations-vs-instants) · **concurrency** (check-then-act, double delivery) · **error paths** (least tested, most critical; failures during failures) · **config** (the code is fine; the environment isn't) · **migrations** (the only unrecoverable class) · **the freshly changed** (the fix is checked; its call sites aren't).

## Appendix D — Drills

**Drill 1 — The problem-sentence rep.** For a week, no task starts — however small — until the [who / can't / because / costing] sentence is written. The tickets where it comes hard are the week's real findings.

**Drill 2 — The red-first rep.** Every test, seen red before green, no exceptions, for a month. Count the tests that were *wrong* when red (bad fixture, self-referential assertion). That count is the bug rate of your safety equipment.

**Drill 3 — The cold-trace rep.** On every substantive diff, one hostile hand trace of the risk map's top scenario, intermediate values written down. Count the blocking finds. This drill has the best catch-rate per minute in the whole pipeline.

**Drill 4 — The blast-radius rep.** For every "trivial" change for two weeks: before shipping, list the call sites and consumers of the thing changed, from the code, not from memory. The gap between the remembered list and the real one is the measure of how much your memory should be trusted (spoiler: it's the same machinery that wrote the bug).

**Drill 5 — The 3 a.m. rep.** After each feature, write the incident line: signal → log → first move → rollback → stranded. If any link is missing, the feature is still open.

---

# CLOSING

The whole manual in one paragraph, for the days there's no time for more:

**Recover the problem before building the ticket. Shape the data before the behavior, and grade every seam. Sort the doors, and spend where undoing is expensive. Map where this specific work fails quietly, and spike the scariest unknown first. Write code whose correctness a hostile stranger can check, in diffs small enough to prosecute. Derive tests from the spec, never from the code, and watch each one fail once. Review cold, trace by hand, and let the reviewer block. Ship dark, watch the signals, and never deploy what you can't undo. Write down the why, the risk, and the trap, because there is no colleague who remembers — there is only what got written. And distrust most the change that feels too small for all this, because that's the one that pages you.**

A hundred-person team is a machine for disagreeing with itself before the customer can. You now have the machine. It runs on sequence, artifacts, and gates you are not allowed to waive alone — and it fits in one head, provided the head changes hats on purpose, one at a time, in order.

Run it until the hats stop feeling like process and start feeling like suspicion in the right places at the right stage. That's the craft. It's yours now.

*— End of manual.*


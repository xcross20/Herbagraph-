# Issue 58 spike: authoritative Ask seams

Inspected 2026-08-18 on `integration/agent` @ `e42737f`. No V2 flags activated.

## Seams today

| Concern | Module | Authority |
|---|---|---|
| Turn transaction / 19 steps | `app/discovery/turn_engine.py` | Owns persist order. Does not own next-response mode. |
| Conversation policy | `app/discovery/orchestrator.py` | Picks a `NextAction` from `generate_actions` + ranker. LLM may only verbalize. |
| Question catalog | `app/discovery/actions.py` `QUESTIONS` | Filters by asked/answered *wording* and fact keys, not canonical slots. |
| Marker questions | `app/discovery/questions.py` | Extra already-tested questions from hypothesis markers. |
| Ranker | `app/discovery/ranker.py` | Scores persisted gaps + catalog questions. Safety S3/S4 override. No pause awareness. |
| Intent | `app/discovery/intent.py` | Regex bag. Missing pause, next-steps, repetition, cannot-provide-evidence. |
| Coverage | `app/discovery/coverage_governor.py` + catalog JSON | Test×concept relations. Not a response-mode owner. |
| Scientific gate | `app/discovery/scientific_output.py` | Fail-closed on rendered statements. |
| Citations | `app/discovery/literature.py` | PubMed-only. No claim-card entailment. |
| Lab engine | `app/api/v1/labs.py` + parser/pipeline | Separate from Ask. Documents can route labs away. Ask must not reimplement. |
| Case projection | `app/discovery/service.py` `rebuild_case` / `persist_map_version` | Findings + map. No focus/slot ledger. |

## Gap that causes the observed failure

There is **no single decision seam** after mutations that chooses:

`active concern × answered slots × user control intent × response mode × next-evidence`.

`asked`/`answered` are finding names and question codes. Semantically equivalent answers still re-open laterality/timing. Pause is not persisted. “What should I do?” is classified as a question, so another intake question wins.

## Recommended design (option 3 from the issue)

Add a **persisted Case-governed controller** behind `DISCOVERY_USEFULNESS_GOVERNOR_V1`:

1. `classify_control_intent(text)` — pause/resume/synthesis/next-steps/research/cannot-provide/frustration.
2. `apply_focus_transition` — append-only; pause ≠ close.
3. `answer_slot_ledger` — canonical keys, not prompt wording.
4. `decide_response_mode` — deterministic priority in the issue.
5. Existing ranker remains the next-evidence scorer **after** mode says a question is allowed.

LLM verbalizes the chosen mode. It cannot override it.

## Not chosen

1. Prompt-only fix — will still repeat after restart.
2. Ephemeral chat memory — dies on return visit.

## Spike complete

Slice A implements the controller and red fixture. Slices B–D reuse this seam.

# ADR-MVP-006 — Persisted usefulness governor

Status: Draft  
Issue: #58  
Date: 2026-08-18

## Decision

Ask response mode, concern focus, and answered semantic slots are persisted Case state. The LLM verbalizes; it does not choose the mode.

## Alternatives rejected

1. Prompt-only conversation fix — repeats after restart.
2. Ephemeral chat-memory controller — lost on return visit.
3. **Persisted Case-governed controller** — accepted.

## Ownership

- `app/discovery/usefulness.py` owns focus, slots, control intent, and `decide_response_mode`.
- `orchestrator.py` remains the only place that binds that mode to a `NextAction`.
- Coverage, ranker, lab engine, and scientific gate stay on their existing seams.

## Rollback

Disable `DISCOVERY_USEFULNESS_GOVERNOR_V1`. `control_json` remains unused. Downgrade drops the nullable column.

## Production

Flag `DISCOVERY_USEFULNESS_GOVERNOR_V1` stays off. Additive `control_json` is inert to old readers. Founder standing order 2026-08-18 authorizes merge to `main` and production deploy of this dormant Slice A controller.

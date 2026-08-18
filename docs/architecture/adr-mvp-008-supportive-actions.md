# ADR-MVP-008 — Supportive actions without treatment authority

Status: Draft  
Issue: #64  
Date: 2026-08-18

## Decision

`SUPPORTIVE_ACTIONS` is a Case-governed response mode. The LLM may explain eligible candidates; it may not invent, re-rank, or rescue ineligible ones. Production activation remains Founder-gated.

## Alternatives rejected

1. Prompt-only “give some tips” — repeats and invents supplements.
2. Reuse the lab-report recommendation engine on symptoms — treats observations as measured biomarkers.

## Rollback

Keep `SUPPORTIVE_ACTIONS_V1` and `SUPPLEMENT_DISCUSSION_V1` off. Governor still refuses another intake question on explicit relief intent.

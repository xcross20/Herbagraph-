# M03–M13 status

Branch: `grok/hg-m03-m13-metabolic-wedge` · PR #74 · base `integration/agent`

Shipped on the branch:
- Kernel + stack evaluator + public `POST /api/v1/public/stack-check`
- `/stack.html` receipt UI
- `POST /api/v1/labs/manual` and `PATCH /api/v1/labs/{id}/results`
- Consumer safety adapter (`ranking_mode` on `check_safety`)
- Typed lab schemas

Still wire on this branch in follow-up commits if missing from HEAD:
- Workspace typed grid (`#upload?mode=manual`)
- Landing hero CTAs
- Ask `startOrContinue` door intercept + `POST /api/v1/cases/route`
- RYR/cassia graph edges
- Worker skip-parse for `manual://`
- `report.html?mode=consumer`
- `GET /api/v1/tracking/follow-up-plan`

Ask remains the investigation door for niche overlapping cases.

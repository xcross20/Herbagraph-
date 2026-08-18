# CI baseline certification (PR-43)

Recorded 2026-08-18 after reproducing the red `gates` job on `cfe8585`.

## Causal failures from PRs 40–42 / 43

| Job | First causal failure | Not a separate cause |
|---|---|---|
| `gates` on `cfe8585` | `test_agent_branches_are_reviewable_but_never_auto_corrected_or_promoted` — `promote-uat` lost the `grok/` head_ref guard during the main merge | 1736 other passing tests |
| `postgres-truth` on PRs 40–42 | Alembic `Multiple head revisions` (`u1v2w3x4y5z6` vs `u2v3w4x5y6z8`) | later uniqueness log lines from the intended race |
| `postgres-truth` on `cfe8585` | green after pinning the truth-layer upgrade to `u2v3w4x5y6z8` | — |

## Exact SHAs at certification time

| Plane | SHA / note |
|---|---|
| `main` (this packet's parent) | `cfe8585c6b28b646d9abc7a02800bdcce48d739c` |
| `integration/agent` | fast-forwarded to the same SHA after PR #43 |
| Railway production (last verified deploy) | `a9a9755` image from 2026-08-18; redeploy after this packet |
| Railway UAT | tracks `integration/agent` |

CI Python is 3.11, matching Railway. Postgres service uses `pg_isready` before jobs run.

Required Discovery/PostgreSQL tests are marked `requires_postgres`. When `HERBAGRAPH_REQUIRE_POSTGRES=1`, a skip of those tests fails the job. Optional Playwright/live E2E skips remain allowed.

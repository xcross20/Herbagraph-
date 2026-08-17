# HerbaGraph UAT and PR previews

There is **no** permanent `uat` git branch. `integration/agent` is the UAT branch.

```text
grok/<issue> PR
→ Railway temporary PR preview
→ Codex/Grok protocol completes (GitHub)
→ merge into integration/agent
→ Railway persistent UAT
→ Founder UAT approval
→ promotion PR: integration/agent → main
→ Railway production
```

Railway tests the **application**. The Codex↔Grok protocol is tested in **GitHub**.

## Persistent UAT

| | |
|---|---|
| Railway project | `charming-charisma` |
| Environment | `uat` |
| Git source | `integration/agent` |
| Human demo | https://herbagraph-uat.up.railway.app/demo |
| Health | https://herbagraph-uat.up.railway.app/health |
| Meta | https://herbagraph-uat.up.railway.app/meta |

UAT has its own Postgres, Redis, `SECRET_KEY`, and `ENCRYPTION_KEY`. Auth is `local` with guest access for synthetic demos. Do not load patient data or PHI.

A human demos UI changes at `/demo` (also `/demo.html`) before any promotion PR to `main`.

Production remains https://www.herbagraph.com (`main` should be the production source). Do not retarget production until a founder-approved promotion PR lands.

## Isolation checklist

| Plane | Database | Auth | Cookies / URL | Notes |
|---|---|---|---|---|
| `uat` | Dedicated Railway Postgres | `AUTH_PROVIDER=local`, guest on | `herbagraph-uat.up.railway.app` | Synthetic catalog only |
| `production` | Existing production DB | `AUTH_PROVIDER=supabase` | `www.herbagraph.com` | Patient data stays here |
| PR preview | Fresh copy of UAT services | Inherits UAT | Unique Railway URL | Deleted when the PR closes |

LLM/NCBI/USDA keys currently still match production (quota only). Founder should mint UAT-only keys before any load test. Sentry is not configured on either plane yet — if it is added, set `SENTRY_ENVIRONMENT=uat` vs `production`.

## PR previews

Railway PR Environments inherit from the persistent `uat` environment (not production). Bot PR Environments are on so Grok-opened `grok/**` PRs get a preview URL.

Each `grok/**` PR gets a unique URL and is removed when the PR closes.

## Founder gates

Protect `main` and `integration/agent` (PRs + CI). Promotion `integration/agent` → `main` requires founder approval. Do not activate the Codex↔Grok `agent-loop` label until those protections exist.

## Protocol canary (Issue #7)

After UAT is live and protections are on, a safe canary PR should prove:

1. Codex reviews the exact SHA
2. Codex returns `CHANGES_REQUIRED`
3. Grok changes only an allowed fixture
4. Grok pushes a new SHA
5. Codex re-reviews
6. Duplicate/stale events do nothing
7. Approval does not merge or deploy
8. Three failed cycles stop for founder review

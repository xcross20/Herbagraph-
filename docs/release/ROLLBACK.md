# Application rollback and restore

Application rollback is independent of schema rollback.

## Application rollback

1. Redeploy the previous known-good image/SHA on Railway production.
2. Do not stamp or downgrade PostgreSQL unless the SHA requires it.
3. Confirm `/health` and `/meta` on the rolled-back SHA.
4. Confirm one synthetic Case still loads and the map fingerprint is unchanged.

Accepted window: complete within one deploy cycle. Do not orphan Case rows by dropping tables.

## Schema rollback

See `MIGRATION_RUNBOOK.md`. Preferred restore is a PostgreSQL dump taken before upgrade, not `alembic downgrade` through historical heads.

Current accepted Alembic head: `u6d7e8f9g0h1`.

## On-call for zero-tolerance tripwires

| Signal | Response |
|---|---|
| duplicate active findings | Halt writes. Rebuild from append-only history. |
| inactive finding exposed as active | Halt map publish. Fix projection. |
| branch closed without direct evidence | Reopen the branch. Preserve prior close reason. |
| unknown coverage as negative | Quarantine the map version. |
| invalid scientific output attempted | Fail closed. Do not ship the payload. |
| safety escalation lost | Restore the safety finding and stop Discovery. |
| parser false success | Mark document unsupported and unlink findings. |

## Performance targets (measured, not estimated)

- p95 non-LLM API: record in UAT before calling MVP ready.
- p95 full turn: record provider time separately.
- Restore point / restore time: measure on the next UAT backup rehearsal.

GitHub Actions billing currently blocks exact-SHA CI proof.

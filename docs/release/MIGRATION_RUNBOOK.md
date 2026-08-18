# PostgreSQL migration runbook (PR-44)

## Strategy

Preferred before relying on production data: one accepted Alembic head (`u3a4b5c6d7e8`). The unaccepted V2 sibling revision is archived and is not applied. Historical `sa.Uuid()` columns that could not FK to `CHAR(36)` IDs are stored as `CHAR(36)`.

Empty environments use `alembic upgrade head`. Do not use `Base.metadata.create_all` as certification.

## Preflight

```bash
python3 scripts/preflight_migrate.py
```

Refuses to continue if `alembic heads` is not exactly `u3a4b5c6d7e8`.

Do not `alembic stamp` UAT or production unless the schema fingerprint matches the accepted ORM/discovery tables. Founder approval is required before stamping a live database.

## Empty database

```bash
alembic upgrade head
python3 scripts/schema_fingerprint.py
```

## Upgrade from the truth-layer increment

```bash
# CI rehearsal only
python3 scripts/ci_postgres_migrate.py --mode upgrade
```

## Backup and rollback

- Take a PostgreSQL dump before any live upgrade.
- Rollback limit: downgrade is supported only for the truth-layer increment `u2 → u1`. Historical revisions are not a practical rollback path.
- Stranded state: a failed empty upgrade leaves the public schema dropped/recreated by the CI helper; live upgrades must be stopped and restored from dump.

## Expected duration

Empty CI rehearsal: under two minutes. Live UAT/production upgrade: measure after the first dry run.

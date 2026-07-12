# HerbaGraph Production Deployment

This guide covers launching HerbaGraph for real users (clinician pilot or early access).

## Recommended stack (fastest path)

| Layer | Recommendation |
|-------|----------------|
| **App + worker** | [Railway](https://railway.app), [Render](https://render.com), or a VPS with Docker Compose |
| **PostgreSQL** | Railway Postgres, [Neon](https://neon.tech), or [Supabase](https://supabase.com) database |
| **Redis** | [Upstash](https://upstash.com) or Railway Redis (required for Celery report jobs) |
| **Auth** | **Supabase Auth** (`AUTH_PROVIDER=supabase`) |
| **LLM** | MiniMax (`LLM_PROVIDER=minimax`) or OpenAI |
| **Files** | Ephemeral volume or S3-compatible bucket for `UPLOAD_DIR` |

HerbaGraph ships as a **single Docker image** serving API + static frontend (`frontend/` mounted at `/`).

## Pre-flight checklist

```bash
cp .env.example .env
python scripts/generate_encryption_key.py   # sets ENCRYPTION_KEY
python scripts/validate_seed_counts.py
./scripts/ops_readiness_check.sh --strict
```

Required production env vars:

```env
DEBUG=false
AUTH_PROVIDER=supabase
ADMIN_EMAILS=you@yourdomain.com
SECRET_KEY=<long-random-string>
ENCRYPTION_KEY=<fernet-key>
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=redis://...
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=...
LLM_PROVIDER=minimax
MINIMAX_API_KEY=...
LLM_MODEL=MiniMax-M2.7
HERBAGRAPH_CATALOG_ONLY_REASONING=0
REQUIRE_EMAIL_VERIFICATION=true
ALLOW_GUEST_AUTH=false
```

## Option A — Docker Compose on a VPS (DigitalOcean, Hetzner, etc.)

1. Provision Ubuntu 22+ server with 4 GB+ RAM.
2. Install Docker + Docker Compose.
3. Clone repo, configure `.env` with managed Postgres + Redis URLs.
4. Point domain A record to server IP.
5. Put Caddy or nginx in front for TLS:

```bash
docker compose up -d --build
docker compose exec api alembic upgrade head
docker compose exec api python scripts/reseed_db.py
```

6. Set `CORS` — with `DEBUG=false`, update `app/main.py` `allow_origins` to your domain (or add `CORS_ORIGINS` env support before launch).

## Option B — Railway / Render (managed)

**Services to create:**

1. **PostgreSQL** — copy `DATABASE_URL` (use `postgresql+asyncpg://` prefix).
2. **Redis** — copy `REDIS_URL`.
3. **Web service** — Dockerfile, port 8000, health check `/health`.
4. **Worker service** — same image, command:
   ```
   celery -A app.workers.celery_app worker --loglevel=info
   ```

**Deploy steps:**

```bash
# One-time after first deploy
railway run alembic upgrade head
railway run python scripts/reseed_db.py
```

Set all env vars on **both** web and worker services.

## Supabase Auth setup

1. Create Supabase project.
2. Authentication → URL configuration:
   - Site URL: `https://yourdomain.com`
   - Redirect URLs: `https://yourdomain.com/app.html`
3. Copy **Project URL** → `SUPABASE_URL`
4. Copy **anon/public key** → `SUPABASE_ANON_KEY`
5. Enable email confirmation if `REQUIRE_EMAIL_VERIFICATION=true`.

Users sign in via `/app.html`; local user rows are created on `/api/v1/auth/sync`.

## Admin console

Set `ADMIN_EMAILS` to comma-separated admin emails, then sign in and open:

- **https://yourdomain.com/admin/** — hub
- **https://yourdomain.com/admin/users.html** — list / activate / role / delete users
- **https://yourdomain.com/admin/validation.html** — feedback analytics

Deleting a Supabase user removes HerbaGraph data only; remove the auth identity in Supabase dashboard if needed.

## Post-deploy smoke test

```bash
curl https://yourdomain.com/health
# Sign in at /app.html
# Upload sample lab from samples/lab_reports/
# Generate report, confirm 4-lane intervention library loads
```

## Ongoing operations

| Task | Command |
|------|---------|
| Reseed catalog after evidence changes | `bash scripts/ops_reseed.sh` |
| Readiness check | `bash scripts/ops_readiness_check.sh` |
| Migrations | `alembic upgrade head` |
| Logs | `docker compose logs -f api worker` |

## Security notes for launch

- Never commit `.env`
- `DEBUG=false` in production
- Restrict `ADMIN_EMAILS` to trusted operators
- Use HTTPS everywhere
- Rotate `SECRET_KEY` and `ENCRYPTION_KEY` per environment
- Keep disclaimers visible on all reports

## Custom domain + TLS with Caddy (example)

```
yourdomain.com {
    reverse_proxy localhost:8000
}
```

Run Caddy on the host; keep `api` container on port 8000 internal.
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
ADMIN_MASTER_PASSWORD=<strong-password-8+chars>
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
3. **Web service** — Dockerfile, port 8000, health check `/health`. Migrations run on container start.
4. **Redis** — required for lab uploads and report generation (`REDIS_URL` on web + worker).
5. **Worker service** — same repo/image, `railway.worker.toml` or start command:
   ```
   celery -A app.workers.celery_app worker --loglevel=info
   ```
6. **ENCRYPTION_KEY** — required for lab file uploads (Fernet). Generate once:
   ```bash
   python scripts/generate_encryption_key.py
   ```
   Set the same key on **web and worker**.

**Deploy steps:**

```bash
# Migrations run automatically on each web deploy (scripts/start_api.sh).
# One-time catalog seed after first successful deploy:
railway run python scripts/reseed_db.py
```

Set all env vars on **both** web and worker services.

**Critical — link Postgres to the web service**

In Railway → web service → **Variables**, add:

```env
DATABASE_URL=${{Postgres.DATABASE_PRIVATE_URL}}
```

Use the **private** URL when Postgres and the API run in the same Railway project (recommended). If you use the public proxy URL instead, the app auto-appends `ssl=require`.

**Alternative:** use your Supabase project's Postgres:

1. Supabase → **Project Settings** → **Database** → **Connection string**
2. Type: **URI** · Method: **Session pooler** (port **6543**)
3. **Do not** use **Direct connection** (`db.*.supabase.co`) — it is IPv6-only and returns "Network is unreachable" on Railway.
4. Paste as `DATABASE_URL`. URL-encode special characters in the password.

Full variable template: `railway.env.example` in the repo root.

If `DATABASE_URL` is missing or points at `localhost`, sign-in will succeed in Supabase but `/api/v1/auth/me` returns 500/503.

Verify after deploy:

```bash
curl https://www.herbagraph.com/api/v1/system/status
# Expect: "database":"connected","schema_ready":true
```

## Supabase Auth setup

1. Create Supabase project.
2. Authentication → URL configuration:
   - Site URL: `https://yourdomain.com` (or `https://www.herbagraph.com`)
   - Redirect URLs — **must include the auth callback** (email confirm / OAuth land here):
     - `https://yourdomain.com/auth/callback.html`  ← required for email confirmation
     - `https://yourdomain.com/app.html`
     - `https://yourdomain.com/login.html`
     - `https://yourdomain.com/signup.html`
     - `https://yourdomain.com/reset-password.html`
     - Local: `http://localhost:8000/auth/callback.html` (plus the same paths for other auth pages)
3. Copy **Project URL** → `SUPABASE_URL`
4. Copy **anon (JWT) public key** → `SUPABASE_ANON_KEY`  
   Prefer the classic `eyJ…` **anon** key for the browser Supabase client.  
   `SUPABASE_PUBLISHABLE_KEY` works as a fallback when configured.
5. Optional: `SUPABASE_JWT_SECRET` (Settings → API → JWT Secret) so the API can verify tokens without JWKS.
6. Enable **Confirm email** under Authentication → Providers → Email if you want confirmation links.

**Email confirmation flow**

1. User signs up on `/signup.html` → Supabase sends mail with `emailRedirectTo=/auth/callback.html` (no `#hash`).
2. User clicks link → Supabase verifies → redirects to `/auth/callback.html?code=…` (or hash tokens).
3. Callback page exchanges the session, calls `POST /api/v1/auth/sync`, then sends the user to `/app.html`.

If confirmation opens a Supabase error page, the redirect URL is almost always **missing from the allow list** above — add `/auth/callback.html` and save.

Users sign in via `/login.html` or `/signup.html`; local user rows are created on `POST /api/v1/auth/sync`.

## Google OAuth (Supabase)

Google sign-in is handled by **Supabase Auth** (no Google client secret in the HerbaGraph API).

### 1. Google Cloud Console

1. [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials
2. Create **OAuth 2.0 Client ID** (Web application)
3. Authorized JavaScript origins:
   - `https://yourdomain.com`
   - `https://YOUR_PROJECT.supabase.co`
4. Authorized redirect URIs:
   - `https://YOUR_PROJECT.supabase.co/auth/v1/callback`
5. Copy **Client ID** and **Client Secret**

### 2. Supabase Dashboard

1. Authentication → Providers → **Google** → Enable
2. Paste Google Client ID and Client Secret
3. Save

### 3. HerbaGraph env vars (Railway web service)

```env
AUTH_PROVIDER=supabase
GOOGLE_OAUTH_ENABLED=true
APP_PUBLIC_URL=https://www.herbagraph.com
```

Redeploy the web service. The login and signup pages show **Continue with Google** when `google_oauth_enabled` is true in `/api/v1/auth/config`.

### Private preview + Google signup

When `SIGNUP_ACCESS_CODE` is set, users must enter a valid access code on the signup page before **Continue with Google**. The frontend exchanges the code for a short-lived approval token (`POST /api/v1/auth/verify-access-code`) and sends it on the first `/auth/sync` after OAuth.

## Admin console (password-protected)

Set both `ADMIN_EMAILS` and `ADMIN_MASTER_PASSWORD` on web + worker services.

1. Ensure at least one HerbaGraph account exists whose email is in `ADMIN_EMAILS` (sign up at `/signup.html` if needed).
2. Open **https://yourdomain.com/admin/login.html** and enter `ADMIN_MASTER_PASSWORD`.
3. After unlock, use the operator console:

| URL | Purpose |
|-----|---------|
| `/admin/` | Hub — health check, links to tools |
| `/admin/users.html` | List, activate, verify, role, delete users |
| `/admin/validation.html` | Clinician feedback and validation analytics |

The master token is stored in `sessionStorage` (12h JWT). Sign out clears it. Operators with an `ADMIN_EMAILS` account can also use their normal Supabase session on admin pages.

Generate secrets locally:

```bash
bash scripts/generate_production_secrets.sh
```

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
- Restrict `ADMIN_EMAILS` to trusted operators; use a strong unique `ADMIN_MASTER_PASSWORD`
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
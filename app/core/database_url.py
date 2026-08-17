"""Normalize DATABASE_URL for SQLAlchemy + asyncpg (Supabase, Railway, local)."""

from __future__ import annotations

import ssl
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse


def _relaxed_ssl_context() -> ssl.SSLContext:
    """TLS without cert verification — required for Supabase pooler on many PaaS hosts."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _is_local_host(host: str) -> bool:
    return host in ("localhost", "127.0.0.1", "db") or host.endswith(".internal")


def is_supabase_direct_host(host: str | None) -> bool:
    """Supabase direct host (db.*.supabase.co) is IPv6-only — breaks many PaaS hosts."""
    return bool(host and host.startswith("db.") and host.endswith(".supabase.co"))


def prepare_asyncpg_url(url: str) -> tuple[str, dict]:
    """Return (clean_sqlalchemy_url, connect_args) for create_async_engine."""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    query = parse_qs(parsed.query)

    connect_args: dict = {}
    ssl_requested = False
    for key in list(query.keys()):
        if key in ("ssl", "sslmode"):
            val = (query.pop(key)[0] or "").lower()
            if val in {"require", "true", "1", "verify-full", "verify-ca", "prefer"}:
                ssl_requested = True

    remote = host and not _is_local_host(host)
    use_ssl = remote and (
        ssl_requested or "supabase.co" in host or "pooler.supabase.com" in host or "rlwy.net" in host
    )
    if use_ssl:
        connect_args["ssl"] = _relaxed_ssl_context()

    # Drop URL query params for remote hosts so SQLAlchemy/asyncpg cannot re-enable cert verify.
    clean_query = "" if use_ssl else urlencode({k: v[0] for k, v in query.items()})
    clean_url = urlunparse(parsed._replace(query=clean_query))
    return clean_url, connect_args


def validate_production_database_url(url: str, *, railway: bool) -> str | None:
    """Return an error message if the URL is unsuitable for production, else None."""
    host = urlparse(url).hostname or ""
    # Railway private DNS (*.railway.internal) is valid UAT/prod mesh, not loopback.
    if railway and host in {"localhost", "127.0.0.1"}:
        return "DATABASE_URL points at localhost. Use Supabase Session pooler or Railway Postgres."
    if railway and is_supabase_direct_host(host):
        return (
            "DATABASE_URL uses Supabase DIRECT host (db.*.supabase.co), which is IPv6-only. "
            "In Supabase → Settings → Database → Connection string, choose URI + Session pooler (port 6543)."
        )
    return None
import ssl

from app.config import Settings
from app.core.database_url import (
    is_supabase_direct_host,
    prepare_asyncpg_url,
    validate_production_database_url,
)


def test_prepare_asyncpg_enables_ssl_for_supabase_pooler():
    url = "postgresql+asyncpg://postgres.ref:pass@aws-0-us-east-1.pooler.supabase.com:6543/postgres"
    clean, args = prepare_asyncpg_url(url)
    assert isinstance(args["ssl"], ssl.SSLContext)
    assert args["ssl"].verify_mode == ssl.CERT_NONE
    assert clean.startswith("postgresql+asyncpg://")


def test_prepare_asyncpg_strips_sslmode_query_param():
    url = (
        "postgresql+asyncpg://postgres.ref:pass@aws-0-us-east-1.pooler.supabase.com:6543/postgres"
        "?sslmode=require"
    )
    clean, args = prepare_asyncpg_url(url)
    assert "sslmode" not in clean
    assert "ssl" in args


def test_prepare_asyncpg_skips_ssl_for_local():
    url = "postgresql+asyncpg://herbagraph:herbagraph@db:5432/herbagraph"
    _, args = prepare_asyncpg_url(url)
    assert "ssl" not in args


def test_validate_allows_railway_private_postgres():
    url = "postgresql+asyncpg://postgres:pass@postgres.railway.internal:5432/railway"
    assert validate_production_database_url(url, railway=True) is None


def test_validate_rejects_supabase_direct_on_railway():
    url = "postgresql+asyncpg://postgres:pass@db.abcdef.supabase.co:5432/postgres"
    err = validate_production_database_url(url, railway=True)
    assert err is not None
    assert "Session pooler" in err


def test_is_supabase_direct_host():
    assert is_supabase_direct_host("db.abcdef.supabase.co")
    assert not is_supabase_direct_host("aws-0-us-east-1.pooler.supabase.com")


def test_settings_normalizes_postgresql_prefix_only():
    settings = Settings(database_url="postgresql://user:pass@host:5432/db")
    assert settings.database_url == "postgresql+asyncpg://user:pass@host:5432/db"
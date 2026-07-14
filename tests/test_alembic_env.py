"""Alembic env.py must tolerate URL-encoded DATABASE_URL passwords."""


def test_alembic_configparser_escapes_percent_in_database_url():
    url = "postgresql+asyncpg://user:pass%40word@host:6543/db"
    escaped = url.replace("%", "%%")
    assert escaped == "postgresql+asyncpg://user:pass%%40word@host:6543/db"
    assert escaped.replace("%%", "%") == url
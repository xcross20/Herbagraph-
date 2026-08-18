from app.discovery.schema_ready import public_schema_error


def test_public_schema_error_hides_sqlalchemy_trace():
    raw = (
        "(sqlalchemy.dialects.postgresql.asyncpg.ProgrammingError) "
        "<class 'asyncpg.exceptions.UndefinedColumnError'>: "
        "column discovery_findings.active does not exist"
    )
    message = public_schema_error(Exception(raw))
    assert "sqlalchemy" not in message.lower()
    assert "does not exist" not in message.lower()
    assert "alembic upgrade head" in message

from app.core.runtime_env import is_production, runtime_environment


def test_runtime_environment_prefers_app_env(monkeypatch):
    monkeypatch.setenv("APP_ENV", "uat")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "production")
    assert runtime_environment() == "uat"


def test_runtime_environment_uses_railway_name(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("HERBAGRAPH_ENV", raising=False)
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "pr-12")
    assert runtime_environment() == "pr-12"


def test_is_production_false_on_uat(monkeypatch):
    monkeypatch.setenv("APP_ENV", "uat")
    assert is_production() is False


def test_is_production_true(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    assert is_production() is True

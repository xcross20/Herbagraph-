from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://herbagraph:herbagraph@localhost:5432/herbagraph"
    secret_key: str = "insecure-dev-secret-key-change-me-in-production"
    encryption_key: str = ""
    openai_api_key: str = ""
    llm_model: str = "gpt-4o"
    redis_url: str = "redis://localhost:6379/0"
    ncbi_api_key: str = ""
    ncbi_email: str = "dev@herbagraph.io"
    upload_dir: str = "/tmp/herbagraph/uploads"
    max_file_size_mb: int = 10
    debug: bool = False
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30
    algorithm: str = "HS256"
    deidentify_before_llm: bool = True

    # Pluggable auth (Phase 3 infrastructure). Default "local" is the built-in JWT +
    # bcrypt implementation and is fully functional/tested with no external account.
    # "clerk"/"firebase" are documented integration points, not implemented yet --
    # see app/core/auth_providers.py.
    auth_provider: str = "local"
    clerk_secret_key: str = ""
    firebase_project_id: str = ""
    # Comma-separated admin emails allowed to access /admin/validation dashboard APIs.
    admin_emails: str = ""

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

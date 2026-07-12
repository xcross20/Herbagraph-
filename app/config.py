from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://herbagraph:herbagraph@localhost:5432/herbagraph"
    secret_key: str = "insecure-dev-secret-key-change-me-in-production"
    encryption_key: str = ""
    openai_api_key: str = ""
    # LLM provider: "openai" or "minimax" (MiniMax uses an OpenAI-compatible API).
    llm_provider: str = "openai"
    minimax_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = "gpt-4o"
    # Optional override for PDF vision parsing (MiniMax-M3 supports images; M2.x is text-only).
    llm_vision_model: str = ""
    # Low temperature keeps structured JSON stable across OpenAI and MiniMax.
    llm_temperature: float = 0.0
    # Anchor LLM recommendations to deterministic catalog evidence (reduces provider variance).
    llm_stabilize_reasoning: bool = True
    redis_url: str = "redis://localhost:6379/0"
    ncbi_api_key: str = ""
    ncbi_email: str = "dev@herbagraph.io"
    upload_dir: str = "/tmp/herbagraph/uploads"
    max_file_size_mb: int = 10
    debug: bool = False
    # Comma-separated allowed browser origins when DEBUG=false (e.g. https://app.herbagraph.com)
    cors_origins: str = ""
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30
    algorithm: str = "HS256"
    deidentify_before_llm: bool = True

    # Auth provider: "local" (bcrypt JWT) or "supabase" (Supabase Auth JWT).
    auth_provider: str = "local"
    require_email_verification: bool = False
    allow_guest_auth: bool = True
    # Supabase — set all three when AUTH_PROVIDER=supabase
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_publishable_key: str = ""
    supabase_jwt_secret: str = ""
    # Legacy stubs (not implemented)
    clerk_secret_key: str = ""
    firebase_project_id: str = ""
    # Comma-separated admin emails for /admin/ console APIs.
    admin_emails: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        if self.debug:
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

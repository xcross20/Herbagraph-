from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://herbagraph:herbagraph@localhost:5432/herbagraph"

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        """Railway/Render often provide postgresql:// — SQLAlchemy async needs +asyncpg."""
        if not isinstance(value, str):
            return value
        if value.startswith("postgresql://"):
            value = "postgresql+asyncpg://" + value[len("postgresql://") :]
        return value
    secret_key: str = "insecure-dev-secret-key-change-me-in-production"
    encryption_key: str = ""
    openai_api_key: str = ""
    # LLM provider: "openai" or "minimax" (MiniMax uses an OpenAI-compatible API).
    llm_provider: str = "openai"
    minimax_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = "gpt-4o"
    # Secondary provider when primary hits context/token/rate limits (empty = auto if both keys set).
    llm_fallback_provider: str = ""
    llm_fallback_model: str = ""
    # Optional override for PDF vision parsing (MiniMax-M3 supports images; M2.x is text-only).
    llm_vision_model: str = ""
    # Low temperature keeps structured JSON stable across OpenAI and MiniMax.
    llm_temperature: float = 0.0
    # Anchor LLM recommendations to deterministic catalog evidence (reduces provider variance).
    llm_stabilize_reasoning: bool = True
    redis_url: str = "redis://localhost:6379/0"
    ncbi_api_key: str = ""
    ncbi_email: str = "dev@herbagraph.io"
    # USDA FoodData Central — free key at https://fdc.nal.usda.gov/api-key-signup.html
    usda_key: str = ""
    upload_dir: str = "/tmp/herbagraph/uploads"
    # auto = database on Railway (web/worker share Postgres), disk locally
    file_storage_backend: str = "auto"
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
    # Ephemeral guest accounts (local auth only). Default off — IMP-002 registered sessions.
    # Set ALLOW_GUEST_AUTH=true only for local/UI smoke demos; never in production.
    allow_guest_auth: bool = False
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
    # Master password for /admin/ console (production). Required with ADMIN_EMAILS for full access.
    admin_master_password: str = ""
    # Private preview: require matching code on signup (set SIGNUP_ACCESS_CODE in production).
    signup_access_code: str = "19922026"
    # Google OAuth via Supabase Auth (enable in Supabase Dashboard + set GOOGLE_OAUTH_ENABLED=true).
    google_oauth_enabled: bool = False
    # Public site URL for OAuth redirect documentation (e.g. https://www.herbagraph.com).
    app_public_url: str = ""
    # Discovery investigation graph. Additive; legacy rebuild remains as cache.
    discovery_guide_enabled: bool = True
    discovery_investigation_state_v2: bool = False
    discovery_coverage_graph_enabled: bool = False
    discovery_append_only_findings: bool = False
    discovery_document_reconciliation: bool = False
    discovery_voice_enabled: bool = False
    discovery_intervention_ledger: bool = False

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

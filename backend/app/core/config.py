from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    app_name: str = "Flexa API"
    environment: str = "development"
    # Pooled Neon URL (PgBouncer) for application traffic.
    database_url: str = "postgresql+psycopg://flexa:flexa@localhost:5432/flexa"
    # Direct (non-pooled) Neon URL for migrations; falls back to database_url.
    database_url_unpooled: str | None = None
    # Comma-separated list of allowed browser origins.
    frontend_url: str = "http://localhost:3000"

    # Later files win: the repo-root .env is written by `neon env pull` / `neon deploy`,
    # so Neon-managed vars there override backend/.env. Real env vars beat both.
    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR / ".env", REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("database_url", "database_url_unpooled")
    @classmethod
    def use_psycopg_driver(cls, value: str | None) -> str | None:
        # Managed providers (Render, Neon, Supabase) hand out postgres:// URLs.
        if value is None:
            return None
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value.removeprefix(prefix)
        return value

    @property
    def migration_database_url(self) -> str:
        return self.database_url_unpooled or self.database_url

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_url.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

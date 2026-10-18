"""Runtime settings, read from environment variables (or a .env file)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent
DEV_SECRET_KEY = "dev-only-insecure-secret-key-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENVIRONMENT: Literal["development", "test", "production"] = "development"

    # One plain DSN; the async and sync driver variants are derived from it.
    DATABASE_URL: str = "postgresql://logitrack:logitrack@localhost:5432/logitrack"

    SECRET_KEY: str = DEV_SECRET_KEY
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, gt=0)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, gt=0)
    LOGIN_RATE_LIMIT: str = "5/minute"

    CORS_ORIGINS: str = "http://localhost:5173"

    DATA_DIR: Path = BACKEND_ROOT.parent / "data" / "raw"
    MODEL_DIR: Path = BACKEND_ROOT / "artifacts"

    # Password for the seeded demo accounts (admin/analyst/viewer@logitrack.dev).
    DEMO_PASSWORD: str = "logitrack-demo"

    @model_validator(mode="after")
    def _refuse_dev_secret_in_production(self) -> Settings:
        if self.ENVIRONMENT == "production" and self.SECRET_KEY == DEV_SECRET_KEY:
            raise ValueError("SECRET_KEY must be set explicitly in production.")
        return self

    @property
    def async_database_url(self) -> str:
        return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

    @property
    def sync_database_url(self) -> str:
        return self.DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

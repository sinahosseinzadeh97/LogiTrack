"""
Application configuration loaded from environment variables via pydantic-settings.

All secrets and connection strings are expected in a .env file at the project
root (or as real environment variables in production). Never commit .env.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central settings object for the LogiTrack backend.

    All values are read from environment variables (case-sensitive) or from a
    .env file located at the project root.  Defaults are provided only for
    non-secret, low-risk values.
    """

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    DATABASE_URL: str = Field(
        ...,
        description=(
            "Async PostgreSQL DSN used by SQLAlchemy / asyncpg at runtime. "
            "Format: postgresql+asyncpg://user:password@host:port/dbname"
        ),
    )
    DATABASE_SYNC_URL: str = Field(
        ...,
        description=(
            "Synchronous PostgreSQL DSN used by Alembic for migrations. "
            "Format: postgresql+psycopg2://user:password@host:port/dbname"
        ),
    )

    # ------------------------------------------------------------------
    # Security / Auth
    # ------------------------------------------------------------------
    SECRET_KEY: str = Field(
        ...,
        description="Random 32-byte hex string used to sign JWT tokens.",
    )
    ALGORITHM: str = Field(
        default="HS256",
        description="JWT signing algorithm.",
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30,
        gt=0,
        description="Lifetime of a short-lived access token in minutes.",
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        default=7,
        gt=0,
        description="Lifetime of a refresh token in days.",
    )

    # ------------------------------------------------------------------
    # Object Storage (MinIO / S3-compatible)
    # ------------------------------------------------------------------
    S3_ENDPOINT_URL: str = Field(
        ...,
        description="Full URL to the MinIO / S3 endpoint, e.g. http://minio:9000.",
    )
    S3_ACCESS_KEY: str = Field(..., description="MinIO root user or IAM access key.")
    S3_SECRET_KEY: str = Field(..., description="MinIO root password or IAM secret.")
    S3_BUCKET_NAME: str = Field(
        default="logitrack",
        description="Target bucket for model artefacts and processed exports.",
    )

    # ------------------------------------------------------------------
    # ML / Prediction
    # ------------------------------------------------------------------
    ALERT_THRESHOLD: float = Field(
        default=0.65,
        ge=0.0,
        le=1.0,
        description=(
            "Probability cutoff above which a shipment is flagged as at-risk "
            "of late delivery."
        ),
    )

    # ------------------------------------------------------------------
    # ETL / Data paths
    # ------------------------------------------------------------------
    DATA_RAW_PATH: str = Field(
        default="data/raw",
        description="Relative path (from project root) to the raw CSV directory.",
    )

    # ------------------------------------------------------------------
    # Runtime
    # ------------------------------------------------------------------
    ENVIRONMENT: str = Field(
        default="development",
        description="One of: development | staging | production.",
    )

    # ------------------------------------------------------------------
    # Rate limiting / caching
    # ------------------------------------------------------------------
    REDIS_URL: str | None = Field(
        default=None,
        description=(
            "Redis connection URL (e.g. redis://redis:6379/0).  "
            "When set, the rate-limiter and token-blacklist cache use Redis.  "
            "When unset, an in-memory store is used (single-process only)."
        ),
    )

    # ------------------------------------------------------------------
    # CORS
    # ------------------------------------------------------------------
    CORS_ORIGINS: str = Field(
        default="http://localhost:5173,http://localhost:3000",
        description=(
            "Comma-separated list of allowed CORS origins.  "
            "Use '*' to allow all (development only)."
        ),
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the singleton Settings instance (cached after first call).

    Using ``lru_cache`` ensures the .env file is read exactly once per process
    lifetime, which is the expected behaviour in both application code and tests
    (tests can clear the cache via ``get_settings.cache_clear()``).
    """
    return Settings()  # type: ignore[call-arg]

"""
Alembic environment configuration for LogiTrack.

This module wires the ``DATABASE_SYNC_URL`` from :mod:`app.config` into
Alembic so that the migration URL is never hardcoded in ``alembic.ini``.
Both online (live DB) and offline (SQL script generation) modes are supported.
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# ---------------------------------------------------------------------------
# Make the backend package importable from the alembic directory
# ---------------------------------------------------------------------------
# Alembic runs from backend/, so we add it to the path if needed.
_backend_root = Path(__file__).resolve().parent.parent
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))

from app.config import get_settings  # noqa: E402
from app.models import Base  # noqa: E402  — imports all ORM models for autogenerate
import app.auth.models  # noqa: E402, F401 — registers User + TokenBlacklist with Base.metadata

# ---------------------------------------------------------------------------
# Alembic Config object — gives access to values in alembic.ini
# ---------------------------------------------------------------------------
config = context.config

# Inject the sync URL from settings so alembic.ini never needs it
_settings = get_settings()
config.set_main_option("sqlalchemy.url", _settings.DATABASE_SYNC_URL)

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# MetaData object for autogenerate support
target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Migration helpers
# ---------------------------------------------------------------------------


def run_migrations_offline() -> None:
    """Run migrations in offline mode (emit SQL to stdout / file).

    Useful for generating migration scripts without a live database connection.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in online mode (apply directly to the target database)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

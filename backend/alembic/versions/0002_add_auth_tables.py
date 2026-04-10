"""Add users and token_blacklist tables.

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-09

Creates:
  - users              (id, email, hashed_password, full_name, role, is_active, created_at)
  - token_blacklist    (id, jti, blacklisted_at, token_hint)
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create auth tables using raw SQL to avoid SQLAlchemy enum type conflicts."""

    # Create the role enum type
    op.execute("CREATE TYPE userrole AS ENUM ('admin', 'analyst', 'viewer')")

    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE users (
            id          SERIAL PRIMARY KEY,
            email       VARCHAR(255) NOT NULL,
            hashed_password VARCHAR(255) NOT NULL,
            full_name   VARCHAR(255) NOT NULL,
            role        userrole NOT NULL DEFAULT 'viewer',
            is_active   BOOLEAN NOT NULL DEFAULT true,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_users_email UNIQUE (email)
        )
    """)
    op.execute("CREATE UNIQUE INDEX ix_users_email ON users (email)")

    # ------------------------------------------------------------------
    # token_blacklist
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE token_blacklist (
            id              SERIAL PRIMARY KEY,
            jti             VARCHAR(255) NOT NULL,
            blacklisted_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            token_hint      TEXT,
            CONSTRAINT uq_token_blacklist_jti UNIQUE (jti)
        )
    """)
    op.execute("CREATE UNIQUE INDEX ix_token_blacklist_jti ON token_blacklist (jti)")


def downgrade() -> None:
    """Drop auth tables and enum."""
    op.execute("DROP INDEX IF EXISTS ix_token_blacklist_jti")
    op.execute("DROP TABLE IF EXISTS token_blacklist")
    op.execute("DROP INDEX IF EXISTS ix_users_email")
    op.execute("DROP TABLE IF EXISTS users")
    op.execute("DROP TYPE IF EXISTS userrole")

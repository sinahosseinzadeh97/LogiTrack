"""Add reports_log table.

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-09

Creates:
  - reports_log  (id, week, generated_at, s3_path, status,
                  file_size_bytes, error_message)
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create reports_log table."""
    op.create_table(
        "reports_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("week", sa.String(length=10), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("s3_path", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.String(length=2000), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_reports_log_week",
        "reports_log",
        ["week"],
        unique=False,
        if_not_exists=True,
    )


def downgrade() -> None:
    """Drop reports_log table."""
    op.drop_index("ix_reports_log_week", table_name="reports_log", if_exists=True)
    op.drop_table("reports_log", if_exists=True)

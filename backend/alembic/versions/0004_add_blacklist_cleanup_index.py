"""Add index on token_blacklist.blacklisted_at for efficient cleanup queries.

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-09

Rationale:
  The daily cleanup job issues:
      DELETE FROM token_blacklist WHERE blacklisted_at < NOW() - INTERVAL '7 days'
  Without an index this is a full table scan.  At low volume it is negligible,
  but as the table grows the index prevents lock contention during the nightly job.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add index on token_blacklist.blacklisted_at."""
    op.create_index(
        "ix_token_blacklist_blacklisted_at",
        "token_blacklist",
        ["blacklisted_at"],
        unique=False,
        if_not_exists=True,
    )


def downgrade() -> None:
    """Drop the blacklisted_at index."""
    op.drop_index(
        "ix_token_blacklist_blacklisted_at",
        table_name="token_blacklist",
        if_exists=True,
    )

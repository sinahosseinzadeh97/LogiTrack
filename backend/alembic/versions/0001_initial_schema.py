"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-17 15:18:25.694839
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "revoked_tokens",
        sa.Column("jti", sa.String(length=36), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("jti"),
    )
    op.create_index(
        op.f("ix_revoked_tokens_expires_at"), "revoked_tokens", ["expires_at"], unique=False
    )
    op.create_table(
        "shipments",
        sa.Column("order_id", sa.String(length=32), nullable=False),
        sa.Column("order_status", sa.String(length=20), nullable=False),
        sa.Column("customer_id", sa.String(length=32), nullable=False),
        sa.Column("customer_state", sa.String(length=2), nullable=True),
        sa.Column("seller_id", sa.String(length=32), nullable=True),
        sa.Column("seller_state", sa.String(length=2), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("purchase_ts", sa.DateTime(), nullable=False),
        sa.Column("approved_ts", sa.DateTime(), nullable=True),
        sa.Column("carrier_ts", sa.DateTime(), nullable=True),
        sa.Column("delivered_ts", sa.DateTime(), nullable=True),
        sa.Column("estimated_delivery", sa.Date(), nullable=True),
        sa.Column("n_items", sa.SmallInteger(), nullable=False),
        sa.Column("n_sellers", sa.SmallInteger(), nullable=False),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("freight_value", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("weight_g", sa.Float(), nullable=True),
        sa.Column("distance_km", sa.Float(), nullable=True),
        sa.Column("review_score", sa.SmallInteger(), nullable=True),
        sa.Column("delay_days", sa.Integer(), nullable=True),
        sa.Column("is_late", sa.Boolean(), nullable=True),
        sa.Column("promised_days", sa.Float(), nullable=True),
        sa.Column("purchase_dow", sa.SmallInteger(), nullable=False),
        sa.Column("seller_prior_orders", sa.Integer(), nullable=False),
        sa.Column("seller_prior_late_rate", sa.Float(), nullable=True),
        sa.Column("network_late_rate_14d", sa.Float(), nullable=True),
        sa.Column("network_orders_7d", sa.Integer(), nullable=False),
        sa.Column("promise_gap_7d", sa.Float(), nullable=True),
        sa.Column("delay_probability", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("order_id"),
    )
    op.create_index("ix_shipments_customer_state", "shipments", ["customer_state"], unique=False)
    op.create_index("ix_shipments_delivered_ts", "shipments", ["delivered_ts"], unique=False)
    op.create_index("ix_shipments_purchase_ts", "shipments", ["purchase_ts"], unique=False)
    op.create_index("ix_shipments_seller_id", "shipments", ["seller_id"], unique=False)
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=100), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("role", sa.Enum("viewer", "analyst", "admin", name="user_role"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )


def downgrade() -> None:
    op.drop_table("users")
    op.drop_index("ix_shipments_seller_id", table_name="shipments")
    op.drop_index("ix_shipments_purchase_ts", table_name="shipments")
    op.drop_index("ix_shipments_delivered_ts", table_name="shipments")
    op.drop_index("ix_shipments_customer_state", table_name="shipments")
    op.drop_table("shipments")
    op.drop_index(op.f("ix_revoked_tokens_expires_at"), table_name="revoked_tokens")
    op.drop_table("revoked_tokens")
    sa.Enum(name="user_role").drop(op.get_bind(), checkfirst=True)

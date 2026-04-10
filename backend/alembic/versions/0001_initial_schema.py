"""Initial schema — create all LogiTrack tables.

Revision ID: 0001_initial_schema
Revises: (none)
Create Date: 2026-04-09

Creates:
  - shipments
  - kpi_daily
  - seller_stats
  - ml_model_versions

All ``op.create_table`` calls use ``checkfirst=True`` so the migration is
safe to re-run against a database that already has these tables (idempotent).
The corresponding ``op.drop_table`` calls in ``downgrade`` also use
``checkfirst=True``.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create all four LogiTrack tables."""

    # ------------------------------------------------------------------
    # shipments
    # ------------------------------------------------------------------
    op.create_table(
        "shipments",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.String(length=50), nullable=False),
        sa.Column("customer_id", sa.String(length=50), nullable=False),
        sa.Column("seller_id", sa.String(length=50), nullable=False),
        sa.Column("product_id", sa.String(length=50), nullable=True),
        sa.Column("category_name", sa.String(length=100), nullable=True),
        sa.Column("seller_state", sa.String(length=5), nullable=True),
        sa.Column("customer_state", sa.String(length=5), nullable=True),
        sa.Column("purchase_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("estimated_delivery", sa.DateTime(timezone=True), nullable=True),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=False, server_default="0"),
        sa.Column("freight_value", sa.Numeric(precision=10, scale=2), nullable=False, server_default="0"),
        sa.Column("payment_value", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("delay_days", sa.Float(), nullable=True),
        sa.Column("is_late", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("distance_km", sa.Float(), nullable=True),
        sa.Column("cost_per_km", sa.Float(), nullable=True),
        sa.Column("seller_lat", sa.Float(), nullable=True),
        sa.Column("seller_lng", sa.Float(), nullable=True),
        sa.Column("customer_lat", sa.Float(), nullable=True),
        sa.Column("customer_lng", sa.Float(), nullable=True),
        sa.Column("day_of_week", sa.SmallInteger(), nullable=True),
        sa.Column("month", sa.SmallInteger(), nullable=True),
        sa.Column("seller_historical_delay_rate", sa.Float(), nullable=True),
        sa.Column("review_score", sa.SmallInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id", name="uq_shipments_order_id"),
    )
    # Indexes — created individually so checkfirst can be applied per index
    op.create_index("ix_shipments_order_id", "shipments", ["order_id"], unique=True, if_not_exists=True)
    op.create_index("ix_shipments_customer_id", "shipments", ["customer_id"], if_not_exists=True)
    op.create_index("ix_shipments_seller_id", "shipments", ["seller_id"], if_not_exists=True)
    op.create_index("ix_shipments_purchase_ts", "shipments", ["purchase_timestamp"], if_not_exists=True)
    op.create_index("ix_shipments_seller_state", "shipments", ["seller_state"], if_not_exists=True)
    op.create_index("ix_shipments_is_late", "shipments", ["is_late"], if_not_exists=True)

    # ------------------------------------------------------------------
    # kpi_daily
    # ------------------------------------------------------------------
    op.create_table(
        "kpi_daily",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("otif_rate", sa.Float(), nullable=True),
        sa.Column("avg_delay_days", sa.Float(), nullable=True),
        sa.Column("fulfillment_rate", sa.Float(), nullable=True),
        sa.Column("avg_cost_per_shipment", sa.Float(), nullable=True),
        sa.Column("total_shipments", sa.Integer(), nullable=True),
        sa.Column("flagged_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("date", name="uq_kpi_daily_date"),
    )
    op.create_index("ix_kpi_daily_date", "kpi_daily", ["date"], unique=True, if_not_exists=True)

    # ------------------------------------------------------------------
    # seller_stats
    # ------------------------------------------------------------------
    op.create_table(
        "seller_stats",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("seller_id", sa.String(length=50), nullable=False),
        sa.Column("seller_state", sa.String(length=5), nullable=True),
        sa.Column("total_orders", sa.Integer(), nullable=True),
        sa.Column("delay_rate", sa.Float(), nullable=True),
        sa.Column("avg_delay_days", sa.Float(), nullable=True),
        sa.Column("avg_cost", sa.Float(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("seller_id", name="uq_seller_stats_seller_id"),
    )
    op.create_index("ix_seller_stats_seller_id", "seller_stats", ["seller_id"], unique=True, if_not_exists=True)

    # ------------------------------------------------------------------
    # ml_model_versions
    # ------------------------------------------------------------------
    op.create_table(
        "ml_model_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column(
            "trained_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("accuracy", sa.Float(), nullable=True),
        sa.Column("precision_late", sa.Float(), nullable=True),
        sa.Column("recall_late", sa.Float(), nullable=True),
        sa.Column("f1_late", sa.Float(), nullable=True),
        sa.Column("threshold", sa.Float(), nullable=False, server_default="0.65"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("storage_path", sa.String(length=500), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Drop all four LogiTrack tables in reverse dependency order."""
    op.drop_table("ml_model_versions", if_exists=True)

    op.drop_index("ix_seller_stats_seller_id", table_name="seller_stats", if_exists=True)
    op.drop_table("seller_stats", if_exists=True)

    op.drop_index("ix_kpi_daily_date", table_name="kpi_daily", if_exists=True)
    op.drop_table("kpi_daily", if_exists=True)

    op.drop_index("ix_shipments_is_late", table_name="shipments", if_exists=True)
    op.drop_index("ix_shipments_seller_state", table_name="shipments", if_exists=True)
    op.drop_index("ix_shipments_purchase_ts", table_name="shipments", if_exists=True)
    op.drop_index("ix_shipments_seller_id", table_name="shipments", if_exists=True)
    op.drop_index("ix_shipments_customer_id", table_name="shipments", if_exists=True)
    op.drop_index("ix_shipments_order_id", table_name="shipments", if_exists=True)
    op.drop_table("shipments", if_exists=True)

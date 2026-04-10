"""
SQLAlchemy ORM models for LogiTrack.

Four tables are defined:
  - ``shipments``         — core fact table; one row per Olist order
  - ``kpi_daily``         — aggregated daily KPIs (OTIF, delay, fulfilment)
  - ``seller_stats``      — per-seller aggregates used by the ML feature store
  - ``ml_model_versions`` — registry of trained classifier checkpoints

All models share a common ``Base`` declarative base so that Alembic can
discover them through a single metadata object::

    from app.models import Base
    # Base.metadata contains all table definitions
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Shared declarative base for all LogiTrack ORM models."""


# ---------------------------------------------------------------------------
# shipments
# ---------------------------------------------------------------------------
class Shipment(Base):
    """Core fact table — one row per Olist order.

    Columns are populated by the ETL pipeline in three stages:
      1. ``clean.py``   — raw fields from CSV joins
      2. ``enrich.py``  — geo features, temporal flags, seller stats
      3. ``load.py``    — upserted via ``insert().on_conflict_do_update()``

    Indexes on ``order_id``, ``customer_id``, and ``seller_id`` support the
    most common API filter patterns.  ``purchase_timestamp`` is not indexed
    here because range scans on it are satisfied via the ``kpi_daily`` table.
    """

    __tablename__ = "shipments"

    # Primary key
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Domain identifiers
    order_id: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    customer_id: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    seller_id: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    product_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    category_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Geographic identifiers
    seller_state: Mapped[str | None] = mapped_column(String(5), nullable=True)
    customer_state: Mapped[str | None] = mapped_column(String(5), nullable=True)

    # Timestamps
    purchase_timestamp: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    delivered_timestamp: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    estimated_delivery: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Financials
    price: Mapped[Numeric] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )
    freight_value: Mapped[Numeric] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )
    payment_value: Mapped[Numeric | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )

    # Delay / performance
    delay_days: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_late: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Geo-enriched features
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_per_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    seller_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    seller_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    customer_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    customer_lng: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Temporal features
    day_of_week: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    month: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    # ML features
    seller_historical_delay_rate: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )

    # Review
    review_score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    # Audit
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_shipments_purchase_ts", "purchase_timestamp"),
        Index("ix_shipments_seller_state", "seller_state"),
        Index("ix_shipments_is_late", "is_late"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Shipment order_id={self.order_id!r} "
            f"is_late={self.is_late} delay_days={self.delay_days}>"
        )


# ---------------------------------------------------------------------------
# kpi_daily
# ---------------------------------------------------------------------------
class KpiDaily(Base):
    """Aggregated daily KPI snapshot computed by the ETL load step.

    One row per calendar date.  The ``updated_at`` column uses PostgreSQL's
    ``ON UPDATE`` equivalent via ``onupdate=func.now()`` so re-runs always
    record the last write time.
    """

    __tablename__ = "kpi_daily"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[Date] = mapped_column(Date, unique=True, nullable=False, index=True)

    # Core KPIs
    otif_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_delay_days: Mapped[float | None] = mapped_column(Float, nullable=True)
    fulfillment_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_cost_per_shipment: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_shipments: Mapped[int | None] = mapped_column(Integer, nullable=True)
    flagged_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (UniqueConstraint("date", name="uq_kpi_daily_date"),)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<KpiDaily date={self.date} otif={self.otif_rate:.3f} "
            f"shipments={self.total_shipments}>"
        )


# ---------------------------------------------------------------------------
# seller_stats
# ---------------------------------------------------------------------------
class SellerStats(Base):
    """Per-seller aggregate statistics refreshed on each ETL run.

    These stats are used as features in the delay-prediction model and are
    also surfaced in the Seller Performance view of the dashboard.
    """

    __tablename__ = "seller_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    seller_id: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    seller_state: Mapped[str | None] = mapped_column(String(5), nullable=True)

    # Volume
    total_orders: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Performance
    delay_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_delay_days: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_cost: Mapped[float | None] = mapped_column(Float, nullable=True)

    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<SellerStats seller_id={self.seller_id!r} "
            f"delay_rate={self.delay_rate}>"
        )


# ---------------------------------------------------------------------------
# ml_model_versions
# ---------------------------------------------------------------------------
class MlModelVersion(Base):
    """Registry of trained classifier versions.

    Only one row may have ``is_active=True`` at any time (enforced by
    application logic in the training pipeline, not a DB constraint, to avoid
    complex partial-index portability issues across environments).
    """

    __tablename__ = "ml_model_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    trained_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Evaluation metrics
    accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    precision_late: Mapped[float | None] = mapped_column(Float, nullable=True)
    recall_late: Mapped[float | None] = mapped_column(Float, nullable=True)
    f1_late: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Prediction configuration
    threshold: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.65
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # Artefact location (S3 key or local path)
    storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<MlModelVersion version={self.version!r} "
            f"is_active={self.is_active} f1={self.f1_late}>"
        )

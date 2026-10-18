"""ORM models for the analytics data. Auth tables live in ``app.auth.models``.

Olist timestamps are naive local time (America/Sao_Paulo) and are stored as-is.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, Index, Integer, Numeric, SmallInteger, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Shipment(Base):
    """One row per order, every status. Built by the ETL, scored by ``ml.train``.

    The ``seller_prior_*``, ``network_*`` and ``promise_gap_7d`` columns are
    point-in-time features: each uses only what was known before ``purchase_ts``.
    """

    __tablename__ = "shipments"

    order_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    order_status: Mapped[str] = mapped_column(String(20))
    customer_id: Mapped[str] = mapped_column(String(32))
    customer_state: Mapped[str | None] = mapped_column(String(2))
    seller_id: Mapped[str | None] = mapped_column(String(32))
    seller_state: Mapped[str | None] = mapped_column(String(2))
    category: Mapped[str | None] = mapped_column(String(64))

    purchase_ts: Mapped[datetime] = mapped_column(DateTime)
    approved_ts: Mapped[datetime | None] = mapped_column(DateTime)
    carrier_ts: Mapped[datetime | None] = mapped_column(DateTime)
    delivered_ts: Mapped[datetime | None] = mapped_column(DateTime)
    estimated_delivery: Mapped[date | None] = mapped_column(Date)

    n_items: Mapped[int] = mapped_column(SmallInteger)
    n_sellers: Mapped[int] = mapped_column(SmallInteger)
    price: Mapped[float] = mapped_column(Numeric(10, 2))
    freight_value: Mapped[float] = mapped_column(Numeric(10, 2))
    weight_g: Mapped[float | None] = mapped_column(Float)
    distance_km: Mapped[float | None] = mapped_column(Float)
    review_score: Mapped[int | None] = mapped_column(SmallInteger)

    # Outcome — NULL until the order is delivered.
    delay_days: Mapped[int | None] = mapped_column(Integer)
    is_late: Mapped[bool | None] = mapped_column(Boolean)

    # Features known at purchase time.
    promised_days: Mapped[float | None] = mapped_column(Float)
    purchase_dow: Mapped[int] = mapped_column(SmallInteger)
    seller_prior_orders: Mapped[int] = mapped_column(Integer)
    seller_prior_late_rate: Mapped[float | None] = mapped_column(Float)
    network_late_rate_14d: Mapped[float | None] = mapped_column(Float)
    network_orders_7d: Mapped[int] = mapped_column(Integer)
    promise_gap_7d: Mapped[float | None] = mapped_column(Float)

    # Written by the trained model (P(late) at purchase time).
    delay_probability: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (
        Index("ix_shipments_purchase_ts", "purchase_ts"),
        Index("ix_shipments_delivered_ts", "delivered_ts"),
        Index("ix_shipments_seller_id", "seller_id"),
        Index("ix_shipments_customer_state", "customer_state"),
    )

"""API response/request models (auth has its own in app/auth/schemas.py)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class KPISummary(BaseModel):
    total_orders: int
    delivered: int
    late: int
    on_time_rate: float | None = Field(
        description="% of delivered orders that arrived by the promised date"
    )
    fulfillment_rate: float | None = Field(description="% of orders that were delivered")
    avg_delay_days_late: float | None = Field(
        description="Mean days past the promise, late orders only"
    )
    avg_delivery_days: float | None
    avg_freight: float | None
    first_order: date | None
    last_order: date | None


class TrendPoint(BaseModel):
    period: date
    orders: int
    on_time_rate: float
    avg_delivery_days: float | None


class CategoryRow(BaseModel):
    category: str
    orders: int
    late_rate: float
    avg_delay_days_late: float | None


class RegionRow(BaseModel):
    state: str
    orders: int
    on_time_rate: float | None
    avg_delivery_days: float | None
    avg_freight: float | None
    avg_distance_km: float | None


class SellerRow(BaseModel):
    seller_id: str
    seller_state: str | None
    orders: int
    delivered: int
    late_rate: float | None
    avg_delay_days_late: float | None
    avg_freight: float | None


class SellerPage(BaseModel):
    items: list[SellerRow]
    total: int
    page: int
    page_size: int


class SellerDetail(SellerRow):
    trend: list[TrendPoint]


class ShipmentRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_id: str
    order_status: str
    seller_id: str | None
    seller_state: str | None
    customer_state: str | None
    category: str | None
    purchase_ts: datetime
    estimated_delivery: date | None
    delivered_ts: datetime | None
    price: float
    freight_value: float
    distance_km: float | None
    delay_days: int | None
    is_late: bool | None
    delay_probability: float | None


class ShipmentPage(BaseModel):
    items: list[ShipmentRow]
    total: int
    page: int
    page_size: int


class ShipmentDetail(ShipmentRow):
    customer_id: str
    approved_ts: datetime | None
    carrier_ts: datetime | None
    n_items: int
    weight_g: float | None
    review_score: int | None
    promised_days: float | None
    seller_prior_orders: int
    seller_prior_late_rate: float | None
    network_late_rate_14d: float | None
    network_orders_7d: int
    promise_gap_7d: float | None


class BacktestWindow(BaseModel):
    cutoff: date = Field(description="Model was trained on data before this date")
    min_date: date
    max_date: date
    default_as_of: date
    threshold: float


Outcome = Literal["late", "on_time", "not_delivered"]


class BacktestItem(BaseModel):
    order_id: str
    seller_id: str | None
    customer_state: str | None
    category: str | None
    purchase_ts: datetime
    estimated_delivery: date
    days_to_promise: int
    delay_probability: float
    risk: Literal["high", "medium"]
    outcome: Outcome
    delay_days: int | None


class BacktestStats(BaseModel):
    in_transit: int = Field(
        description="Bought, not yet delivered and not yet due on the as-of date"
    )
    overdue: int = Field(description="Already past their promised date on the as-of date")
    flagged: int
    flagged_late: int
    precision: float | None = Field(description="Share of flagged orders that turned out late")
    recall: float | None = Field(
        description="Share of the eventually-late orders that were flagged"
    )
    base_rate: float | None = Field(description="Late share among all in-transit orders")


class BacktestResponse(BaseModel):
    as_of: date
    threshold: float
    stats: BacktestStats
    items: list[BacktestItem]


class PredictRequest(BaseModel):
    """What-if inputs; anything omitted falls back to a typical value."""

    category: str | None = None
    seller_state: str | None = Field(default=None, min_length=2, max_length=2)
    customer_state: str | None = Field(default=None, min_length=2, max_length=2)
    promised_days: float | None = Field(default=None, ge=0, le=180)
    distance_km: float | None = Field(default=None, ge=0, le=5000)
    price: float | None = Field(default=None, ge=0, le=20000)
    freight_value: float | None = Field(default=None, ge=0, le=5000)
    weight_g: float | None = Field(default=None, ge=0, le=100000)
    n_items: float | None = Field(default=None, ge=1, le=50)
    purchase_dow: float | None = Field(default=None, ge=0, le=6)
    seller_prior_orders: float | None = Field(default=None, ge=0)
    seller_prior_late_rate: float | None = Field(default=None, ge=0, le=1)
    network_late_rate_14d: float | None = Field(default=None, ge=0, le=1)
    network_orders_7d: float | None = Field(default=None, ge=0)
    promise_gap_7d: float | None = Field(default=None, ge=-180, le=180)


class PredictResponse(BaseModel):
    delay_probability: float
    flagged: bool
    threshold: float
    base_rate: float
    inputs: dict[str, float | str | None]

"""
Pydantic v2 response schemas for the LogiTrack API.

These models are consumed by the FastAPI routers introduced in Phase 3.
They are defined here (in ``core``) so the KPI engine and the API layer
share the same contract without a circular import.

All field names match the keys returned by :mod:`core.kpi_engine` functions
so serialisation requires no manual mapping.

Naming conventions
------------------
- ``*Response`` — top-level response bodies (returned directly by route handlers).
- ``*Item``     — elements within a response list.
- ``Paginated*`` — paginated collection wrapper.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# KPI summary
# ---------------------------------------------------------------------------


class KPISummaryResponse(BaseModel):
    """Aggregated top-level KPIs for the dashboard overview card.

    Returned by ``GET /api/v1/kpi/summary``.
    """

    otif_rate: float = Field(
        ...,
        description="On-Time In-Full rate as a percentage [0, 100].",
        ge=0.0,
        le=100.0,
    )
    avg_delay_days: float = Field(
        ...,
        description=(
            "Mean delay in days for *late* orders only. "
            "Positive = delivered after estimated date."
        ),
    )
    fulfillment_rate: float = Field(
        ...,
        description="Percentage of all orders (any status) that reached 'delivered'.",
        ge=0.0,
        le=100.0,
    )
    avg_cost_per_shipment: float = Field(
        ...,
        description="Mean freight value per delivered order (BRL).",
        ge=0.0,
    )
    total_shipments: int = Field(
        ...,
        description="Total number of delivered shipments in the analysed window.",
        ge=0,
    )
    late_shipments: int = Field(
        ...,
        description="Number of delivered shipments that arrived late.",
        ge=0,
    )
    week_over_week_otif_delta: float | None = Field(
        default=None,
        description=(
            "OTIF rate of the current ISO week minus OTIF rate of the previous ISO week. "
            "Null when the dataset contains fewer than two weeks of data."
        ),
    )


# ---------------------------------------------------------------------------
# OTIF trend
# ---------------------------------------------------------------------------


class OTIFTrendPoint(BaseModel):
    """A single data-point in the weekly OTIF trend chart.

    Returned as a list by ``GET /api/v1/kpi/otif-trend``.
    """

    week_start: date = Field(
        ...,
        description="ISO date of the Monday that opens the week.",
    )
    otif_rate: float | None = Field(
        ...,
        description=(
            "OTIF percentage for this week [0, 100]. "
            "Null when no deliveries were recorded in this week."
        ),
    )


# ---------------------------------------------------------------------------
# Delay by category
# ---------------------------------------------------------------------------


class DelayByCategoryItem(BaseModel):
    """Per-category delay statistics row.

    Returned as a list by ``GET /api/v1/kpi/delay-by-category``.
    """

    category_name: str = Field(..., description="Olist product category (Portuguese).")
    avg_delay_days: float | None = Field(
        ...,
        description="Mean delay in days for late orders in this category.",
    )
    order_count: int = Field(
        ...,
        description="Total delivered orders in this category (late + on-time).",
        ge=0,
    )


# ---------------------------------------------------------------------------
# Seller scorecard
# ---------------------------------------------------------------------------


class SellerScorecardItem(BaseModel):
    """One row of the seller performance scorecard.

    Returned as a list by ``GET /api/v1/sellers/scorecard``.
    """

    seller_id: str = Field(..., description="Olist seller UUID (hashed).")
    seller_state: str = Field(..., description="Brazilian state code, e.g. 'SP'.")
    total_orders: int = Field(
        ...,
        description="Total delivered orders attributed to this seller.",
        ge=0,
    )
    delay_rate: float = Field(
        ...,
        description="Fraction of the seller's orders that arrived late [0, 1].",
        ge=0.0,
        le=1.0,
    )
    avg_delay_days: float | None = Field(
        ...,
        description="Mean delay in days for the seller's *late* orders only.",
    )
    avg_cost: float = Field(
        ...,
        description="Mean freight value across all delivered orders (BRL).",
        ge=0.0,
    )


# ---------------------------------------------------------------------------
# Shipment detail
# ---------------------------------------------------------------------------


class ShipmentDetail(BaseModel):
    """Full detail record for a single delivered shipment.

    Used in ``GET /api/v1/shipments/{order_id}`` and as the item type in
    :class:`PaginatedShipments`.
    """

    order_id: str = Field(..., description="Unique Olist order identifier.")
    seller_id: str = Field(..., description="Seller identifier.")
    seller_state: str = Field(..., description="Brazilian state where the seller is located.")
    customer_state: str = Field(..., description="Brazilian state where the customer is located.")
    distance_km: float | None = Field(
        default=None,
        description="Geodesic distance between seller and customer centroids (km).",
    )
    delay_days: float | None = Field(
        default=None,
        description=(
            "Signed delay relative to estimated delivery. "
            "Negative = early, positive = late."
        ),
    )
    is_late: bool = Field(..., description="True when the order arrived after the estimated date.")
    freight_value: float = Field(..., description="Freight charge in BRL.", ge=0.0)
    category_name: str | None = Field(
        default=None,
        description="Product category name (Portuguese), may be null for uncategorised items.",
    )
    purchase_timestamp: datetime = Field(..., description="UTC timestamp of order placement.")
    delivered_timestamp: datetime | None = Field(
        default=None,
        description="UTC timestamp of actual delivery. Null for undelivered orders.",
    )
    prediction_probability: float | None = Field(
        default=None,
        description=(
            "ML model's probability that this shipment will be late. "
            "Null when no active model version is loaded."
        ),
        ge=0.0,
        le=1.0,
    )


# ---------------------------------------------------------------------------
# Paginated shipment list
# ---------------------------------------------------------------------------


class PaginatedShipments(BaseModel):
    """Paginated wrapper for the shipments list endpoint.

    Returned by ``GET /api/v1/shipments`` with ``page`` / ``page_size`` query params.
    """

    items: list[ShipmentDetail] = Field(
        ...,
        description="Shipment records for the current page.",
    )
    total: int = Field(..., description="Total number of shipments matching the filter.", ge=0)
    page: int = Field(..., description="Current page number (1-indexed).", ge=1)
    page_size: int = Field(..., description="Number of items per page.", ge=1)
    total_pages: int = Field(
        ...,
        description="Ceiling of total / page_size.",
        ge=0,
    )

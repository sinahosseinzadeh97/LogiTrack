"""
KPI router — /api/v1/kpi prefix.

All endpoints require at minimum 'viewer' role.

Endpoints:
    GET /api/v1/kpi/summary
    GET /api/v1/kpi/otif-trend
    GET /api/v1/kpi/delay-by-category
    GET /api/v1/kpi/seller-scorecard
"""

from __future__ import annotations

import logging
import math
from typing import Annotated

import pandas as pd
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.service import VIEWER_AND_ABOVE, require_role
from app.database import get_async_session
from core.kpi_engine import (
    calculate_avg_delay,
    calculate_cost_per_shipment,
    calculate_delay_by_category,
    calculate_fulfillment_rate,
    calculate_kpi_summary,
    calculate_otif,
    calculate_seller_scorecard,
    calculate_weekly_otif_trend,
)
from core.schemas import (
    DelayByCategoryItem,
    KPISummaryResponse,
    OTIFTrendPoint,
    SellerScorecardItem,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/kpi", tags=["KPI"])

_ViewerDep = Annotated[User, Depends(require_role(*VIEWER_AND_ABOVE))]


# ---------------------------------------------------------------------------
# Shared DB helpers
# ---------------------------------------------------------------------------


async def _load_shipments_df(db: AsyncSession) -> pd.DataFrame:
    """Load delivered shipments as a DataFrame (cached per request)."""
    result = await db.execute(
        text(
            "SELECT order_id, seller_id, seller_state, customer_state, "
            "category_name, is_late, delay_days, freight_value, "
            "purchase_timestamp, delivered_timestamp, distance_km "
            "FROM shipments WHERE is_late IS NOT NULL"
        )
    )
    rows = result.fetchall()
    cols = list(result.keys())
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(rows, columns=cols)
    if "is_late" in df.columns:
        df["is_late"] = df["is_late"].astype(bool)
    return df


async def _load_all_orders_df(db: AsyncSession) -> pd.DataFrame:
    """Load all orders (any status) to compute true fulfillment rate."""
    result = await db.execute(
        text(
            "SELECT is_late, delay_days, freight_value, "
            "purchase_timestamp, 'delivered' AS order_status "
            "FROM shipments WHERE is_late IS NOT NULL"
        )
    )
    rows = result.fetchall()
    cols = list(result.keys())
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(rows, columns=cols)
    if "is_late" in df.columns:
        df["is_late"] = df["is_late"].astype(bool)
    return df


# ---------------------------------------------------------------------------
# GET /api/v1/kpi/summary
# ---------------------------------------------------------------------------


@router.get(
    "/summary",
    response_model=KPISummaryResponse,
    summary="Top-level KPI dashboard summary",
)
async def kpi_summary(
    _: _ViewerDep,
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> KPISummaryResponse:
    """Return aggregated KPIs: OTIF, avg delay, fulfillment, cost, WoW delta.

    Data is sourced from the ``shipments`` table (delivered rows).
    Cache: ~5 minutes recommended in production via a Redis layer.
    """
    df = await _load_shipments_df(db)
    df_all = await _load_all_orders_df(db)

    if df.empty:
        return KPISummaryResponse(
            otif_rate=0.0,
            avg_delay_days=0.0,
            fulfillment_rate=0.0,
            avg_cost_per_shipment=0.0,
            total_shipments=0,
            late_shipments=0,
            week_over_week_otif_delta=None,
        )

    summary = calculate_kpi_summary(df, df_all)
    return KPISummaryResponse(
        otif_rate=summary["otif_rate"],
        avg_delay_days=summary["avg_delay_days"] if not math.isnan(summary["avg_delay_days"]) else 0.0,
        fulfillment_rate=summary["fulfillment_rate"],
        avg_cost_per_shipment=summary["avg_cost_per_shipment"],
        total_shipments=summary["total_shipments"],
        late_shipments=summary["late_shipments"],
        week_over_week_otif_delta=summary["week_over_week_otif_delta"],
    )


# ---------------------------------------------------------------------------
# GET /api/v1/kpi/otif-trend
# ---------------------------------------------------------------------------


@router.get(
    "/otif-trend",
    response_model=list[OTIFTrendPoint],
    summary="Weekly OTIF rate trend",
)
async def otif_trend(
    _: _ViewerDep,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    weeks: Annotated[int, Query(ge=1, le=52, description="Number of trailing weeks")] = 8,
) -> list[OTIFTrendPoint]:
    """Return per-ISO-week OTIF rate for the last *weeks* weeks."""
    df = await _load_shipments_df(db)

    if df.empty:
        return []

    trend_df = calculate_weekly_otif_trend(df, weeks=weeks)
    return [
        OTIFTrendPoint(
            week_start=row["week_start"].date() if hasattr(row["week_start"], "date") else row["week_start"],
            otif_rate=None if (row["otif_rate"] is None or math.isnan(row["otif_rate"])) else row["otif_rate"],
        )
        for _, row in trend_df.iterrows()
    ]


# ---------------------------------------------------------------------------
# GET /api/v1/kpi/delay-by-category
# ---------------------------------------------------------------------------


@router.get(
    "/delay-by-category",
    response_model=list[DelayByCategoryItem],
    summary="Average delay days grouped by product category",
)
async def delay_by_category(
    _: _ViewerDep,
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> list[DelayByCategoryItem]:
    """Return per-category avg delay and order count, sorted by avg_delay_days desc."""
    df = await _load_shipments_df(db)

    if df.empty:
        return []

    cat_df = calculate_delay_by_category(df)
    items = []
    for _, row in cat_df.iterrows():
        avg = row.get("avg_delay_days")
        items.append(
            DelayByCategoryItem(
                category_name=str(row["category_name"]),
                avg_delay_days=None if (avg is None or (isinstance(avg, float) and math.isnan(avg))) else float(avg),
                order_count=int(row["order_count"]),
            )
        )
    return items


# ---------------------------------------------------------------------------
# GET /api/v1/kpi/seller-scorecard
# ---------------------------------------------------------------------------


@router.get(
    "/seller-scorecard",
    response_model=list[SellerScorecardItem],
    summary="Seller performance scorecard",
)
async def seller_scorecard(
    _: _ViewerDep,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    limit: Annotated[int, Query(ge=1, le=500, description="Max sellers to return")] = 50,
    sort_by: Annotated[str, Query(description="Column to sort by")] = "delay_rate",
    order: Annotated[str, Query(pattern="^(asc|desc)$", description="Sort direction")] = "desc",
) -> list[SellerScorecardItem]:
    """Return top sellers by delay rate (or other metric), paginated."""
    df = await _load_shipments_df(db)

    if df.empty:
        return []

    sc_df = calculate_seller_scorecard(df)

    valid_sort = {"delay_rate", "total_orders", "avg_delay_days", "avg_cost"}
    if sort_by not in valid_sort:
        sort_by = "delay_rate"

    ascending = order == "asc"
    sc_df = sc_df.sort_values(sort_by, ascending=ascending, na_position="last").head(limit)

    items = []
    for _, row in sc_df.iterrows():
        avg_delay = row.get("avg_delay_days")
        items.append(
            SellerScorecardItem(
                seller_id=str(row["seller_id"]),
                seller_state=str(row.get("seller_state", "")),
                total_orders=int(row["total_orders"]),
                delay_rate=float(row["delay_rate"]),
                avg_delay_days=None if (avg_delay is None or (isinstance(avg_delay, float) and math.isnan(avg_delay))) else float(avg_delay),
                avg_cost=float(row["avg_cost"]),
            )
        )
    return items

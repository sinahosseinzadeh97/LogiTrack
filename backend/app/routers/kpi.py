"""Headline KPIs, trend, and breakdowns by category and region — all aggregated in SQL."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.auth.service import ViewerUser
from app.routers.common import EndDate, Session, StartDate, purchase_window, rows
from app.schemas import CategoryRow, KPISummary, RegionRow, TrendPoint

router = APIRouter(prefix="/api/v1/kpi", tags=["kpi"])

MIN_PERIOD_ORDERS = 30  # hide weeks/months too small to read a rate from
MIN_CATEGORY_ORDERS = 100

ON_TIME_RATE = (
    "ROUND(100.0 * COUNT(*) FILTER (WHERE NOT is_late) / NULLIF(COUNT(is_late), 0), 2)::float"
)
DELIVERY_DAYS = (
    "ROUND((AVG(EXTRACT(EPOCH FROM delivered_ts - purchase_ts) / 86400)"
    " FILTER (WHERE is_late IS NOT NULL))::numeric, 2)::float"
)


@router.get("/summary", response_model=KPISummary)
async def summary(_: ViewerUser, db: Session, start: StartDate = None, end: EndDate = None) -> dict:
    where, params = purchase_window(start, end)
    [row] = await rows(
        db,
        f"""
        SELECT COUNT(*) AS total_orders,
               COUNT(is_late) AS delivered,
               COUNT(*) FILTER (WHERE is_late) AS late,
               {ON_TIME_RATE} AS on_time_rate,
               ROUND(100.0 * COUNT(is_late) / NULLIF(COUNT(*), 0), 2)::float AS fulfillment_rate,
               ROUND(AVG(delay_days) FILTER (WHERE is_late), 2)::float AS avg_delay_days_late,
               {DELIVERY_DAYS} AS avg_delivery_days,
               ROUND(AVG(freight_value), 2)::float AS avg_freight,
               MIN(purchase_ts)::date AS first_order,
               MAX(purchase_ts)::date AS last_order
        FROM shipments WHERE {where}""",
        params,
    )
    return row


@router.get("/trend", response_model=list[TrendPoint])
async def trend(
    _: ViewerUser,
    db: Session,
    start: StartDate = None,
    end: EndDate = None,
    granularity: Annotated[Literal["week", "month"], Query()] = "week",
) -> list[dict]:
    where, params = purchase_window(start, end)
    # granularity is validated by the Literal above, so it is safe to inline.
    return await rows(
        db,
        f"""
        SELECT DATE_TRUNC('{granularity}', purchase_ts)::date AS period,
               COUNT(is_late) AS orders,
               {ON_TIME_RATE} AS on_time_rate,
               {DELIVERY_DAYS} AS avg_delivery_days
        FROM shipments WHERE {where}
        GROUP BY 1 HAVING COUNT(is_late) >= {MIN_PERIOD_ORDERS}
        ORDER BY 1""",
        params,
    )


@router.get("/categories", response_model=list[CategoryRow])
async def categories(
    _: ViewerUser,
    db: Session,
    start: StartDate = None,
    end: EndDate = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> list[dict]:
    where, params = purchase_window(start, end)
    return await rows(
        db,
        f"""
        SELECT category,
               COUNT(is_late) AS orders,
               ROUND(AVG(is_late::int), 4)::float AS late_rate,
               ROUND(AVG(delay_days) FILTER (WHERE is_late), 2)::float AS avg_delay_days_late
        FROM shipments WHERE {where} AND category IS NOT NULL
        GROUP BY category HAVING COUNT(is_late) >= {MIN_CATEGORY_ORDERS}
        ORDER BY late_rate DESC LIMIT :limit""",
        {**params, "limit": limit},
    )


@router.get("/regions", response_model=list[RegionRow])
async def regions(
    _: ViewerUser, db: Session, start: StartDate = None, end: EndDate = None
) -> list[dict]:
    """Delivery performance by customer (destination) state."""
    where, params = purchase_window(start, end)
    return await rows(
        db,
        f"""
        SELECT customer_state AS state,
               COUNT(*) AS orders,
               {ON_TIME_RATE} AS on_time_rate,
               {DELIVERY_DAYS} AS avg_delivery_days,
               ROUND(AVG(freight_value), 2)::float AS avg_freight,
               ROUND(AVG(distance_km)::numeric, 1)::float AS avg_distance_km
        FROM shipments WHERE {where} AND customer_state IS NOT NULL
        GROUP BY customer_state ORDER BY orders DESC""",
        params,
    )

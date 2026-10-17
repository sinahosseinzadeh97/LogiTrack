"""Seller scorecard and per-seller detail."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, status

from app.auth.service import ViewerUser
from app.routers.common import EndDate, Page, PageSize, Session, StartDate, purchase_window, rows
from app.routers.kpi import DELIVERY_DAYS, ON_TIME_RATE
from app.schemas import SellerDetail, SellerPage

router = APIRouter(prefix="/api/v1/sellers", tags=["sellers"])

SELLER_STATS = """
    seller_id,
    MIN(seller_state) AS seller_state,
    COUNT(*) AS orders,
    COUNT(is_late) AS delivered,
    ROUND(AVG(is_late::int), 4)::float AS late_rate,
    ROUND(AVG(delay_days) FILTER (WHERE is_late), 2)::float AS avg_delay_days_late,
    ROUND(AVG(freight_value), 2)::float AS avg_freight
"""
SortKey = Literal["orders", "late_rate", "avg_delay_days_late", "avg_freight"]


@router.get("", response_model=SellerPage)
async def list_sellers(
    _: ViewerUser,
    db: Session,
    start: StartDate = None,
    end: EndDate = None,
    min_orders: Annotated[int, Query(ge=1, description="Minimum delivered orders")] = 20,
    sort: SortKey = "late_rate",
    order: Literal["asc", "desc"] = "desc",
    page: Page = 1,
    page_size: PageSize = 20,
) -> dict:
    where, params = purchase_window(start, end)
    # sort/order are Literal-validated, so inlining them is safe.
    items = await rows(
        db,
        f"""
        SELECT {SELLER_STATS}, COUNT(*) OVER () AS total
        FROM shipments WHERE {where} AND seller_id IS NOT NULL
        GROUP BY seller_id HAVING COUNT(is_late) >= :min_orders
        ORDER BY {sort} {order} NULLS LAST, seller_id
        LIMIT :limit OFFSET :offset""",
        {**params, "min_orders": min_orders, "limit": page_size, "offset": (page - 1) * page_size},
    )
    total = items[0]["total"] if items else 0
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/{seller_id}", response_model=SellerDetail)
async def get_seller(seller_id: str, _: ViewerUser, db: Session) -> dict:
    found = await rows(
        db,
        f"SELECT {SELLER_STATS} FROM shipments WHERE seller_id = :id GROUP BY seller_id",
        {"id": seller_id},
    )
    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Seller not found.")
    trend = await rows(
        db,
        f"""
        SELECT DATE_TRUNC('month', purchase_ts)::date AS period,
               COUNT(is_late) AS orders,
               {ON_TIME_RATE} AS on_time_rate,
               {DELIVERY_DAYS} AS avg_delivery_days
        FROM shipments WHERE seller_id = :id
        GROUP BY 1 HAVING COUNT(is_late) > 0 ORDER BY 1""",
        {"id": seller_id},
    )
    return {**found[0], "trend": trend}

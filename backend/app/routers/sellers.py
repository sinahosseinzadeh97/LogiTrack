"""
Sellers router — /api/v1/sellers prefix.

Endpoints:
    GET /api/v1/sellers/{seller_id}            — seller profile + trend
    GET /api/v1/sellers/{seller_id}/shipments  — paginated shipments for seller
"""

from __future__ import annotations

import logging
import math
from typing import Annotated

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.service import VIEWER_AND_ABOVE, require_role
from app.database import get_async_session
from app.models.shipment import SellerStats, Shipment
from core.kpi_engine import calculate_weekly_otif_trend
from core.schemas import OTIFTrendPoint, PaginatedShipments

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sellers", tags=["Sellers"])

_ViewerDep = Annotated[User, Depends(require_role(*VIEWER_AND_ABOVE))]


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class SellerProfile(BaseModel):
    seller_id: str
    seller_state: str | None = None
    total_orders: int
    delay_rate: float
    avg_delay_days: float | None = None
    avg_cost: float
    delay_trend_8w: list[OTIFTrendPoint] = Field(
        default_factory=list,
        description="Per-ISO-week OTIF rate for the last 8 weeks (seller-scoped).",
    )


# ---------------------------------------------------------------------------
# GET /api/v1/sellers/{seller_id}
# ---------------------------------------------------------------------------


@router.get(
    "/{seller_id}",
    response_model=SellerProfile,
    summary="Get full seller profile with 8-week delay trend",
)
async def get_seller(
    seller_id: str,
    _: _ViewerDep,
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> SellerProfile:
    """Return seller statistics from ``seller_stats`` + an 8-week OTIF trend."""
    # Fetch aggregate stats
    ss_result = await db.execute(
        select(SellerStats).where(SellerStats.seller_id == seller_id)
    )
    stats: SellerStats | None = ss_result.scalar_one_or_none()

    if stats is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Seller '{seller_id}' not found.",
        )

    # Load seller shipments for trend computation
    rows_result = await db.execute(
        select(Shipment).where(Shipment.seller_id == seller_id)
    )
    shipment_rows = rows_result.scalars().all()

    trend: list[OTIFTrendPoint] = []
    if shipment_rows:
        df = pd.DataFrame(
            [
                {
                    "is_late": r.is_late,
                    "delay_days": r.delay_days,
                    "freight_value": float(r.freight_value),
                    "purchase_timestamp": r.purchase_timestamp,
                }
                for r in shipment_rows
            ]
        )
        try:
            trend_df = calculate_weekly_otif_trend(df, weeks=8)
            trend = [
                OTIFTrendPoint(
                    week_start=row["week_start"].date() if hasattr(row["week_start"], "date") else row["week_start"],
                    otif_rate=None if (row["otif_rate"] is None or math.isnan(row["otif_rate"])) else row["otif_rate"],
                )
                for _, row in trend_df.iterrows()
            ]
        except ValueError:
            trend = []

    avg_delay = stats.avg_delay_days
    return SellerProfile(
        seller_id=stats.seller_id,
        seller_state=stats.seller_state,
        total_orders=stats.total_orders or 0,
        delay_rate=stats.delay_rate or 0.0,
        avg_delay_days=None if (avg_delay is None or (isinstance(avg_delay, float) and math.isnan(avg_delay))) else float(avg_delay),
        avg_cost=stats.avg_cost or 0.0,
        delay_trend_8w=trend,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/sellers/{seller_id}/shipments
# ---------------------------------------------------------------------------


@router.get(
    "/{seller_id}/shipments",
    response_model=PaginatedShipments,
    summary="Paginated shipments for a specific seller",
)
async def seller_shipments(
    seller_id: str,
    _: _ViewerDep,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    request: Request,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> PaginatedShipments:
    """Return paginated shipments scoped to a single seller."""
    from app.routers.shipments import _predict_prob, _shipment_to_detail

    base_q = select(Shipment).where(Shipment.seller_id == seller_id)

    count_result = await db.execute(select(func.count()).select_from(base_q.subquery()))
    total: int = count_result.scalar_one()

    if total == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No shipments found for seller '{seller_id}'.",
        )

    offset = (page - 1) * page_size
    rows = (
        await db.execute(
            base_q.order_by(Shipment.purchase_timestamp.desc()).offset(offset).limit(page_size)
        )
    ).scalars().all()

    bundle = getattr(request.app.state, "model_bundle", None)
    items = [_shipment_to_detail(r, _predict_prob(bundle, r)) for r in rows]
    total_pages = math.ceil(total / page_size)

    return PaginatedShipments(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )

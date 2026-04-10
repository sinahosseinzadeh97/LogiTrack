"""
Shipments router — /api/v1/shipments prefix.

Endpoints:
    GET /api/v1/shipments          — paginated list with filters
    GET /api/v1/shipments/export   — CSV download (analyst+)
    GET /api/v1/shipments/{order_id} — single shipment with ML probability
"""

from __future__ import annotations

import collections.abc
import csv
import io
import logging
import math
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import Integer, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.service import ANALYST_AND_ABOVE, VIEWER_AND_ABOVE, require_role
from app.database import get_async_session
from app.models.shipment import Shipment
from core.schemas import PaginatedShipments, ShipmentDetail

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/shipments", tags=["Shipments"])

_ViewerDep = Annotated[User, Depends(require_role(*VIEWER_AND_ABOVE))]
_AnalystDep = Annotated[User, Depends(require_role(*ANALYST_AND_ABOVE))]


# ---------------------------------------------------------------------------
# Shared filter builder
# ---------------------------------------------------------------------------


def _build_query(
    status_filter: str | None,
    state: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    search: str | None,
):
    """Return a SQLAlchemy select() for Shipment with optional filters applied."""
    q = select(Shipment)

    if status_filter is not None:
        is_late_val = status_filter.lower() == "late"
        q = q.where(Shipment.is_late == is_late_val)

    if state is not None:
        q = q.where(Shipment.seller_state == state.upper())

    if date_from is not None:
        q = q.where(Shipment.purchase_timestamp >= date_from)

    if date_to is not None:
        q = q.where(Shipment.purchase_timestamp <= date_to)

    if search is not None:
        pattern = f"%{search}%"
        q = q.where(
            Shipment.order_id.ilike(pattern) | Shipment.seller_id.ilike(pattern)
        )

    return q


def _shipment_to_detail(row: Shipment, prediction_probability: float | None = None) -> ShipmentDetail:
    """Convert a ``Shipment`` ORM row to the response schema."""
    return ShipmentDetail(
        order_id=row.order_id,
        seller_id=row.seller_id,
        seller_state=row.seller_state or "",
        customer_state=row.customer_state or "",
        distance_km=row.distance_km,
        delay_days=row.delay_days,
        is_late=row.is_late,
        freight_value=float(row.freight_value),
        category_name=row.category_name,
        purchase_timestamp=row.purchase_timestamp,  # type: ignore[arg-type]
        delivered_timestamp=row.delivered_timestamp,  # type: ignore[arg-type]
        prediction_probability=prediction_probability,
    )


def _get_model_bundle(request: Request) -> tuple | None:
    """Safely extract the model bundle from app.state (may be None)."""
    bundle = getattr(request.app.state, "model_bundle", None)
    if bundle is None:
        return None
    return bundle


def _predict_prob(bundle: tuple | None, row: Shipment) -> float | None:
    """Run single-row inference; return probability or None on any error."""
    if bundle is None:
        return None
    try:
        from ml.features import encode_single_row  # deferred import

        model, encoders, threshold = bundle
        row_dict = {
            "distance_km": row.distance_km,
            "seller_historical_delay_rate": row.seller_historical_delay_rate,
            "day_of_week": row.day_of_week,
            "month": row.month,
            "category_name": row.category_name,
            "seller_state": row.seller_state,
            "freight_value": float(row.freight_value) if row.freight_value else 0.0,
            "price": float(row.price) if row.price else 0.0,
        }
        X = encode_single_row(row_dict, encoders)
        prob = float(model.predict_proba(X)[:, 1][0])
        return prob
    except Exception as exc:  # noqa: BLE001
        logger.debug("Prediction failed for order %s: %s", row.order_id, exc)
        return None


# ---------------------------------------------------------------------------
# GET /api/v1/shipments
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=PaginatedShipments,
    summary="List shipments with optional filters",
)
async def list_shipments(
    _: _ViewerDep,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    request: Request,
    page: Annotated[int, Query(ge=1, description="Page number (1-indexed)")] = 1,
    page_size: Annotated[int, Query(ge=1, le=200, description="Items per page")] = 50,
    status_filter: Annotated[str | None, Query(alias="status", pattern="^(late|on_time)$")] = None,
    state: Annotated[str | None, Query(description="Seller state code, e.g. SP")] = None,
    date_from: Annotated[datetime | None, Query(description="Filter by purchase_timestamp >=)")] = None,
    date_to: Annotated[datetime | None, Query(description="Filter by purchase_timestamp <=")] = None,
    search: Annotated[str | None, Query(description="Partial match on order_id or seller_id")] = None,
) -> PaginatedShipments:
    """Return a paginated, filtered list of shipments.

    Does **not** load all rows into memory — uses ``COUNT`` + ``OFFSET/LIMIT``.
    """
    base_q = _build_query(status_filter, state, date_from, date_to, search)

    # Count total without loading rows
    count_q = select(func.count()).select_from(base_q.subquery())
    total: int = (await db.execute(count_q)).scalar_one()

    # Fetch page
    offset = (page - 1) * page_size
    rows_q = base_q.order_by(Shipment.purchase_timestamp.desc()).offset(offset).limit(page_size)
    rows = (await db.execute(rows_q)).scalars().all()

    bundle = _get_model_bundle(request)
    items = [_shipment_to_detail(r, _predict_prob(bundle, r)) for r in rows]
    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return PaginatedShipments(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/shipments/export
# ---------------------------------------------------------------------------


@router.get(
    "/export",
    summary="Export filtered shipments as CSV (analyst+)",
    response_class=StreamingResponse,
)
async def export_shipments(
    _: _AnalystDep,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    status_filter: Annotated[str | None, Query(alias="status", pattern="^(late|on_time)$")] = None,
    state: Annotated[str | None, Query()] = None,
    date_from: Annotated[datetime | None, Query()] = None,
    date_to: Annotated[datetime | None, Query()] = None,
    search: Annotated[str | None, Query()] = None,
) -> StreamingResponse:
    """Stream all matching shipments as a CSV file.  Requires analyst+ role."""
    base_q = _build_query(status_filter, state, date_from, date_to, search)
    rows = (await db.execute(base_q.order_by(Shipment.purchase_timestamp.desc()))).scalars().all()

    fieldnames = [
        "order_id", "seller_id", "seller_state", "customer_state",
        "category_name", "is_late", "delay_days", "freight_value",
        "distance_km", "purchase_timestamp", "delivered_timestamp",
    ]

    def _generate() -> collections.abc.Generator[str, None, None]:
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate()

        for row in rows:
            writer.writerow(
                {
                    "order_id": row.order_id,
                    "seller_id": row.seller_id,
                    "seller_state": row.seller_state or "",
                    "customer_state": row.customer_state or "",
                    "category_name": row.category_name or "",
                    "is_late": row.is_late,
                    "delay_days": row.delay_days,
                    "freight_value": float(row.freight_value),
                    "distance_km": row.distance_km,
                    "purchase_timestamp": row.purchase_timestamp,
                    "delivered_timestamp": row.delivered_timestamp,
                }
            )
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate()

    return StreamingResponse(
        _generate(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=shipments_export.csv"},
    )


# ---------------------------------------------------------------------------
# GET /api/v1/shipments/{order_id}
# ---------------------------------------------------------------------------


@router.get(
    "/{order_id}",
    response_model=ShipmentDetail,
    summary="Get a single shipment by order_id",
)
async def get_shipment(
    order_id: str,
    _: _ViewerDep,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    request: Request,
) -> ShipmentDetail:
    """Return full shipment detail including ML delay probability (if model active)."""
    result = await db.execute(select(Shipment).where(Shipment.order_id == order_id))
    row: Shipment | None = result.scalar_one_or_none()

    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Order '{order_id}' not found.")

    bundle = _get_model_bundle(request)
    prob = _predict_prob(bundle, row)
    return _shipment_to_detail(row, prob)

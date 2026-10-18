"""Browse, filter, export and inspect individual orders."""

from __future__ import annotations

import csv
import io
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import ColumnElement, Select, func, select

from app.auth.service import AnalystUser, ViewerUser
from app.database import get_engine
from app.models import Shipment
from app.routers.common import Page, PageSize, Session, start_of
from app.schemas import ShipmentDetail, ShipmentPage, ShipmentRow

router = APIRouter(prefix="/api/v1/shipments", tags=["shipments"])

LIST_COLUMNS = list(ShipmentRow.model_fields)
SORTABLE = {
    "purchase_ts": Shipment.purchase_ts,
    "delay_probability": Shipment.delay_probability,
    "delay_days": Shipment.delay_days,
}


@dataclass(frozen=True)
class ShipmentFilters:
    status: Annotated[str | None, Query(max_length=20)] = None
    customer_state: Annotated[str | None, Query(min_length=2, max_length=2)] = None
    seller_id: Annotated[str | None, Query(max_length=32)] = None
    category: Annotated[str | None, Query(max_length=64)] = None
    is_late: bool | None = None
    start: date | None = None
    end: date | None = None
    search: Annotated[str | None, Query(max_length=32, description="order_id prefix")] = None

    def conditions(self) -> list[ColumnElement[bool]]:
        c: list[ColumnElement[bool]] = []
        if self.status:
            c.append(Shipment.order_status == self.status)
        if self.customer_state:
            c.append(Shipment.customer_state == self.customer_state.upper())
        if self.seller_id:
            c.append(Shipment.seller_id == self.seller_id)
        if self.category:
            c.append(Shipment.category == self.category)
        if self.is_late is not None:
            c.append(Shipment.is_late.is_(self.is_late))
        if self.start:
            c.append(Shipment.purchase_ts >= start_of(self.start))
        if self.end:
            c.append(Shipment.purchase_ts < start_of(self.end + timedelta(days=1)))
        if self.search:
            c.append(Shipment.order_id.startswith(self.search.lower(), autoescape=True))
        return c


Filters = Annotated[ShipmentFilters, Depends()]


def _filtered(filters: ShipmentFilters) -> Select:
    return select(*(getattr(Shipment, c) for c in LIST_COLUMNS)).where(*filters.conditions())


@router.get("", response_model=ShipmentPage)
async def list_shipments(
    _: ViewerUser,
    db: Session,
    filters: Filters,
    sort: Literal["purchase_ts", "delay_probability", "delay_days"] = "purchase_ts",
    order: Literal["asc", "desc"] = "desc",
    page: Page = 1,
    page_size: PageSize = 25,
) -> dict:
    base = _filtered(filters)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    column = SORTABLE[sort]
    ordered = base.order_by(
        column.desc().nulls_last() if order == "desc" else column.asc().nulls_last(),
        Shipment.order_id,
    )
    result = await db.execute(ordered.limit(page_size).offset((page - 1) * page_size))
    return {"items": result.mappings().all(), "total": total, "page": page, "page_size": page_size}


@router.get("/export")
async def export_shipments(_: AnalystUser, filters: Filters) -> StreamingResponse:
    """Stream the filtered orders as CSV (analyst and admin only)."""
    query = _filtered(filters).order_by(Shipment.purchase_ts)

    async def lines() -> AsyncIterator[str]:
        # Own connection: the request-scoped session may be closed while the body streams.
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(LIST_COLUMNS)
        async with get_engine().connect() as conn:
            result = await conn.stream(query.execution_options(yield_per=2_000))
            async for partition in result.partitions():
                writer.writerows(partition)
                yield buffer.getvalue()
                buffer.seek(0)
                buffer.truncate()
        yield buffer.getvalue()

    headers = {"Content-Disposition": 'attachment; filename="shipments.csv"'}
    return StreamingResponse(lines(), media_type="text/csv", headers=headers)


@router.get("/{order_id}", response_model=ShipmentDetail)
async def get_shipment(order_id: str, _: ViewerUser, db: Session) -> Shipment:
    shipment = await db.get(Shipment, order_id)
    if shipment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found.")
    return shipment

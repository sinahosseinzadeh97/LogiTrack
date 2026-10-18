"""Small helpers shared by the routers."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Annotated, Any

from fastapi import Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session

Session = Annotated[AsyncSession, Depends(get_session)]
StartDate = Annotated[date | None, Query(description="First purchase date to include")]
EndDate = Annotated[date | None, Query(description="Last purchase date to include")]
Page = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]


def start_of(day: date) -> datetime:
    return datetime.combine(day, time.min)


def purchase_window(start: date | None, end: date | None) -> tuple[str, dict[str, Any]]:
    """SQL condition on purchase_ts for an inclusive [start, end] date range."""
    clauses, params = [], {}
    if start:
        clauses.append("purchase_ts >= :start")
        params["start"] = start_of(start)
    if end:
        clauses.append("purchase_ts < :end")
        params["end"] = start_of(end + timedelta(days=1))
    return " AND ".join(clauses) or "TRUE", params


async def rows(
    db: AsyncSession, sql: str, params: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    result = await db.execute(text(sql), params or {})
    return [dict(r) for r in result.mappings().all()]

"""Backtest of the at-risk queue: replay any day after the training cutoff.

For an as-of date D, the queue is every order that was bought before D, not
yet delivered, and not yet due. The model's score for each order only used
information from before its purchase, and we already know how each one
ended, so the response shows exactly how useful the alerts would have been.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.auth.service import ViewerUser
from app.routers.common import Session, rows, start_of
from app.routers.ml import LoadedModel, Model
from app.schemas import BacktestResponse, BacktestWindow

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])

LOOKBACK_DAYS = 60  # ignore orders stuck "in transit" for longer than this
HIGH_RISK = 0.5
DEFAULT_OFFSET = timedelta(days=42)

IN_QUEUE = """
    purchase_ts < :as_of AND purchase_ts >= :lookback
    AND order_status NOT IN ('canceled', 'unavailable')
    AND (delivered_ts IS NULL OR delivered_ts >= :as_of)
    AND delay_probability IS NOT NULL
    -- rows the model was trained on are excluded, so every score is out-of-sample
    AND NOT (purchase_ts < :cutoff AND estimated_delivery < :cutoff_date)
"""


def _cutoff(model: LoadedModel) -> date:
    return date.fromisoformat(model.card["cutoff"])


@router.get("/window", response_model=BacktestWindow)
async def window(_: ViewerUser, db: Session, model: Model) -> dict:
    cutoff = _cutoff(model)
    [bounds] = await rows(
        db, "SELECT MAX(purchase_ts)::date AS last FROM shipments WHERE is_late IS NOT NULL"
    )
    last = bounds["last"] or cutoff
    return {
        "cutoff": cutoff,
        "min_date": cutoff,
        "max_date": last,
        "default_as_of": min(cutoff + DEFAULT_OFFSET, last),
        "threshold": model.threshold,
    }


@router.get("", response_model=BacktestResponse)
async def backtest(
    _: ViewerUser,
    db: Session,
    model: Model,
    as_of: Annotated[date, Query(description="Replay the queue as of this morning")],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> dict:
    cutoff = _cutoff(model)
    if as_of < cutoff:
        # 422 as a literal: Starlette renamed its constant between versions.
        raise HTTPException(422, f"as_of must be on or after the training cutoff ({cutoff}).")
    params = {
        "as_of": start_of(as_of),
        "as_of_date": as_of,
        "lookback": start_of(as_of - timedelta(days=LOOKBACK_DAYS)),
        "cutoff": start_of(cutoff),
        "cutoff_date": cutoff,
        "threshold": model.threshold,
        "limit": limit,
    }
    # "Late" includes orders never delivered: they missed their promise too.
    [counts] = await rows(
        db,
        f"""
        WITH queue AS (
            SELECT estimated_delivery >= :as_of_date AS not_due,
                   delay_probability >= :threshold AS flagged,
                   is_late IS NOT FALSE AS missed
            FROM shipments WHERE {IN_QUEUE}
        )
        SELECT COUNT(*) FILTER (WHERE not_due) AS in_transit,
               COUNT(*) FILTER (WHERE NOT not_due) AS overdue,
               COUNT(*) FILTER (WHERE not_due AND flagged) AS flagged,
               COUNT(*) FILTER (WHERE not_due AND flagged AND missed) AS flagged_late,
               COUNT(*) FILTER (WHERE not_due AND missed) AS late
        FROM queue""",
        params,
    )
    items = await rows(
        db,
        f"""
        SELECT order_id, seller_id, customer_state, category, purchase_ts, estimated_delivery,
               estimated_delivery - :as_of_date AS days_to_promise,
               delay_probability,
               CASE WHEN delay_probability >= {HIGH_RISK} THEN 'high' ELSE 'medium' END AS risk,
               CASE WHEN is_late IS NULL THEN 'not_delivered'
                    WHEN is_late THEN 'late' ELSE 'on_time' END AS outcome,
               delay_days
        FROM shipments
        WHERE {IN_QUEUE} AND estimated_delivery >= :as_of_date AND delay_probability >= :threshold
        ORDER BY delay_probability DESC, order_id LIMIT :limit""",
        params,
    )

    flagged, in_transit = counts["flagged"], counts["in_transit"]
    stats = {
        "in_transit": in_transit,
        "overdue": counts["overdue"],
        "flagged": flagged,
        "flagged_late": counts["flagged_late"],
        "precision": counts["flagged_late"] / flagged if flagged else None,
        "recall": counts["flagged_late"] / counts["late"] if counts["late"] else None,
        "base_rate": counts["late"] / in_transit if in_transit else None,
    }
    return {"as_of": as_of, "threshold": model.threshold, "stats": stats, "items": items}

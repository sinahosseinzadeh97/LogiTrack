"""
Alerts router — /api/v1/alerts prefix.

Endpoints:
    GET  /api/v1/alerts         — flagged at-risk shipments (viewer+)
    GET  /api/v1/alerts/stats   — aggregate risk stats (viewer+)
    POST /api/v1/alerts/predict — single-row live inference (analyst+)
"""

from __future__ import annotations

import logging
import math
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.service import ANALYST_AND_ABOVE, VIEWER_AND_ABOVE, require_role
from app.database import get_async_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/alerts", tags=["Alerts"])

_ViewerDep = Annotated[User, Depends(require_role(*VIEWER_AND_ABOVE))]
_AnalystDep = Annotated[User, Depends(require_role(*ANALYST_AND_ABOVE))]


# ---------------------------------------------------------------------------
# Response schemas (local — not worth adding to core.schemas)
# ---------------------------------------------------------------------------


class FlaggedShipmentItem(BaseModel):
    order_id: str
    seller_id: str
    category_name: str | None = None
    seller_state: str | None = None
    customer_state: str | None = None
    distance_km: float | None = None
    delay_probability: float
    estimated_delivery: Any | None = None
    days_until_delivery: int | None = None


class AlertStatsResponse(BaseModel):
    total_flagged: int = Field(..., ge=0)
    high_risk: int = Field(..., ge=0, description="Probability > 0.8")
    medium_risk: int = Field(..., ge=0, description="Probability 0.65–0.8")
    avg_probability: float = Field(..., ge=0.0, le=1.0)


class PredictRequest(BaseModel):
    distance_km: float = Field(..., ge=0)
    category_name: str = Field(..., description="Product category (Portuguese)")
    seller_state: str = Field(..., description="Brazilian state code, e.g. SP")
    day_of_week: int = Field(..., ge=0, le=6, description="0=Mon … 6=Sun")
    freight_value: float = Field(..., ge=0)
    price: float = Field(..., ge=0)
    month: int = Field(default=1, ge=1, le=12)
    seller_historical_delay_rate: float = Field(default=0.1, ge=0.0, le=1.0)


class PredictResponse(BaseModel):
    delay_probability: float = Field(..., ge=0.0, le=1.0)
    predicted_late: bool
    risk_level: str = Field(..., description="high | medium | low")


# ---------------------------------------------------------------------------
# Helper: resolve model bundle
# ---------------------------------------------------------------------------


def _get_bundle(request: Request) -> tuple | None:
    return getattr(request.app.state, "model_bundle", None)


def _risk_level(prob: float) -> str:
    if prob > 0.8:
        return "high"
    if prob >= 0.65:
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# GET /api/v1/alerts
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=list[FlaggedShipmentItem],
    summary="List flagged at-risk shipments",
)
async def list_alerts(
    _: _ViewerDep,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    request: Request,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[FlaggedShipmentItem]:
    """Return at-risk in-transit shipments scored by the active ML model.

    Runs ``get_flagged_shipments`` on in-memory data loaded from the DB.
    Cache: 10 minutes recommended in production.
    """
    bundle = _get_bundle(request)
    if bundle is None:
        return []

    import pandas as pd
    from ml.predict import get_flagged_shipments

    model, encoders, threshold = bundle

    # Load active/in-transit-ish shipments — use shipments with no delivered_timestamp
    result = await db.execute(
        text(
            "SELECT order_id, seller_id, category_name, seller_state, customer_state, "
            "distance_km, seller_historical_delay_rate, day_of_week, month, "
            "freight_value, price, estimated_delivery "
            "FROM shipments WHERE delivered_timestamp IS NULL LIMIT 5000"
        )
    )
    rows = result.fetchall()
    if not rows:
        return []

    cols = list(result.keys())
    df = pd.DataFrame(rows, columns=cols)

    flagged = get_flagged_shipments(df, model, encoders, threshold).head(limit)

    items: list[FlaggedShipmentItem] = []
    for _, row in flagged.iterrows():
        days = row.get("days_until_delivery")
        items.append(
            FlaggedShipmentItem(
                order_id=str(row["order_id"]),
                seller_id=str(row["seller_id"]),
                category_name=row.get("category_name"),
                seller_state=row.get("seller_state"),
                customer_state=row.get("customer_state"),
                distance_km=row.get("distance_km"),
                delay_probability=float(row["delay_probability"]),
                estimated_delivery=row.get("estimated_delivery"),
                days_until_delivery=int(days) if days is not None and not (isinstance(days, float) and math.isnan(days)) else None,
            )
        )
    return items


# ---------------------------------------------------------------------------
# GET /api/v1/alerts/stats
# ---------------------------------------------------------------------------


@router.get(
    "/stats",
    response_model=AlertStatsResponse,
    summary="Aggregate risk statistics for flagged shipments",
)
async def alert_stats(
    _: _ViewerDep,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    request: Request,
) -> AlertStatsResponse:
    """Return counts for total_flagged, high_risk, medium_risk, and avg_probability."""
    bundle = _get_bundle(request)
    if bundle is None:
        return AlertStatsResponse(
            total_flagged=0, high_risk=0, medium_risk=0, avg_probability=0.0
        )

    import pandas as pd
    from ml.predict import get_flagged_shipments

    model, encoders, threshold = bundle

    result = await db.execute(
        text(
            "SELECT order_id, seller_id, category_name, seller_state, customer_state, "
            "distance_km, seller_historical_delay_rate, day_of_week, month, "
            "freight_value, price, estimated_delivery "
            "FROM shipments WHERE delivered_timestamp IS NULL LIMIT 5000"
        )
    )
    rows = result.fetchall()
    if not rows:
        return AlertStatsResponse(
            total_flagged=0, high_risk=0, medium_risk=0, avg_probability=0.0
        )

    cols = list(result.keys())
    df = pd.DataFrame(rows, columns=cols)
    flagged = get_flagged_shipments(df, model, encoders, threshold)

    if flagged.empty:
        return AlertStatsResponse(
            total_flagged=0, high_risk=0, medium_risk=0, avg_probability=0.0
        )

    probs = flagged["delay_probability"].astype(float)
    high_risk = int((probs > 0.8).sum())
    medium_risk = int(((probs >= 0.65) & (probs <= 0.8)).sum())

    return AlertStatsResponse(
        total_flagged=len(flagged),
        high_risk=high_risk,
        medium_risk=medium_risk,
        avg_probability=float(probs.mean()),
    )


# ---------------------------------------------------------------------------
# POST /api/v1/alerts/predict
# ---------------------------------------------------------------------------


@router.post(
    "/predict",
    response_model=PredictResponse,
    summary="Single-row live delay prediction (analyst+)",
)
async def predict(
    payload: PredictRequest,
    _: _AnalystDep,
    request: Request,
) -> PredictResponse:
    """Run live single-row inference. Requires **analyst** or **admin** role."""
    bundle = _get_bundle(request)
    if bundle is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No active ML model loaded. Run /api/v1/ml/retrain first.",
        )

    from ml.features import encode_single_row

    model, encoders, threshold = bundle

    row_dict = {
        "distance_km": payload.distance_km,
        "seller_historical_delay_rate": payload.seller_historical_delay_rate,
        "day_of_week": payload.day_of_week,
        "month": payload.month,
        "category_name": payload.category_name,
        "seller_state": payload.seller_state,
        "freight_value": payload.freight_value,
        "price": payload.price,
    }

    X = encode_single_row(row_dict, encoders)
    prob = float(model.predict_proba(X)[:, 1][0])
    predicted_late = prob >= threshold

    return PredictResponse(
        delay_probability=prob,
        predicted_late=predicted_late,
        risk_level=_risk_level(prob),
    )

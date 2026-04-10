"""
ML admin router — /api/v1/ml prefix.

All endpoints require 'admin' role.

Endpoints:
    GET  /api/v1/ml/model-info
    GET  /api/v1/ml/feature-importance
    POST /api/v1/ml/retrain
    GET  /api/v1/ml/retrain-status/{task_id}
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.service import ADMIN_ONLY, require_role
from app.database import get_async_session
from app.models.shipment import MlModelVersion

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ml", tags=["ML Admin"])

_AdminDep = Annotated[User, Depends(require_role(*ADMIN_ONLY))]

# In-memory task registry (per-process; sufficient for single-instance deployments)
_task_registry: dict[str, dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class ModelInfoResponse(BaseModel):
    id: int
    version: str
    trained_at: datetime
    accuracy: float | None = None
    precision_late: float | None = None
    recall_late: float | None = None
    f1_late: float | None = None
    threshold: float
    is_active: bool
    storage_path: str | None = None
    notes: str | None = None


class FeatureImportanceItem(BaseModel):
    feature: str
    importance: float


class RetrainResponse(BaseModel):
    message: str
    task_id: str


class RetrainStatusResponse(BaseModel):
    task_id: str
    status: str = Field(..., description="pending | running | done | failed")
    result: dict[str, Any] | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


# ---------------------------------------------------------------------------
# GET /api/v1/ml/model-info
# ---------------------------------------------------------------------------


@router.get(
    "/model-info",
    response_model=ModelInfoResponse,
    summary="Active ML model version info",
)
async def model_info(
    _: _AdminDep,
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> ModelInfoResponse:
    """Return metadata for the currently active model from ``ml_model_versions``."""
    result = await db.execute(
        select(MlModelVersion)
        .where(MlModelVersion.is_active.is_(True))
        .order_by(MlModelVersion.trained_at.desc())
        .limit(1)
    )
    model_version: MlModelVersion | None = result.scalar_one_or_none()

    if model_version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active model found. Run POST /api/v1/ml/retrain to train one.",
        )

    return ModelInfoResponse(
        id=model_version.id,
        version=model_version.version,
        trained_at=model_version.trained_at,  # type: ignore[arg-type]
        accuracy=model_version.accuracy,
        precision_late=model_version.precision_late,
        recall_late=model_version.recall_late,
        f1_late=model_version.f1_late,
        threshold=model_version.threshold,
        is_active=model_version.is_active,
        storage_path=model_version.storage_path,
        notes=model_version.notes,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/ml/feature-importance
# ---------------------------------------------------------------------------


@router.get(
    "/feature-importance",
    response_model=list[FeatureImportanceItem],
    summary="Feature importances from the active model",
)
async def feature_importance(
    _: _AdminDep,
    request: Request,
) -> list[FeatureImportanceItem]:
    """Return per-feature importances from the loaded RandomForest model.

    Reads from ``app.state.model_bundle`` (loaded at startup).
    """
    bundle = getattr(request.app.state, "model_bundle", None)
    if bundle is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No model loaded. Run POST /api/v1/ml/retrain first.",
        )

    from ml.features import FEATURE_COLUMNS  # deferred import

    model, _encoders, _threshold = bundle

    importances: list[float] = model.feature_importances_.tolist()
    pairs = sorted(
        zip(FEATURE_COLUMNS, importances, strict=True),
        key=lambda x: x[1],
        reverse=True,
    )

    return [FeatureImportanceItem(feature=f, importance=round(imp, 6)) for f, imp in pairs]


# ---------------------------------------------------------------------------
# POST /api/v1/ml/retrain
# ---------------------------------------------------------------------------


def _retrain_task(task_id: str, settings: Any, db_url: str) -> None:
    """Blocking retraining job — executed in a background thread by FastAPI."""
    import traceback

    from sqlalchemy import create_engine

    from ml.retrain import run_retrain_pipeline

    _task_registry[task_id]["status"] = "running"
    _task_registry[task_id]["started_at"] = datetime.now(tz=timezone.utc)

    try:
        engine = create_engine(db_url)
        result = run_retrain_pipeline(engine, settings)
        _task_registry[task_id]["status"] = "done"
        _task_registry[task_id]["result"] = result
    except Exception as exc:  # noqa: BLE001
        _task_registry[task_id]["status"] = "failed"
        _task_registry[task_id]["error"] = traceback.format_exc()
        logger.error("Retrain task %s failed: %s", task_id, exc)
    finally:
        _task_registry[task_id]["completed_at"] = datetime.now(tz=timezone.utc)


@router.post(
    "/retrain",
    response_model=RetrainResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger model retraining as background task (admin only)",
)
async def trigger_retrain(
    _: _AdminDep,
    background_tasks: BackgroundTasks,
    request: Request,
) -> RetrainResponse:
    """Kick off the full retraining pipeline asynchronously.

    Returns immediately with a ``task_id`` that can be polled via
    ``GET /api/v1/ml/retrain-status/{task_id}``.
    """
    from app.config import get_settings

    settings = get_settings()
    task_id = str(uuid.uuid4())
    _task_registry[task_id] = {
        "status": "pending",
        "result": None,
        "error": None,
        "started_at": None,
        "completed_at": None,
    }
    background_tasks.add_task(_retrain_task, task_id, settings, settings.DATABASE_SYNC_URL)
    logger.info("Retraining background task created: task_id=%s", task_id)
    return RetrainResponse(message="Retraining started", task_id=task_id)


# ---------------------------------------------------------------------------
# GET /api/v1/ml/retrain-status/{task_id}
# ---------------------------------------------------------------------------


@router.get(
    "/retrain-status/{task_id}",
    response_model=RetrainStatusResponse,
    summary="Poll the status of a retraining task",
)
async def retrain_status(
    task_id: str,
    _: _AdminDep,
) -> RetrainStatusResponse:
    """Return the current status of a retraining task by its ID."""
    entry = _task_registry.get(task_id)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' not found. IDs are only retained in the current process.",
        )
    return RetrainStatusResponse(task_id=task_id, **entry)

"""
LogiTrack FastAPI application entry point.

Startup responsibilities:
  1. Verify PostgreSQL connection
  2. Load active ML model into app.state
  3. Start APScheduler retraining job

Middleware:
  - CORS (origins from settings)
  - Request logging (method, path, status, latency)

Global exception handlers:
  - ValueError → 422
  - RuntimeError → 503
  - Catch-all → 500

Routes mounted:
  - /auth             → auth router
  - /api/v1/kpi       → kpi router
  - /api/v1/shipments → shipments router
  - /api/v1/alerts    → alerts router
  - /api/v1/sellers   → sellers router
  - /api/v1/ml        → ml router
  - /api/v1/reports   → reports router
  - /health           → inline health endpoint
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIASGIMiddleware
from sqlalchemy import delete, text

from app.auth.router import router as auth_router
from app.config import get_settings
from app.database import async_engine, sync_engine
from app.limiter import limiter
from app.routers.alerts import router as alerts_router
from app.routers.kpi import router as kpi_router
from app.routers.ml import router as ml_router
from app.routers.reports import router as reports_router
from app.routers.sellers import router as sellers_router
from app.routers.shipments import router as shipments_router

logger = logging.getLogger(__name__)

_START_TIME = time.time()


# ---------------------------------------------------------------------------
# Weekly report scheduler helper
# ---------------------------------------------------------------------------


def _schedule_weekly_report(db_engine: object) -> None:  # type: ignore[type-arg]
    """Register Monday-09:00-UTC APScheduler job to auto-generate the weekly PDF."""
    from datetime import date

    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    from sqlalchemy import create_engine as _ce

    from app.routers.reports import _run_report_generation
    from app.models.report_log import ReportLog
    from app.database import SyncSessionLocal

    def _job() -> None:
        logger.info("APScheduler: weekly report job triggered.")
        today = date.today()
        # Compute ISO week
        monday = today - __import__("datetime").timedelta(days=today.isoweekday() - 1)
        iso_cal = monday.isocalendar()
        week_label = f"{iso_cal.year}-W{iso_cal.week:02d}"

        try:
            with SyncSessionLocal() as db:
                new_report = ReportLog(week=week_label, status="pending")
                db.add(new_report)
                db.commit()
                db.refresh(new_report)
                report_id = new_report.id
            _run_report_generation(report_id, monday)
            logger.info("Scheduled report %d completed for week %s.", report_id, week_label)
        except Exception as exc:  # noqa: BLE001
            logger.error("Scheduled weekly report FAILED: %s", exc)

    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        _job,
        trigger=CronTrigger(day_of_week="mon", hour=9, minute=0),
        id="weekly_report",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("APScheduler weekly report job registered — fires every Monday 09:00 UTC.")


# ---------------------------------------------------------------------------
# Token-blacklist cleanup scheduler helper
# ---------------------------------------------------------------------------


def _schedule_blacklist_cleanup(db_engine: object) -> None:  # type: ignore[type-arg]
    """Register a daily APScheduler job to prune expired blacklisted tokens."""
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger

    from app.auth.models import TokenBlacklist
    from app.database import SyncSessionLocal

    def _cleanup_job() -> None:
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=7)
        try:
            with SyncSessionLocal() as db:
                result = db.execute(
                    delete(TokenBlacklist).where(TokenBlacklist.blacklisted_at < cutoff)
                )
                deleted = result.rowcount
                db.commit()
            if deleted:
                logger.info("Token blacklist cleanup: removed %d expired entries.", deleted)
        except Exception as exc:  # noqa: BLE001
            logger.error("Token blacklist cleanup failed: %s", exc)

    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        _cleanup_job,
        trigger=CronTrigger(hour=3, minute=0),  # 03:00 UTC daily
        id="blacklist_cleanup",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("APScheduler token blacklist cleanup job registered — fires daily at 03:00 UTC.")


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:  # type: ignore[type-arg]
    """Application lifespan: startup → yield → shutdown."""
    settings = get_settings()

    # ── 1. Check DB connection ───────────────────────────────────────────────
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection verified.")
    except Exception as exc:  # noqa: BLE001
        logger.critical("Cannot connect to database: %s", exc)
        # Continue startup; /health endpoint will report the failure.

    # ── 2. Load active ML model ──────────────────────────────────────────────
    app.state.model_bundle = None
    try:
        from ml.registry import load_active_model

        bundle = load_active_model(sync_engine, settings)
        app.state.model_bundle = bundle
        logger.info("Active ML model loaded into app.state.")
    except RuntimeError:
        logger.warning("No active model found — alerts and predictions will be unavailable.")
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load ML model: %s", exc)

    # ── 3. Start retraining scheduler ───────────────────────────────────────
    try:
        from ml.retrain import schedule_retrain

        schedule_retrain(settings, sync_engine)
        logger.info("APScheduler retraining job registered.")
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to start retraining scheduler: %s", exc)

    # ── 4. Schedule weekly PDF report generation ─────────────────────────
    try:
        _schedule_weekly_report(sync_engine)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to start report scheduler: %s", exc)

    # ── 5. Schedule token blacklist cleanup ──────────────────────────────
    try:
        _schedule_blacklist_cleanup(sync_engine)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to start blacklist cleanup scheduler: %s", exc)

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    logger.info("LogiTrack API shutting down.")
    await async_engine.dispose()


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="LogiTrack API",
        version="0.7.0",
        description=(
            "Logistics KPI dashboard and delay prediction backend.  "
            "Provides real-time KPIs, shipment management, ML-powered delay alerts, "
            "and seller performance analytics.\n\n"
            "**Swagger UI:** `/docs`  |  **ReDoc:** `/redoc`"
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # ── Rate limiting (slowapi) ───────────────────────────────────────────────
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
    app.add_middleware(SlowAPIASGIMiddleware)

    # ── CORS ─────────────────────────────────────────────────────────────────
    cors_origins_raw = getattr(settings, "CORS_ORIGINS", "http://localhost:5173")
    if isinstance(cors_origins_raw, str):
        cors_origins = [o.strip() for o in cors_origins_raw.split(",")]
    else:
        cors_origins = list(cors_origins_raw)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── HTTPS enforcement (production) ───────────────────────────────────────
    @app.middleware("http")
    async def https_redirect(request: Request, call_next):  # type: ignore[no-untyped-def]
        if (
            settings.ENVIRONMENT == "production"
            and request.headers.get("X-Forwarded-Proto", "https") == "http"
        ):
            https_url = request.url.replace(scheme="https")
            return RedirectResponse(url=str(https_url), status_code=301)
        return await call_next(request)

    # ── Security headers ─────────────────────────────────────────────────────
    @app.middleware("http")
    async def security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if settings.ENVIRONMENT == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    # ── Request logging middleware ────────────────────────────────────────────
    @app.middleware("http")
    async def log_requests(request: Request, call_next):  # type: ignore[no-untyped-def]
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "%s %s → %d  [%.1f ms]",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response

    # ── Global exception handlers ─────────────────────────────────────────────
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:  # type: ignore[misc]
        logger.debug("ValueError at %s: %s", request.url.path, exc)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": str(exc)},
        )

    @app.exception_handler(RuntimeError)
    async def runtime_error_handler(request: Request, exc: RuntimeError) -> JSONResponse:  # type: ignore[misc]
        logger.error("RuntimeError at %s: %s", request.url.path, exc)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": str(exc)},
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:  # type: ignore[misc]
        logger.exception("Unhandled exception at %s", request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error."},
        )

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(auth_router)
    app.include_router(kpi_router)
    app.include_router(shipments_router)
    app.include_router(alerts_router)
    app.include_router(sellers_router)
    app.include_router(ml_router)
    app.include_router(reports_router)

    # ── Health endpoint ───────────────────────────────────────────────────────
    @app.get("/health", tags=["Health"], summary="System health check")
    async def health(request: Request) -> JSONResponse:
        """Return DB connectivity status, model version, and process uptime."""
        db_ok = False
        db_error: str | None = None
        try:
            async with async_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            db_ok = True
        except Exception as exc:  # noqa: BLE001
            db_error = str(exc)

        bundle = getattr(request.app.state, "model_bundle", None)
        model_loaded = bundle is not None

        uptime_seconds = round(time.time() - _START_TIME, 1)

        payload = {
            "status": "healthy" if db_ok else "degraded",
            "database": {"connected": db_ok, "error": db_error},
            "model_loaded": model_loaded,
            "uptime_seconds": uptime_seconds,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }

        http_status = status.HTTP_200_OK if db_ok else status.HTTP_503_SERVICE_UNAVAILABLE
        return JSONResponse(content=payload, status_code=http_status)

    return app


app = create_app()

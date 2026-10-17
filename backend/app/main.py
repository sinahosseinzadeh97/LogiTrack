"""FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.auth.router import limiter
from app.auth.router import router as auth_router
from app.config import get_settings
from app.database import get_engine
from app.routers import alerts, kpi, ml, sellers, shipments
from app.routers.ml import LoadedModel
from ml import model_store

logger = logging.getLogger("app")


def _load_model() -> LoadedModel | None:
    model_dir = get_settings().MODEL_DIR
    if not model_store.exists(model_dir):
        logger.warning(
            "no model in %s; prediction endpoints return 503 until one is trained", model_dir
        )
        return None
    pipeline, card = model_store.load(model_dir)
    logger.info("loaded model %s (cutoff %s)", card["version"], card["cutoff"])
    return LoadedModel(pipeline, card)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.model = _load_model()
    yield
    await get_engine().dispose()


def create_app() -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = get_settings()
    app = FastAPI(title="LogiTrack API", version="1.0.0", lifespan=lifespan)

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next) -> Response:
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    for module in (kpi, shipments, sellers, alerts, ml):
        app.include_router(module.router)
    app.include_router(auth_router)

    @app.get("/health", tags=["health"])
    async def health(request: Request) -> JSONResponse:
        model_loaded = request.app.state.model is not None
        try:
            async with get_engine().connect() as conn:
                await conn.execute(text("SELECT 1"))
        except (SQLAlchemyError, OSError):
            logger.exception("health check: database unreachable")
            return JSONResponse(
                {"status": "degraded", "database": False, "model_loaded": model_loaded},
                status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return JSONResponse({"status": "ok", "database": True, "model_loaded": model_loaded})

    return app


app = create_app()

"""
Async SQLAlchemy engine and session factory for LogiTrack.

Usage in FastAPI route handlers::

    from app.database import get_async_session

    @router.get("/shipments")
    async def list_shipments(db: AsyncSession = Depends(get_async_session)):
        result = await db.execute(select(Shipment))
        return result.scalars().all()

The synchronous engine (``sync_engine``) is provided exclusively for Alembic
migrations and ETL batch operations that cannot run in an async context.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

logger = logging.getLogger(__name__)

_settings = get_settings()

# ---------------------------------------------------------------------------
# Async engine — used by the FastAPI application at runtime
# ---------------------------------------------------------------------------
async_engine: AsyncEngine = create_async_engine(
    _settings.DATABASE_URL,
    pool_pre_ping=True,          # checks connection liveness before checkout
    pool_size=10,
    max_overflow=20,
    echo=_settings.ENVIRONMENT == "development",
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,      # avoids lazy-load errors after commit
    autoflush=False,
    autocommit=False,
)

# ---------------------------------------------------------------------------
# Sync engine — used by Alembic and ETL bulk operations
# ---------------------------------------------------------------------------
sync_engine = create_engine(
    _settings.DATABASE_SYNC_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=_settings.ENVIRONMENT == "development",
)

SyncSessionLocal: sessionmaker[Session] = sessionmaker(
    bind=sync_engine,
    autoflush=False,
    autocommit=False,
)


# ---------------------------------------------------------------------------
# Dependency injector — FastAPI
# ---------------------------------------------------------------------------
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a transactional ``AsyncSession`` and guarantee cleanup.

    This function is intended for use as a FastAPI ``Depends`` dependency.
    The session is committed automatically if the handler raises no exception;
    any unhandled exception triggers a rollback before the session is closed.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
            logger.debug("AsyncSession closed.")

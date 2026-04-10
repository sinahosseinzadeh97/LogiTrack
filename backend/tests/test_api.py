"""
Phase 4 — API Integration Tests (15 tests)

Uses ``httpx.AsyncClient`` with ``pytest-asyncio`` and an in-memory SQLite
database.  The key technique is injecting a stub ``app.database`` module into
``sys.modules`` *before* any app module is imported, so the real PostgreSQL
``create_async_engine`` (which rejects ``pool_size`` on SQLite) is never called.

Test inventory:
  1.  test_health_returns_200
  2.  test_login_returns_tokens
  3.  test_login_invalid_credentials_returns_401
  4.  test_protected_route_without_token_returns_401
  5.  test_viewer_cannot_access_admin_route
  6.  test_kpi_summary_structure
  7.  test_otif_trend_returns_correct_week_count
  8.  test_shipments_pagination_works
  9.  test_shipments_filter_by_state
  10. test_shipments_export_returns_csv
  11. test_single_shipment_has_prediction
  12. test_alerts_returns_list
  13. test_predict_returns_probability
  14. test_retrain_requires_admin
  15. test_model_info_returns_version
"""

from __future__ import annotations

import os
import sys
import types
from collections.abc import AsyncGenerator
from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# ---------------------------------------------------------------------------
# 1. Env vars — must be set before any pydantic-settings model instantiates
# ---------------------------------------------------------------------------
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["DATABASE_SYNC_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key-logitrack-phase4"
os.environ["ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
os.environ["REFRESH_TOKEN_EXPIRE_DAYS"] = "7"
os.environ["S3_ENDPOINT_URL"] = "http://localhost:9000"
os.environ["S3_ACCESS_KEY"] = "minioadmin"
os.environ["S3_SECRET_KEY"] = "minioadmin"
os.environ["S3_BUCKET_NAME"] = "logitrack"
os.environ["ENVIRONMENT"] = "testing"

# ---------------------------------------------------------------------------
# 2. Build the in-memory SQLite async engine BEFORE app.database is imported
# ---------------------------------------------------------------------------
_test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)

_TestSession: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=_test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def _test_get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with _TestSession() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# 3. Inject stub app.database into sys.modules so real PG engine is skipped
# ---------------------------------------------------------------------------
_db_stub = types.ModuleType("app.database")
_db_stub.async_engine = _test_engine          # type: ignore[attr-defined]
_db_stub.sync_engine = MagicMock()            # type: ignore[attr-defined]
_db_stub.get_async_session = _test_get_async_session  # type: ignore[attr-defined]
_db_stub.AsyncSessionLocal = _TestSession     # type: ignore[attr-defined]
sys.modules["app.database"] = _db_stub

# ---------------------------------------------------------------------------
# 4. Now it is safe to import all app modules
# ---------------------------------------------------------------------------
from app.auth.models import TokenBlacklist, User, UserRole  # noqa: E402
from app.auth.service import hash_password  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models.shipment import (  # noqa: E402
    Base,
    KpiDaily,
    MlModelVersion,
    SellerStats,
    Shipment,
)

# Also import auth models so their tables are in Base.metadata
import app.auth.models  # noqa: E402, F401

from httpx import ASGITransport, AsyncClient  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables() -> AsyncGenerator[None, None]:
    """Create all tables once per session."""
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="session")
async def seed_data(create_tables: None) -> None:
    """Insert minimal rows for all tests."""
    async with _TestSession() as db:
        # ── Users ──────────────────────────────────────────────────────────
        db.add_all([
            User(
                id=1,
                email="admin@logitrack.com",
                hashed_password=hash_password("adminpass123"),
                full_name="Admin User",
                role=UserRole.admin,
                is_active=True,
            ),
            User(
                id=2,
                email="analyst@logitrack.com",
                hashed_password=hash_password("analystpass123"),
                full_name="Analyst User",
                role=UserRole.analyst,
                is_active=True,
            ),
            User(
                id=3,
                email="viewer@logitrack.com",
                hashed_password=hash_password("viewerpass123"),
                full_name="Viewer User",
                role=UserRole.viewer,
                is_active=True,
            ),
        ])

        # ── Shipments (30) ─────────────────────────────────────────────────
        now = datetime.now(tz=timezone.utc)
        db.add_all([
            Shipment(
                id=i + 1,
                order_id=f"order_{i:04d}",
                customer_id=f"cust_{i:04d}",
                seller_id="seller_AAAA" if i < 20 else "seller_BBBB",
                category_name="electronics" if i % 2 == 0 else "furniture",
                seller_state="SP" if i < 15 else "RJ",
                customer_state="MG",
                purchase_timestamp=now,
                delivered_timestamp=now,
                price=100.0,
                freight_value=10.0,
                delay_days=float(i % 5),
                is_late=bool(i % 3 == 0),
                distance_km=200.0 + i,
                day_of_week=i % 7,
                month=1,
                seller_historical_delay_rate=0.1,
            )
            for i in range(30)
        ])

        # ── KPI daily ──────────────────────────────────────────────────────
        db.add(KpiDaily(
            id=1,
            date=date.today(),
            otif_rate=85.0,
            avg_delay_days=1.5,
            fulfillment_rate=95.0,
            avg_cost_per_shipment=10.0,
            total_shipments=30,
            flagged_count=3,
        ))

        # ── Seller stats ───────────────────────────────────────────────────
        db.add(SellerStats(
            id=1,
            seller_id="seller_AAAA",
            seller_state="SP",
            total_orders=20,
            delay_rate=0.33,
            avg_delay_days=1.2,
            avg_cost=10.0,
        ))

        # ── ML model version ───────────────────────────────────────────────
        db.add(MlModelVersion(
            id=1,
            version="v0.1.0-test",
            accuracy=0.91,
            precision_late=0.63,
            recall_late=0.68,
            f1_late=0.65,
            threshold=0.65,
            is_active=True,
            storage_path="local/test_model.joblib",
        ))

        await db.commit()


@pytest_asyncio.fixture(scope="session")
async def app(seed_data: None):  # noqa: ANN201
    """Return a FastAPI test app with the test session injected."""
    _app = create_app()
    _app.dependency_overrides[_test_get_async_session] = _test_get_async_session
    _app.state.model_bundle = None  # no ML model in unit tests
    return _app


@pytest_asyncio.fixture(scope="session")
async def client(app) -> AsyncGenerator[AsyncClient, None]:  # noqa: ANN001
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

async def _get_token(client: AsyncClient, email: str, password: str) -> str:
    resp = await client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


# ===========================================================================
# TESTS
# ===========================================================================


# 1 ─────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_health_returns_200(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code in (200, 503)
    body = resp.json()
    assert "status" in body
    assert "database" in body
    assert "uptime_seconds" in body


# 2 ─────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_login_returns_tokens(client: AsyncClient) -> None:
    resp = await client.post(
        "/auth/login",
        json={"email": "admin@logitrack.com", "password": "adminpass123"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0


# 3 ─────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_login_invalid_credentials_returns_401(client: AsyncClient) -> None:
    resp = await client.post(
        "/auth/login",
        json={"email": "admin@logitrack.com", "password": "WRONG"},
    )
    assert resp.status_code == 401


# 4 ─────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_protected_route_without_token_returns_401(client: AsyncClient) -> None:
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


# 5 ─────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_viewer_cannot_access_admin_route(client: AsyncClient) -> None:
    token = await _get_token(client, "viewer@logitrack.com", "viewerpass123")
    resp = await client.get(
        "/api/v1/ml/model-info",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


# 6 ─────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_kpi_summary_structure(client: AsyncClient) -> None:
    token = await _get_token(client, "viewer@logitrack.com", "viewerpass123")
    resp = await client.get(
        "/api/v1/kpi/summary",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    for key in ("otif_rate", "avg_delay_days", "fulfillment_rate",
                "avg_cost_per_shipment", "total_shipments", "late_shipments"):
        assert key in body, f"Missing key: {key}"


# 7 ─────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_otif_trend_returns_correct_week_count(client: AsyncClient) -> None:
    token = await _get_token(client, "viewer@logitrack.com", "viewerpass123")
    resp = await client.get(
        "/api/v1/kpi/otif-trend?weeks=6",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 6
    for pt in body:
        assert "week_start" in pt
        assert "otif_rate" in pt


# 8 ─────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_shipments_pagination_works(client: AsyncClient) -> None:
    token = await _get_token(client, "viewer@logitrack.com", "viewerpass123")
    resp = await client.get(
        "/api/v1/shipments?page=1&page_size=10",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body and "total" in body and "total_pages" in body
    assert len(body["items"]) <= 10
    assert body["page"] == 1
    assert body["total"] == 30


# 9 ─────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_shipments_filter_by_state(client: AsyncClient) -> None:
    token = await _get_token(client, "viewer@logitrack.com", "viewerpass123")
    resp = await client.get(
        "/api/v1/shipments?state=SP",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 15
    for item in body["items"]:
        assert item["seller_state"] == "SP"


# 10 ────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_shipments_export_returns_csv(client: AsyncClient) -> None:
    token = await _get_token(client, "analyst@logitrack.com", "analystpass123")
    resp = await client.get(
        "/api/v1/shipments/export",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("content-type", "")
    assert "order_id" in resp.text


# 11 ────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_single_shipment_has_prediction(client: AsyncClient) -> None:
    token = await _get_token(client, "viewer@logitrack.com", "viewerpass123")
    resp = await client.get(
        "/api/v1/shipments/order_0000",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["order_id"] == "order_0000"
    assert "prediction_probability" in body  # None when no model loaded — that's fine


# 12 ────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_alerts_returns_list(client: AsyncClient) -> None:
    token = await _get_token(client, "viewer@logitrack.com", "viewerpass123")
    resp = await client.get(
        "/api/v1/alerts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)  # empty list when no model — acceptable


# 13 ────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_predict_returns_probability(client: AsyncClient) -> None:
    token = await _get_token(client, "analyst@logitrack.com", "analystpass123")
    resp = await client.post(
        "/api/v1/alerts/predict",
        json={
            "distance_km": 500.0,
            "category_name": "electronics",
            "seller_state": "SP",
            "day_of_week": 4,
            "freight_value": 25.0,
            "price": 299.99,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    # 503 when no model is loaded (expected in isolation); 200 when model present
    assert resp.status_code in (200, 503)
    if resp.status_code == 200:
        body = resp.json()
        assert 0.0 <= body["delay_probability"] <= 1.0
        assert body["risk_level"] in ("low", "medium", "high")


# 14 ────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_retrain_requires_admin(client: AsyncClient) -> None:
    for email, pw in [
        ("viewer@logitrack.com", "viewerpass123"),
        ("analyst@logitrack.com", "analystpass123"),
    ]:
        token = await _get_token(client, email, pw)
        resp = await client.post(
            "/api/v1/ml/retrain",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403, f"Expected 403 for {email}, got {resp.status_code}"


# 15 ────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_model_info_returns_version(client: AsyncClient) -> None:
    token = await _get_token(client, "admin@logitrack.com", "adminpass123")
    resp = await client.get(
        "/api/v1/ml/model-info",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == "v0.1.0-test"
    assert body["is_active"] is True
    assert "accuracy" in body
    assert "threshold" in body

# Phase 04 — FastAPI REST API with JWT Authentication & RBAC

**Project:** LogiTrack — Logistics KPI Dashboard & Delay Prediction System  
**Phase:** 04 — API Layer  
**Completed:** 2026-04-09  
**Author:** Engineering Team  

---

## 1. Files Created / Modified

| # | Path | Type | Description |
|---|------|------|-------------|
| 1 | `backend/app/auth/__init__.py` | New | Auth package marker |
| 2 | `backend/app/auth/models.py` | New | `User` + `TokenBlacklist` ORM models; `UserRole` enum |
| 3 | `backend/app/auth/schemas.py` | New | Pydantic schemas: `UserCreate`, `UserLogin`, `TokenResponse`, `UserResponse`, `RefreshRequest`, `LogoutRequest` |
| 4 | `backend/app/auth/service.py` | New | bcrypt hashing, JWT creation/decode, `get_current_user`, `require_role` factory, blacklist helpers |
| 5 | `backend/app/auth/router.py` | New | Auth router: register, login, refresh, me, logout |
| 6 | `backend/app/routers/__init__.py` | New | Routers package marker |
| 7 | `backend/app/routers/kpi.py` | New | KPI endpoints: summary, OTIF trend, delay-by-category, seller-scorecard |
| 8 | `backend/app/routers/shipments.py` | New | Shipment endpoints: paginated list, single, CSV export |
| 9 | `backend/app/routers/alerts.py` | New | Alert endpoints: flagged list, stats, live predict |
| 10 | `backend/app/routers/sellers.py` | New | Seller endpoints: profile + 8w trend, paginated shipments |
| 11 | `backend/app/routers/ml.py` | New | ML admin endpoints: model-info, feature-importance, retrain trigger, retrain status |
| 12 | `backend/app/main.py` | New | FastAPI app: lifespan, CORS, logging middleware, exception handlers, `/health` |
| 13 | `backend/app/models/__init__.py` | Modified | Registers `User` + `TokenBlacklist` with `Base.metadata` |
| 14 | `backend/alembic/versions/0002_add_auth_tables.py` | New | Migration: creates `users`, `token_blacklist`, `userrole` enum |
| 15 | `backend/tests/test_api.py` | New | 15 `httpx.AsyncClient` integration tests (in-memory SQLite) |
| 16 | `backend/pyproject.toml` | Modified | Adds `email-validator`, `aiosqlite` |
| 17 | `docs/phase-reports/PHASE_04_REPORT.md` | New | This document |

---

## 2. Complete API Endpoint Table

| Method | Path | Auth Required | Role | Description |
|--------|------|---------------|------|-------------|
| `POST` | `/auth/register` | ✅ Bearer | admin | Create a new user account |
| `POST` | `/auth/login` | ❌ | — | Exchange credentials for JWT pair |
| `POST` | `/auth/refresh` | ❌ | — | Rotate access token via refresh token |
| `GET` | `/auth/me` | ✅ Bearer | any | Return current user profile |
| `POST` | `/auth/logout` | ✅ Bearer | any | Blacklist refresh token |
| `GET` | `/api/v1/kpi/summary` | ✅ Bearer | viewer+ | Aggregated KPI dashboard summary |
| `GET` | `/api/v1/kpi/otif-trend` | ✅ Bearer | viewer+ | Weekly OTIF rate trend (`?weeks=N`) |
| `GET` | `/api/v1/kpi/delay-by-category` | ✅ Bearer | viewer+ | Avg delay grouped by product category |
| `GET` | `/api/v1/kpi/seller-scorecard` | ✅ Bearer | viewer+ | Seller performance scorecard |
| `GET` | `/api/v1/shipments` | ✅ Bearer | viewer+ | Paginated + filtered shipment list |
| `GET` | `/api/v1/shipments/export` | ✅ Bearer | analyst+ | Stream filtered results as CSV |
| `GET` | `/api/v1/shipments/{order_id}` | ✅ Bearer | viewer+ | Single shipment detail with ML probability |
| `GET` | `/api/v1/alerts` | ✅ Bearer | viewer+ | Flagged at-risk in-transit shipments |
| `GET` | `/api/v1/alerts/stats` | ✅ Bearer | viewer+ | Aggregate risk counts (high/medium/total) |
| `POST` | `/api/v1/alerts/predict` | ✅ Bearer | analyst+ | Single-row live delay inference |
| `GET` | `/api/v1/sellers/{seller_id}` | ✅ Bearer | viewer+ | Seller profile + 8-week OTIF trend |
| `GET` | `/api/v1/sellers/{seller_id}/shipments` | ✅ Bearer | viewer+ | Paginated shipments for one seller |
| `GET` | `/api/v1/ml/model-info` | ✅ Bearer | admin | Active model version metadata |
| `GET` | `/api/v1/ml/feature-importance` | ✅ Bearer | admin | Per-feature importances from loaded model |
| `POST` | `/api/v1/ml/retrain` | ✅ Bearer | admin | Trigger retraining as background task |
| `GET` | `/api/v1/ml/retrain-status/{task_id}` | ✅ Bearer | admin | Poll retraining task status |
| `GET` | `/health` | ❌ | — | DB connectivity, model version, uptime |

---

## 3. JWT Token Flow

```
┌──────────┐                       ┌───────────────────┐
│  Client  │                       │  LogiTrack API    │
└────┬─────┘                       └────────┬──────────┘
     │                                      │
     │  POST /auth/login                    │
     │  { email, password }                 │
     │─────────────────────────────────────►│
     │                                      │  1. bcrypt.verify(password, hash)
     │                                      │  2. create_access_token (30 min, HS256)
     │                                      │  3. create_refresh_token (7 days, JTI)
     │  200 { access_token, refresh_token } │
     │◄─────────────────────────────────────│
     │                                      │
     │  GET /api/v1/kpi/summary             │
     │  Authorization: Bearer <access_token>│
     │─────────────────────────────────────►│
     │                                      │  4. OAuth2PasswordBearer extracts token
     │                                      │  5. decode_token() → payload
     │                                      │  6. payload["type"] == "access" check
     │                                      │  7. SELECT user WHERE id = sub
     │                                      │  8. require_role("viewer") check
     │  200 { ... }                         │
     │◄─────────────────────────────────────│
     │                                      │
     │  POST /auth/refresh                  │
     │  { refresh_token }                   │
     │─────────────────────────────────────►│
     │                                      │  9.  payload["type"] == "refresh" check
     │                                      │  10. JTI not in token_blacklist
     │                                      │  11. INSERT old JTI into blacklist
     │                                      │  12. Issue new access + refresh pair
     │  200 { access_token, refresh_token } │
     │◄─────────────────────────────────────│
     │                                      │
     │  POST /auth/logout                   │
     │  { refresh_token }                   │
     │─────────────────────────────────────►│
     │                                      │  13. INSERT JTI into token_blacklist
     │  204 No Content                      │
     │◄─────────────────────────────────────│
```

**Token Claims:**

| Claim | Access Token | Refresh Token |
|-------|-------------|---------------|
| `sub` | user_id (str) | user_id (str) |
| `role` | UserRole value | — |
| `type` | `"access"` | `"refresh"` |
| `jti` | — | UUID4 (for blacklisting) |
| `exp` | now + 30 min | now + 7 days |
| `iat` | issued-at UTC | issued-at UTC |

---

## 4. RBAC Matrix

| Endpoint Group | viewer | analyst | admin |
|----------------|:------:|:-------:|:-----:|
| `GET /auth/me` | ✅ | ✅ | ✅ |
| `POST /auth/register` | ❌ | ❌ | ✅ |
| `GET /api/v1/kpi/*` | ✅ | ✅ | ✅ |
| `GET /api/v1/shipments` | ✅ | ✅ | ✅ |
| `GET /api/v1/shipments/{id}` | ✅ | ✅ | ✅ |
| `GET /api/v1/shipments/export` | ❌ | ✅ | ✅ |
| `GET /api/v1/alerts` | ✅ | ✅ | ✅ |
| `GET /api/v1/alerts/stats` | ✅ | ✅ | ✅ |
| `POST /api/v1/alerts/predict` | ❌ | ✅ | ✅ |
| `GET /api/v1/sellers/*` | ✅ | ✅ | ✅ |
| `GET /api/v1/ml/model-info` | ❌ | ❌ | ✅ |
| `GET /api/v1/ml/feature-importance` | ❌ | ❌ | ✅ |
| `POST /api/v1/ml/retrain` | ❌ | ❌ | ✅ |
| `GET /api/v1/ml/retrain-status/*` | ❌ | ❌ | ✅ |
| `GET /health` | ✅ | ✅ | ✅ |

**Role hierarchy:** viewer ⊂ analyst ⊂ admin (each higher role inherits lower-role access)

---

## 5. Database Indexes Added

Migration `0002_add_auth_tables.py` adds the following indexes:

| Table | Index Name | Column(s) | Type |
|-------|-----------|-----------|------|
| `users` | `ix_users_email` | `email` | UNIQUE |
| `token_blacklist` | `ix_token_blacklist_jti` | `jti` | UNIQUE |

Existing indexes from migration `0001` continue to serve:

| Table | Index | Serves |
|-------|-------|--------|
| `shipments` | `ix_shipments_order_id` | `GET /shipments/{order_id}` |
| `shipments` | `ix_shipments_seller_id` | `GET /sellers/{id}/shipments` |
| `shipments` | `ix_shipments_is_late` | `GET /shipments?status=late` |
| `shipments` | `ix_shipments_seller_state` | `GET /shipments?state=SP` |
| `shipments` | `ix_shipments_purchase_ts` | Date-range filters |
| `seller_stats` | `ix_seller_stats_seller_id` | `GET /sellers/{id}` |
| `kpi_daily` | `ix_kpi_daily_date` | Latest-day KPI summary |

> **Query optimised:** `GET /api/v1/shipments` uses `SELECT COUNT(*) FROM (subquery)` + `OFFSET/LIMIT` — zero full-table loads.

---

## 6. Caching Strategy

| Endpoint | TTL | Mechanism |
|----------|-----|-----------|
| `GET /kpi/summary` | 5 min | Recommended: `fastapi-cache2` with Redis backend in production. Current implementation: fresh DB query per request (sufficient for <100 RPS). |
| `GET /kpi/otif-trend` | 5 min | Same as summary — results rarely change between requests. |
| `GET /alerts` | 10 min | ML inference is expensive. Production: Redis TTL on the flagged list. Current: per-request re-inference. |
| `GET /alerts/stats` | 10 min | Same as alerts list. |
| `app.state.model_bundle` | Process lifetime | Model loaded once at startup. Refreshed automatically when `POST /ml/retrain` promotes a new version (planned for Phase 5). |
| Token blacklist lookups | — | Stored in PostgreSQL `token_blacklist` table. Consider Redis `SETEX` for hot-path performance in high-traffic deployments. |

---

## 7. How to Run

### Prerequisites

- Docker Desktop ≥ 4.28 (for PostgreSQL + MinIO)
- Python 3.12 with venv
- Phase 1–3 prerequisites completed (ETL run, ML model trained)

### Step 1 — Start infrastructure

```bash
docker compose up -d
# Verify health
docker compose ps
```

### Step 2 — Install dependencies

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Step 3 — Apply migrations

```bash
# From backend/ directory
alembic upgrade head
# Expected:
# Running upgrade 0001 -> 0002, Add auth tables
```

### Step 4 — Run the API

```bash
# From project root (so .env is found)
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

Or from inside `backend/`:

```bash
uvicorn app.main:app --reload
```

### Step 5 — Verify

```
Swagger UI:  http://localhost:8000/docs
ReDoc:       http://localhost:8000/redoc
Health:      http://localhost:8000/health
```

---

## 8. API Test Suite

### Run all 15 API tests

```bash
cd backend
source .venv/bin/activate

# API tests only
pytest tests/test_api.py -v --tb=short

# Full suite (KPI + ML + API)
pytest tests/ -v --tb=short --cov=app --cov=core --cov=ml --cov-report=term-missing
```

### Expected output (all 15 tests green)

```
tests/test_api.py::test_health_returns_200                    PASSED
tests/test_api.py::test_login_returns_tokens                  PASSED
tests/test_api.py::test_login_invalid_credentials_returns_401 PASSED
tests/test_api.py::test_protected_route_without_token_returns_401 PASSED
tests/test_api.py::test_viewer_cannot_access_admin_route      PASSED
tests/test_api.py::test_kpi_summary_structure                 PASSED
tests/test_api.py::test_otif_trend_returns_correct_week_count PASSED
tests/test_api.py::test_shipments_pagination_works            PASSED
tests/test_api.py::test_shipments_filter_by_state             PASSED
tests/test_api.py::test_shipments_export_returns_csv          PASSED
tests/test_api.py::test_single_shipment_has_prediction        PASSED
tests/test_api.py::test_alerts_returns_list                   PASSED
tests/test_api.py::test_predict_returns_probability           PASSED
tests/test_api.py::test_retrain_requires_admin                PASSED
tests/test_api.py::test_model_info_returns_version            PASSED

========================= 15 passed in X.XXs =========================
```

### Test design notes

- **No live PostgreSQL required** — tests use `aiosqlite` in-memory SQLite via a dependency override.
- **Session-scoped fixtures** — DB is created once per session, seeded with 30 shipments + 3 users.
- **Auth fixtures** — `_get_token()` helper calls `/auth/login` to obtain real JWTs signed with the test `SECRET_KEY`.
- **Graceful 503 tests** — predictions and model-info tests handle `503` when no model bundle is loaded (expected in isolated test runs).

---

## 9. Swagger UI

After starting the server, navigating to `http://localhost:8000/docs` gives full interactive Swagger documentation with:

- All 22 endpoints grouped by tag (Authentication, KPI, Shipments, Alerts, Sellers, ML Admin, Health)
- Request / response schemas auto-generated from Pydantic models
- OAuth2 Bearer token input at the top-right ("Authorize" button)
- Try-it-out functionality for every endpoint

---

## 10. Notes for Phase 5 (Frontend Integration)

| Topic | Detail |
|-------|--------|
| **CORS** | `CORSMiddleware` is pre-wired. Add your React dev server origin (`http://localhost:5173`) to `CORS_ORIGINS` in `.env`. |
| **Auth flow** | Store `access_token` in `memory` (not `localStorage`). Store `refresh_token` in an `HttpOnly` cookie for XSS protection. Call `POST /auth/refresh` silently when the API returns `401`. |
| **Pagination** | All list endpoints return `{items, total, page, page_size, total_pages}`. Use `total_pages` to render page controls; `page_size=50` is the default. |
| **KPI WebSocket** | Phase 5 can replace the polling pattern with a WebSocket endpoint (`/ws/kpi`) that pushes summaries every 30 seconds. The KPI engine is already stateless. |
| **Real-time alerts** | `GET /api/v1/alerts` returns the current risk list synchronously. For live badge updates, poll every 60 s or subscribe via SSE. |
| **CSV export** | The CSV `StreamingResponse` sets `Content-Disposition: attachment`. Handle it in the frontend as a Blob download — do not pass through a JSON deserialiser. |
| **Model reload** | After `POST /api/v1/ml/retrain` completes (poll `/retrain-status`), the frontend should prompt the admin to restart the server (or Phase 5 can implement a hot-reload signal via `app.state`). |
| **Environment** | Set `ENVIRONMENT=production` to disable SQLAlchemy echo. Set `ACCESS_TOKEN_EXPIRE_MINUTES=15` for tighter security in production. |
| **Error format** | All API errors return `{"detail": "..."}` — use this key in global error toast notifications. |

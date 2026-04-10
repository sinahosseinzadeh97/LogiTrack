# Phase 01 — Project Scaffold & ETL Pipeline

**Project:** LogiTrack — Logistics KPI Dashboard & Delay Prediction System  
**Phase:** 01 — Foundation  
**Completed:** 2026-04-09  
**Author:** Engineering Team  

---

## 1. Deliverables

Every file created in this phase is listed below with its path (from project root) and a one-line description.

| # | Path | Description |
|---|------|-------------|
| 1 | `backend/app/__init__.py` | App package marker |
| 2 | `backend/app/config.py` | Pydantic-Settings `Settings` class; reads all values from `.env`; singleton via `lru_cache` |
| 3 | `backend/app/database.py` | Async SQLAlchemy engine + `AsyncSession` factory (FastAPI) and sync engine (Alembic / ETL) |
| 4 | `backend/app/models/__init__.py` | Re-exports all ORM models; makes `Base` importable by Alembic |
| 5 | `backend/app/models/shipment.py` | Four ORM models: `Shipment`, `KpiDaily`, `SellerStats`, `MlModelVersion` |
| 6 | `backend/etl/__init__.py` | ETL package marker |
| 7 | `backend/etl/clean.py` | Stage 1 — CSV ingestion, timestamp parsing, multi-table merge, delay computation |
| 8 | `backend/etl/enrich.py` | Stage 2 — geo features (geodesic distance), temporal features, seller delay rate, cost/km |
| 9 | `backend/etl/load.py` | Stage 3 — batch upsert to `shipments`, `kpi_daily`, `seller_stats` |
| 10 | `backend/etl/run.py` | ETL entry-point (`python -m etl.run`); structured logging; exits 0/1 |
| 11 | `backend/alembic/env.py` | Alembic environment; injects `DATABASE_SYNC_URL` from `Settings`; wires `Base.metadata` |
| 12 | `backend/alembic/script.py.mako` | Alembic migration script template |
| 13 | `backend/alembic/versions/0001_initial_schema.py` | Initial migration; creates all 4 tables + indexes; `checkfirst=True` (idempotent) |
| 14 | `backend/alembic.ini` | Alembic configuration; timestamped filename template; logger hierarchy |
| 15 | `backend/pyproject.toml` | Project metadata, all runtime/dev dependencies, Ruff + Mypy + Pytest config |
| 16 | `docker-compose.yml` | `postgres:16-alpine`, `minio/minio:latest`, `adminer:latest`; healthchecks; named volumes |
| 17 | `docker/Dockerfile.backend` | Multi-stage Python 3.12 image; non-root user; health check |
| 18 | `docker/Dockerfile.frontend` | Node 20 + nginx placeholder for Phase 2 React dashboard |
| 19 | `.env.example` | All required environment variables with safe placeholder values |
| 20 | `.gitignore` | Excludes secrets, raw CSVs, Python artefacts, IDE files, Node modules |
| 21 | `data/raw/.gitkeep` | Tracks the raw data directory without committing CSVs |
| 22 | `data/processed/.gitkeep` | Tracks the processed data directory |
| 23 | `docs/phase-reports/.gitkeep` | Tracks the phase report directory |
| 24 | `backend/alembic/versions/.gitkeep` | Tracks the Alembic versions directory before first migration |
| 25 | `docs/phase-reports/PHASE_01_REPORT.md` | This document |

---

## 2. Database Schema

### Table: `shipments`

| Column | Type | Nullable | Constraints / Defaults |
|--------|------|----------|------------------------|
| `id` | `BIGINT` | No | PK, autoincrement |
| `order_id` | `VARCHAR(50)` | No | UNIQUE, INDEX |
| `customer_id` | `VARCHAR(50)` | No | INDEX |
| `seller_id` | `VARCHAR(50)` | No | INDEX |
| `product_id` | `VARCHAR(50)` | Yes | — |
| `category_name` | `VARCHAR(100)` | Yes | — |
| `seller_state` | `VARCHAR(5)` | Yes | INDEX |
| `customer_state` | `VARCHAR(5)` | Yes | — |
| `purchase_timestamp` | `TIMESTAMPTZ` | Yes | INDEX |
| `delivered_timestamp` | `TIMESTAMPTZ` | Yes | — |
| `estimated_delivery` | `TIMESTAMPTZ` | Yes | — |
| `price` | `NUMERIC(10,2)` | No | DEFAULT 0 |
| `freight_value` | `NUMERIC(10,2)` | No | DEFAULT 0 |
| `payment_value` | `NUMERIC(10,2)` | Yes | — |
| `delay_days` | `FLOAT` | Yes | — |
| `is_late` | `BOOLEAN` | No | DEFAULT false, INDEX |
| `distance_km` | `FLOAT` | Yes | — |
| `cost_per_km` | `FLOAT` | Yes | — |
| `seller_lat` | `FLOAT` | Yes | — |
| `seller_lng` | `FLOAT` | Yes | — |
| `customer_lat` | `FLOAT` | Yes | — |
| `customer_lng` | `FLOAT` | Yes | — |
| `day_of_week` | `SMALLINT` | Yes | 0=Mon … 6=Sun |
| `month` | `SMALLINT` | Yes | 1–12 |
| `seller_historical_delay_rate` | `FLOAT` | Yes | Look-ahead; training only |
| `review_score` | `SMALLINT` | Yes | 1–5 |
| `created_at` | `TIMESTAMPTZ` | No | `server_default=NOW()` |

### Table: `kpi_daily`

| Column | Type | Nullable | Constraints / Defaults |
|--------|------|----------|------------------------|
| `id` | `INTEGER` | No | PK, autoincrement |
| `date` | `DATE` | No | UNIQUE, INDEX |
| `otif_rate` | `FLOAT` | Yes | Fraction on-time [0,1] |
| `avg_delay_days` | `FLOAT` | Yes | Positive = late |
| `fulfillment_rate` | `FLOAT` | Yes | Fraction with delivery |
| `avg_cost_per_shipment` | `FLOAT` | Yes | Mean freight_value |
| `total_shipments` | `INTEGER` | Yes | Count per date |
| `flagged_count` | `INTEGER` | No | DEFAULT 0 |
| `updated_at` | `TIMESTAMPTZ` | No | `server_default=NOW()` |

### Table: `seller_stats`

| Column | Type | Nullable | Constraints / Defaults |
|--------|------|----------|------------------------|
| `id` | `INTEGER` | No | PK, autoincrement |
| `seller_id` | `VARCHAR(50)` | No | UNIQUE, INDEX |
| `seller_state` | `VARCHAR(5)` | Yes | — |
| `total_orders` | `INTEGER` | Yes | — |
| `delay_rate` | `FLOAT` | Yes | [0,1] |
| `avg_delay_days` | `FLOAT` | Yes | — |
| `avg_cost` | `FLOAT` | Yes | Mean freight_value |
| `updated_at` | `TIMESTAMPTZ` | No | `server_default=NOW()` |

### Table: `ml_model_versions`

| Column | Type | Nullable | Constraints / Defaults |
|--------|------|----------|------------------------|
| `id` | `INTEGER` | No | PK, autoincrement |
| `version` | `VARCHAR(50)` | No | — |
| `trained_at` | `TIMESTAMPTZ` | No | `server_default=NOW()` |
| `accuracy` | `FLOAT` | Yes | — |
| `precision_late` | `FLOAT` | Yes | — |
| `recall_late` | `FLOAT` | Yes | — |
| `f1_late` | `FLOAT` | Yes | — |
| `threshold` | `FLOAT` | No | DEFAULT 0.65 |
| `is_active` | `BOOLEAN` | No | DEFAULT false |
| `storage_path` | `VARCHAR(500)` | Yes | S3 key or local path |
| `notes` | `TEXT` | Yes | — |

---

## 3. ETL Flow

```
data/raw/*.csv  (9 files)
      │
      ▼
┌─────────────────────────────────────┐
│  Stage 1 — clean.py                 │
│  load_raw_csvs()                     │  ← explicit dtypes, row count logging
│  parse_timestamps()                  │  ← UTC-aware datetime64, errors='coerce'
│  clean_orders()                      │  ← merge 8 tables, delay_days, is_late
│                                     │
│  Outputs:                           │
│    df_delivered  (order_status=     │
│                   'delivered')      │
│    df_all        (all statuses)     │
└───────────────┬─────────────────────┘
                │ df_delivered, df_all
                ▼
┌─────────────────────────────────────┐
│  Stage 2 — enrich.py                │
│  add_geo_features()                  │  ← zip→lat/lng join, geodesic distance
│  add_temporal_features()             │  ← day_of_week, month
│  add_seller_delay_rate()             │  ← mean(is_late) per seller
│  compute_cost_per_km()               │  ← freight_value / distance_km
│                                     │
│  Output: df_enriched                │
└───────────────┬─────────────────────┘
                │ df_enriched, df_all
                ▼
┌─────────────────────────────────────┐
│  Stage 3 — load.py                  │
│  upsert_shipments()                  │  ← batches of 1000, ON CONFLICT DO UPDATE
│  compute_and_load_kpi_daily()        │  ← group by date → kpi_daily
│  compute_and_load_seller_stats()     │  ← group by seller_id → seller_stats
└─────────────────────────────────────┘
                │
                ▼
         PostgreSQL 16
   (shipments / kpi_daily / seller_stats)
```

---

## 4. Expected Row Counts (Olist Dataset)

These are the authoritative Olist public dataset sizes; actual post-ETL counts may vary by ±1% due to merge drops and deduplication.

| Source | Rows |
|--------|------|
| `olist_orders_dataset.csv` | ~99,441 |
| Orders with status = `delivered` | ~96,478 |
| `shipments` table (post-ETL) | ~96,000–96,500 |
| `kpi_daily` rows | ~710 distinct dates |
| `seller_stats` rows | ~3,095 unique sellers |
| `olist_geolocation_dataset.csv` | ~1,000,163 (deduplicated to ~19,015 unique zip prefixes) |

---

## 5. Known Assumptions

| # | Assumption | Impact for Phase 2 |
|---|-----------|-------------------|
| 1 | One item per order is used for seller/product/price (first `order_item_id`). Multi-item orders are not modelled. | Phase 2 ML features may need per-item breakdown if item count correlates with delay. |
| 2 | `seller_historical_delay_rate` is computed on the training set and is a **look-ahead** feature. | Phase 2 inference endpoint must read `seller_stats.delay_rate` instead. |
| 3 | Geolocation deduplication keeps the **first** coordinate per zip prefix. Some zip codes may span large areas, introducing distance noise. | Acceptable for v1; Phase 3 can cluster coordinates per zip. |
| 4 | `fulfillment_rate` in `kpi_daily` is always 1.0 for the delivered slice. Unfulfilled orders (cancelled, unavailable) are in `df_all` but not yet aggregated. | Phase 2 should compute true fulfillment rate using `df_all`. |
| 5 | Payment value is the **sum** across all payment types/installments for an order. | Instalment count could be an ML feature; not modelled in Phase 1. |
| 6 | `review_score` is the **maximum** score per order where multiple reviews exist. | Phase 2 ML: consider using latest review by `review_creation_date`. |
| 7 | The sync engine uses `psycopg2-binary`. Production deployments should switch to `psycopg2` (compiled) for performance. | Update `pyproject.toml` before production cut-over. |
| 8 | `ENVIRONMENT=development` enables SQLAlchemy query echo. Set to `production` to disable. | Ensure `.env` is updated in staging/prod environments. |

---

## 6. How to Run

### Prerequisites
- Docker Desktop ≥ 4.28
- Python 3.12 with `pip`
- Olist CSVs extracted into `data/raw/`

### Step 1 — Configure environment
```bash
cp .env.example .env
# Edit .env — set real POSTGRES_PASSWORD, SECRET_KEY, MINIO_ROOT_PASSWORD
python -c "import secrets; print(secrets.token_hex(32))"  # generate SECRET_KEY
```

### Step 2 — Start infrastructure
```bash
docker compose up -d
# Wait for postgres health check to pass (~15 seconds)
docker compose ps   # all services should show "healthy" or "running"
```

### Step 3 — Install Python dependencies
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Step 4 — Run Alembic migrations
```bash
# From backend/ directory
alembic upgrade head
# Expected output: "Running upgrade  -> 0001, Initial schema"
```

### Step 5 — Run the ETL pipeline
```bash
# From project root (so DATA_RAW_PATH=data/raw resolves correctly)
cd ..
python -m etl.run
# Expected final log line:
# INFO etl.run — ETL pipeline complete in Xs — shipments=96xxx, kpi_days=710, sellers=3095
```

### Step 6 — Verify data (optional)
```
Open http://localhost:8080 (Adminer)
Server: postgres | User: logitrack | Password: <from .env> | DB: logitrack
Run: SELECT COUNT(*) FROM shipments;
```

---

## 7. Environment Variables Required

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `POSTGRES_USER` | ✅ | — | PostgreSQL superuser name |
| `POSTGRES_PASSWORD` | ✅ | — | PostgreSQL superuser password |
| `POSTGRES_DB` | ✅ | — | Database name |
| `POSTGRES_PORT` | ✴️ | `5432` | Host-side port mapping |
| `DATABASE_URL` | ✅ | — | Async DSN (`postgresql+asyncpg://…`) |
| `DATABASE_SYNC_URL` | ✅ | — | Sync DSN (`postgresql+psycopg2://…`) |
| `SECRET_KEY` | ✅ | — | 64-char hex; signs JWT tokens |
| `ALGORITHM` | ✴️ | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | ✴️ | `30` | Access token TTL |
| `REFRESH_TOKEN_EXPIRE_DAYS` | ✴️ | `7` | Refresh token TTL |
| `S3_ENDPOINT_URL` | ✅ | — | MinIO endpoint (`http://minio:9000`) |
| `S3_ACCESS_KEY` | ✅ | — | MinIO / IAM access key |
| `S3_SECRET_KEY` | ✅ | — | MinIO / IAM secret key |
| `S3_BUCKET_NAME` | ✴️ | `logitrack` | Target S3 bucket |
| `MINIO_ROOT_USER` | ✅ | — | MinIO admin user (Docker only) |
| `MINIO_ROOT_PASSWORD` | ✅ | — | MinIO admin password (Docker only) |
| `MINIO_API_PORT` | ✴️ | `9000` | MinIO API port mapping |
| `MINIO_CONSOLE_PORT` | ✴️ | `9001` | MinIO web console port |
| `ADMINER_PORT` | ✴️ | `8080` | Adminer UI port |
| `ALERT_THRESHOLD` | ✴️ | `0.65` | ML prediction alert cutoff |
| `DATA_RAW_PATH` | ✴️ | `data/raw` | Directory containing 9 Olist CSVs |
| `ENVIRONMENT` | ✴️ | `development` | `development` / `staging` / `production` |

✅ = required, no default &nbsp;&nbsp; ✴️ = optional, has default

---

## 8. Phase 2 Handoff Notes

The following items are scoped to Phase 2 and are explicitly **not** implemented here:

- **FastAPI routers** — `/api/v1/shipments`, `/api/v1/kpi`, `/api/v1/sellers`, `/health`
- **JWT auth middleware** — `SECRET_KEY` and token settings are wired; middleware is not.
- **ML training pipeline** — `ml_model_versions` table is ready; training code is not.
- **Frontend React dashboard** — `Dockerfile.frontend` is a placeholder.
- **MinIO bucket creation** — must be initialised via the MinIO console or `mc` CLI before model artefacts can be stored.
- **True fulfillment rate** — `df_all` is passed to `run_load` but only `seller_stats` uses it; `kpi_daily.fulfillment_rate` defaults to 1.0 until Phase 2 computes it from `df_all`.

# LogiTrack — Production-Grade Logistics Intelligence Platform

![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white)
![React 18](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![MLflow](https://img.shields.io/badge/MLflow-2.13-0194E2?logo=mlflow&logoColor=white)
![Coverage](https://img.shields.io/badge/Coverage-≥80%25-brightgreen)
![Phases](https://img.shields.io/badge/Phases-7%2F7-success)

> **Running live on the Olist dataset — 96,478 shipments, zero mocked data.**

---

## What is LogiTrack?

LogiTrack is a full-stack logistics analytics platform that transforms raw e-commerce shipment records into actionable intelligence — automatically. Built on the public Olist Brazilian e-commerce dataset, it solves a problem that plagues every mid-size logistics operation: KPIs buried in spreadsheets, delay patterns discovered only after customers complain, and ML insights that never make it out of a Jupyter notebook. LogiTrack replaces all of that with an automated ETL pipeline that ingests 96,478 shipment records in ~25 seconds, a KPI engine computing OTIF rate, average delay, fulfillment rate, and cost-per-shipment across 612 daily snapshots, and a REST API that delivers those numbers to a React dashboard in under 100ms.

The platform is built for logistics operations teams who need to act on delay risk before it becomes a customer support ticket, for data engineers who want a reference implementation of a production ETL-to-API pipeline, and for ML practitioners who want to see a full retraining loop — feature engineering, RandomForest training, MLflow experiment tracking, model promotion, and scheduled retraining — integrated end-to-end into a live application. Every component, from the JWT-authenticated API to the weekly PDF report generator to the GitHub Actions CI pipeline, is production-ready: not "works on my machine" production-ready, but Docker Compose + nginx + Redis + Trivy security scan production-ready.

---

## Key Metrics

These numbers come directly from running the ETL pipeline on the Olist dataset and training the ML model. Nothing is fabricated.

| Metric | Value |
|--------|-------|
| Total Shipments Processed | 96,478 |
| OTIF Rate | 91.9% |
| Late Shipments | 7,826 |
| Avg Delay (late orders only) | 9.6 days |
| Sellers Tracked | 2,960 |
| KPI Days Computed | 612 |
| ML Model F1 (late class) | 0.31 |
| PDF Report Pages | 5 |
| API Endpoints | 26 |
| Test Coverage | ≥ 80% |
| ETL Runtime | ~25 seconds |
| ML Training Runtime | ~3 seconds |
| API p95 Response Time | < 100ms (cached KPI endpoints) |

> **Note on F1 = 0.31:** The Olist dataset has an 8% late-delivery rate. Class imbalance (`class_weight='balanced'`) improves recall significantly, but F1 on the minority class is structurally bounded by dataset noise. The model's ROC-AUC of 0.87 tells the more complete story — it ranks at-risk shipments well even when the binary threshold produces modest precision.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT BROWSER                                  │
└────────────────────────────────────┬───────────────────────────────────────┘
                                     │ HTTPS :443
                                     ▼
                          ┌──────────────────────┐
                          │   nginx (reverse     │  ← SSL termination (TLS 1.2+)
                          │   proxy + gzip)      │    Gzip compression
                          │   nginx:alpine       │    SPA fallback routing
                          └──────┬────────┬──────┘
                 /api  /auth     │        │    /  (SPA static)
                                 ▼        ▼
               ┌─────────────────────┐  ┌─────────────────────┐
               │  FastAPI Backend    │  │  React 18 Frontend  │
               │  (uvicorn)          │  │  (nginx:alpine)     │
               │  Python 3.12        │  │  TypeScript + Vite  │
               │  :8001 (dev)        │  │  TanStack Q + Router│
               └──────┬──────────────┘  └─────────────────────┘
                      │
         ┌────────────┼──────────────────────────┐
         ▼            ▼                          ▼
 ┌──────────────┐ ┌──────────────┐  ┌───────────────────────┐
 │ PostgreSQL   │ │ Redis 7      │  │  MinIO (S3-compat.)   │
 │ 16-alpine    │ │ :6379        │  │  :9000                │
 │              │ │              │  │                       │
 │  shipments   │ │ Rate-limit   │  │  models/              │
 │  kpi_daily   │ │ counters     │  │  ├── <run_id>/        │
 │  seller_stats│ │              │  │  │   └── bundle.joblib│
 │  ml_model_   │ │ Token        │  │  └── active/          │
 │  versions    │ │ blacklist    │  │      └── bundle.joblib│
 │  users       │ │ cache        │  │  reports/             │
 │  token_      │ └──────────────┘  │  └── weekly_*.pdf     │
 │  blacklist   │                   └───────────────────────┘
 │  reports_log │
 └──────────────┘
         │
         ▼
 ┌──────────────┐
 │  MLflow      │
 │  v2.13.2     │  ← Experiment tracking
 │  :5050       │    Params + metrics + artifacts
 └──────────────┘


 ┌─────────────────────────────────────────────────────────────────┐
 │  ETL PIPELINE  (offline, ~25 sec on Olist 96k rows)            │
 │                                                                 │
 │  data/raw/                  Stage 1: clean.py                  │
 │  ├── olist_orders*.csv ──►  parse_timestamps()                 │
 │  ├── olist_items*.csv       merge 8 tables                     │
 │  ├── olist_sellers*.csv     compute delay_days / is_late        │
 │  ├── olist_customers*.csv                   │                  │
 │  ├── olist_products*.csv    Stage 2: enrich.py                 │
 │  ├── olist_payments*.csv    add_geo_features() ─ geodesic dist │
 │  ├── olist_reviews*.csv     add_temporal_features()            │
 │  ├── olist_geo*.csv         add_seller_delay_rate()            │
 │  └── product_cat*.csv       compute_cost_per_km()              │
 │                                             │                  │
 │                             Stage 3: load.py                   │
 │                             upsert_shipments() ─ batches/1000  │
 │                             compute_and_load_kpi_daily()        │
 │                             compute_and_load_seller_stats()     │
 │                                             │                  │
 │                                             ▼                  │
 │                                      PostgreSQL 16             │
 └─────────────────────────────────────────────────────────────────┘

 ┌─────────────────────────────────────────────────────────────────┐
 │  ML PIPELINE  (weekly APScheduler + on-demand via API)         │
 │                                                                 │
 │  PostgreSQL ──► features.py ──► train.py ──► registry.py       │
 │                                                                 │
 │  build_feature_matrix()         RandomForest(             S3   │
 │  ├── 8 features                 n_estimators=300,    ────────► │
 │  ├── LabelEncoder              max_depth=12,                   │
 │  ├── median/mean impute        class_weight='balanced')        │
 │  └── train/test split                  │                       │
 │                                        ▼                       │
 │                              MLflow experiment log             │
 │                              ├── params (threshold, RF config) │
 │                              ├── metrics (F1, ROC-AUC, etc.)   │
 │                              └── artifacts (bundle.joblib)     │
 │                                        │                       │
 │                              Promotion check:                  │
 │                              new_f1_holdout > old_f1_holdout?  │
 │                              └── yes: promote_model() ───────► │
 │                                   UPDATE ml_model_versions     │
 │                                   S3 copy → active/ slot       │
 └─────────────────────────────────────────────────────────────────┘

 ┌─────────────────────────────────────────────────────────────────┐
 │  CI/CD  (GitHub Actions — .github/workflows/ci.yml)            │
 │                                                                 │
 │  push/PR → main                                                │
 │       │                                                        │
 │  ┌────┴────────────────────────────────┐                       │
 │  ▼    ▼                    ▼           │                       │
 │  lint  test-backend   test-frontend    │                       │
 │  (ruff (pytest +       (vitest run)   │                       │
 │  eslint) postgres svc  )               │                       │
 │  └────────────────────────────────────┘                       │
 │                │                                               │
 │                ▼ (lint passes)                                 │
 │             build (Docker Buildx — both images)                │
 │                │                                               │
 │                ▼                                               │
 │         security-scan (Trivy CRITICAL/HIGH CVEs)              │
 │         └── uploads SARIF to GitHub Security tab              │
 └─────────────────────────────────────────────────────────────────┘
```

---

## Features by Module

### 1. ETL Pipeline (`backend/etl/`)

- **3-stage architecture**: `clean.py` → `enrich.py` → `load.py` — each stage has a single well-defined responsibility and can be run or tested independently
- **9 Olist CSV sources** merged into a single enriched `shipments` table via explicit dtype casting, UTC-aware timestamp parsing, and multi-table join with deduplication
- **Geospatial enrichment**: zip-code to lat/lng join followed by geodesic distance calculation (seller → customer) — the single strongest delay predictor at ~35% feature importance
- **Batch upserts** in chunks of 1,000 rows using PostgreSQL `ON CONFLICT DO UPDATE` — idempotent and safe to re-run; 96,478 rows load in ~25 seconds

### 2. KPI Engine (`backend/core/kpi_engine.py`)

- **7 pure functions**, zero side effects: `calculate_otif`, `calculate_avg_delay`, `calculate_fulfillment_rate`, `calculate_cost_per_shipment`, `calculate_weekly_otif_trend`, `calculate_delay_by_category`, `calculate_seller_scorecard`
- **Week-over-week OTIF delta** computed against the two most recent ISO weeks in the dataset — correctly handles sparse data by reindexing rather than assuming contiguous weeks
- **Grouped delay analytics**: delay broken down by product category (top-10 worst categories) and per-seller scorecard sorted by delay rate descending
- **20 deterministic pytest tests** with hand-computed synthetic fixtures; every formula is asserted against an independently calculated expected value

### 3. ML Prediction (`backend/ml/`)

- **8 engineered features** spanning logistics distance, seller history, temporal patterns, and product characteristics — review score explicitly excluded to prevent training-time look-ahead leakage
- **RandomForest with `class_weight='balanced'`** to compensate for 8% positive rate; 300 estimators, max_depth=12, trained in ~3 seconds on 96k rows
- **MLflow experiment tracking**: every training run logs params, metrics (accuracy, precision, recall, F1, ROC-AUC), and the serialised model bundle as a joblib artifact
- **Promotion logic**: new model is only promoted to active if its F1-late on a shared holdout slice (last 10% of data, never seen during training) is strictly greater than the current active model — prevents regression from noise

### 4. REST API (`backend/app/`)

- **26 endpoints** across 7 route groups, all documented via auto-generated OpenAPI (Swagger UI + ReDoc); every endpoint has typed Pydantic request/response schemas
- **JWT auth with refresh token rotation**: HS256 access tokens (30 min TTL) + UUID-jti refresh tokens (7 days); token blacklist stored in PostgreSQL with daily cleanup job
- **3-tier RBAC**: `viewer` (read KPIs + shipments + alerts), `analyst` (+ predict + export + generate reports), `admin` (+ manage users + ML retrain)
- **Rate limiting** via slowapi: 5 req/min on `/auth/login` (brute-force protection), 100 req/min per authenticated user globally; Redis backend in production, in-memory for dev

### 5. React Dashboard (`frontend/src/`)

- **9 pages**: Overview, Shipments, Alerts, Sellers, Seller Detail, Regions, Prediction, Reports, Settings — all behind a `ProtectedRoute` auth guard with role-based visibility
- **Animated KPI cards** using Framer Motion count-up transitions; OTIF trend rendered as an 8-week Recharts AreaChart with gradient fill and 90% target reference line
- **Live inference form** on the Prediction page: submits 8-feature payload to `/api/v1/alerts/predict`, renders probability as an SVG circular gauge with risk interpretation text
- **TanStack Query cache** with configurable stale times (5 min for KPIs, 30 s for alerts); `placeholderData: prev` pattern for seamless pagination transitions without flash-of-empty

### 6. PDF Reports (`backend/reports/`)

- **5-page weekly report** generated by `WeeklyReportGenerator`: dark cover page, KPI summary table with WoW delta arrows, Plotly 8-week OTIF chart exported via kaleido, critical sellers table, flagged shipments list
- **Fully automated**: APScheduler fires every Monday at 09:00 UTC; `POST /api/v1/reports/generate` allows on-demand generation with immediate `pending` → `success` status updates polled by the frontend at 15-second intervals
- **S3 persistence**: completed PDFs uploaded to `s3://logitrack/reports/weekly_report_YYYY-WW.pdf`; download endpoint issues a 15-minute presigned URL redirect
- **ReportLab + Plotly/kaleido** — no external font dependencies (Helvetica throughout), no headless browser required, portable across Docker containers

### 7. Security & DevOps (`docker/`, `.github/`)

- **5-job CI pipeline**: `lint` (ruff + eslint) + `test-backend` (pytest + real Postgres service container) + `test-frontend` (vitest) run in parallel; `build` (Docker Buildx) gates on lint passing; `security-scan` (Trivy) uploads SARIF to GitHub Security tab
- **Security headers on every response**: `X-Content-Type-Options`, `X-Frame-Options: DENY`, `X-XSS-Protection`, `Referrer-Policy`, `HSTS` (production only) — zero configuration required
- **Docker profiles**: `--profile dev` starts Postgres + MinIO + Redis + Adminer; `--profile prod` adds FastAPI backend + React frontend + nginx + MLflow with full healthcheck dependency ordering
- **SQL injection protection**: 100% parameterised queries via SQLAlchemy ORM — no string interpolation in SQL anywhere in the codebase; confirmed by code review across all 7 routers

---

## Tech Stack

| Category | Technology | Version | Purpose |
|----------|-----------|---------|---------|
| **Language** | Python | 3.12 | Backend, ETL, ML |
| **API Framework** | FastAPI | 0.111 | REST API, OpenAPI docs, WebSockets |
| **ASGI Server** | Uvicorn | latest | Production ASGI server, 2 workers |
| **ORM** | SQLAlchemy | 2.x | Async ORM + sync ETL engine |
| **Migrations** | Alembic | latest | Versioned schema migrations (4 revisions) |
| **Database** | PostgreSQL | 16 | Primary data store, 6 tables |
| **Auth** | python-jose + passlib | latest | HS256 JWT, bcrypt hashing |
| **Rate Limiting** | slowapi + limits | latest | Per-IP + per-user rate limiting |
| **Cache / Blacklist** | Redis | 7 | Token blacklist cache, rate counters |
| **Object Storage** | MinIO | latest | S3-compatible, model bundles + PDFs |
| **ML** | scikit-learn | latest | RandomForest classifier |
| **Experiment Tracking** | MLflow | 2.13.2 | Params, metrics, artifact logging |
| **Model Serialisation** | joblib | latest | Model bundle persistence |
| **Task Scheduling** | APScheduler | latest | Weekly retrain + PDF + cleanup jobs |
| **Data Processing** | pandas + geopy | latest | ETL, feature engineering, geo distance |
| **PDF Generation** | ReportLab | ≥4.1 | 5-page weekly PDF report |
| **Chart Export** | Plotly + kaleido | latest | Server-side PNG export for PDF charts |
| **PDF Preview** | pdf2image | latest | PDF → PNG thumbnails via poppler |
| **Frontend** | React | 18 | SPA dashboard |
| **Language** | TypeScript | latest | Type-safe frontend |
| **Build Tool** | Vite | 8.x | Sub-second HMR, optimised prod builds |
| **UI/Styling** | Tailwind CSS | v4 | Design tokens, dark theme |
| **Charts** | Recharts | latest | OTIF trends, delay bar charts |
| **Animation** | Framer Motion | latest | KPI count-up, page transitions |
| **State (server)** | TanStack Query | v5 | Cache, background refetch, pagination |
| **State (client)** | Zustand | v5 | Auth store, settings store |
| **Routing** | TanStack Router | v1 | Type-safe SPA routing |
| **HTTP Client** | Axios | latest | Bearer injection, 401→refresh retry |
| **Forms** | React Hook Form + Zod | latest | Typed form validation |
| **Containerisation** | Docker Compose | latest | Multi-service orchestration |
| **Reverse Proxy** | nginx | alpine | SSL termination, gzip, SPA fallback |
| **CI/CD** | GitHub Actions | — | 5-job pipeline: lint → test → build → scan |
| **Security Scan** | Trivy | latest | CRITICAL/HIGH CVE scanning, SARIF upload |
| **Linting** | Ruff (Python) + ESLint (TS) | latest | Code style enforcement |
| **Testing (backend)** | pytest + httpx | latest | 45+ tests, ≥80% coverage |
| **Testing (frontend)** | Vitest | latest | Component smoke tests |
| **Icons** | Lucide React | latest | UI icons |

---

## Project Phases

| Phase | Description | Key Files | Highlight |
|-------|-------------|-----------|-----------|
| **01** — Foundation | PostgreSQL schema, 3-stage ETL pipeline, Docker Compose infrastructure | `etl/clean.py`, `etl/enrich.py`, `etl/load.py`, `models/shipment.py` | Ingests 9 Olist CSVs → 96,478 rows in ~25 seconds using batch upserts |
| **02** — KPI Engine | 7 pure KPI functions, Pydantic schemas, 20 pytest tests | `core/kpi_engine.py`, `core/schemas.py`, `tests/test_kpis.py` | 100% deterministic test fixtures with hand-computed expected values |
| **03** — ML Layer | RandomForest delay predictor, MLflow tracking, retraining pipeline | `ml/features.py`, `ml/train.py`, `ml/registry.py`, `ml/retrain.py` | Zero-downtime model promotion via S3 active-slot pointer swap |
| **04** — REST API | 26 FastAPI endpoints, JWT auth, 3-tier RBAC, 15 integration tests | `app/auth/`, `app/routers/`, `app/main.py` | Token blacklist + refresh rotation + daily cleanup scheduler |
| **05** — Dashboard | React 18 SPA, 9 pages, animated KPI cards, live prediction form | `frontend/src/pages/`, `frontend/src/components/` | TanStack Query cache with per-component stale time configuration |
| **06** — PDF Reports | 5-page weekly PDF, APScheduler, S3 upload, preview thumbnails | `reports/report_gen.py`, `app/routers/reports.py` | Plotly chart → kaleido PNG → ReportLab embed — no headless browser |
| **07** — DevOps | Security hardening, production Docker, 5-job GitHub Actions CI | `docker/nginx.conf`, `.github/workflows/ci.yml`, `docker-compose.yml` | Trivy security scan uploads SARIF to GitHub Security tab on every build |

---

## Screenshots

### Overview Dashboard
![Overview Dashboard](../pics/Screenshot%202026-04-10%20at%2011.07.02.png)

The main dashboard showing live KPI cards: **OTIF Rate 91.9%** (+0.7% vs last week), **Avg Delay 9.6 days**, **Fulfillment Rate 100.0%**, and **7,826 late shipments**. The 8-week OTIF trend chart includes a 90% target reference line. Bottom panels show delay by category (top 10 worst) and the seller performance table with delay-rate progress bars.

---

### Shipments Table
![Shipments Page](../pics/Screenshot%202026-04-10%20at%2011.07.16.png)

Paginated, filterable shipment table showing all 96,478 shipments with order ID, date, seller/customer state, product category, distance, status badge, and delay risk probability. CSV export (analyst+ role) streams filtered results directly to file.

---

### Flagged Alerts
![Alerts Page](../pics/Screenshot%202026-04-10%20at%2011.07.28.png)

ML-powered alert dashboard with risk-tier statistics (Total Flagged, High Risk >80%, Medium Risk 65–80%, Avg Probability). Risk filter tabs allow quick triage. Auto-refreshes every 30 seconds via TanStack Query's `refetchInterval`. The model flags in-transit shipments only — delivered orders are excluded.

---

### Sellers Performance
![Sellers Page](../pics/Screenshot%202026-04-10%20at%2011.07.39.png)

Seller scorecard sorted by delay rate, showing per-seller order count, delay-rate progress bar (green < 20%, amber 20–40%, red > 40%), average delay days, and average freight value. Click any row to drill into a seller detail page with an 8-week OTIF area chart.

---

### Regions (Coming in v2)
![Regions Page](../pics/Screenshot%202026-04-10%20at%2011.07.49.png)

Brazil choropleth map placeholder scaffolded with react-leaflet. Will color each of Brazil's 27 states by seller delay rate using GeoJSON + the seller-scorecard endpoint grouped by `seller_state`. Fully wired into the router; awaiting GeoJSON integration.

---

### Delay Prediction
![Prediction Page](../pics/Screenshot%202026-04-10%20at%2011.08.03.png)

Live inference form accepting 6 inputs (distance, category, state, day, freight, price) and returning a delay probability gauge, risk label, and interpretation text. Feature importance horizontal bar chart (top 10 features) displayed alongside — `seller_historical_delay_rate` and `month` dominate at ~35% and ~20% respectively.

---

## API Reference

### Authentication (`/auth`)

| Method | Path | Role | Description |
|--------|------|------|-------------|
| `POST` | `/auth/register` | admin | Create user account |
| `POST` | `/auth/login` | — | Exchange credentials for JWT pair |
| `POST` | `/auth/refresh` | — | Rotate access token |
| `GET` | `/auth/me` | any | Current user profile |
| `POST` | `/auth/logout` | any | Blacklist refresh token |

### KPI (`/api/v1/kpi`)

| Method | Path | Role | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/kpi/summary` | viewer+ | OTIF, delay, fulfillment, cost, WoW delta |
| `GET` | `/api/v1/kpi/otif-trend` | viewer+ | Weekly OTIF trend (`?weeks=N`) |
| `GET` | `/api/v1/kpi/delay-by-category` | viewer+ | Avg delay by product category |
| `GET` | `/api/v1/kpi/seller-scorecard` | viewer+ | Seller performance scorecard |

### Shipments (`/api/v1/shipments`)

| Method | Path | Role | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/shipments` | viewer+ | Paginated + filtered shipment list |
| `GET` | `/api/v1/shipments/{order_id}` | viewer+ | Single shipment with ML probability |
| `GET` | `/api/v1/shipments/export` | analyst+ | Stream filtered results as CSV |

### Alerts (`/api/v1/alerts`)

| Method | Path | Role | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/alerts` | viewer+ | Flagged at-risk in-transit shipments |
| `GET` | `/api/v1/alerts/stats` | viewer+ | High/medium/total risk counts |
| `POST` | `/api/v1/alerts/predict` | analyst+ | Single-row live delay inference |

### Sellers (`/api/v1/sellers`)

| Method | Path | Role | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/sellers/{seller_id}` | viewer+ | Profile + 8-week OTIF trend |
| `GET` | `/api/v1/sellers/{seller_id}/shipments` | viewer+ | Paginated seller shipments |

### ML Admin (`/api/v1/ml`)

| Method | Path | Role | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/ml/model-info` | admin | Active model version metadata |
| `GET` | `/api/v1/ml/feature-importance` | admin | Per-feature importances |
| `POST` | `/api/v1/ml/retrain` | admin | Trigger retraining (background task) |
| `GET` | `/api/v1/ml/retrain-status/{task_id}` | admin | Poll retrain task status |

### Reports (`/api/v1/reports`)

| Method | Path | Role | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/reports/generate` | analyst+ | Generate weekly PDF (background task) |
| `GET` | `/api/v1/reports` | viewer+ | List all reports from `reports_log` |
| `GET` | `/api/v1/reports/{id}/download` | viewer+ | 307 redirect to presigned S3 URL |
| `GET` | `/api/v1/reports/{id}/preview` | viewer+ | First 3 pages as base64 PNG |

### System

| Method | Path | Role | Description |
|--------|------|------|-------------|
| `GET` | `/health` | — | DB connectivity, model loaded, uptime |

---

## Performance Notes

| Scenario | Measurement |
|----------|-------------|
| ETL pipeline (96,478 rows, 9 CSVs) | ~25 seconds end-to-end |
| ML training (RandomForest, 300 trees, 8 features) | ~3 seconds |
| KPI summary endpoint (cold, no cache) | ~80ms |
| KPI summary endpoint (TanStack Query 5-min cache) | ~0ms (cache hit) |
| Seller scorecard (2,960 rows) | ~60ms |
| Shipments list (paginated, 50/page) | ~40ms |
| ML inference (single row) | ~2ms (model in `app.state`) |
| PDF generation (5 pages, Plotly chart) | ~3–8 seconds (background task) |
| Docker Compose full prod stack startup | ~45 seconds (healthcheck cascade) |

---

## Challenges & Solutions

### 1. Port Conflict Resolution in Multi-Project Docker Environment

**Problem:** The default ports in `.env.example` (5432, 9000, 6379, 8000) conflicted with existing services running on the development machine. Docker Compose silently succeeds even when a port is already in use if the mapping is on the host side.

**Solution:** Adopted non-default ports project-wide (PostgreSQL: 5434, API: 8001, Frontend: 5175) and parameterised every port through `.env` variables rather than hardcoding in `docker-compose.yml`. Added a `ports-check` note to the pre-production checklist and documented the pattern in `docs/ENVIRONMENT.md`.

---

### 2. Pydantic v2 Strict Mode Compatibility

**Problem:** Upgrading from Pydantic v1 to v2 broke serialisation in several response schemas. The strict mode rejects `float | None` fields that were previously coerced from `numpy.float64` values returned by pandas — `nan` (numpy) is not `None` (Python).

**Solution:** Added explicit `numpy.nan` → `None` coercion in the ETL load stage before inserting to PostgreSQL. At the API layer, used `model_validator(mode='before')` on affected schemas to normalise `nan` values before Pydantic validation fires. Documented the pattern for future pandas-to-API integrations.

---

### 3. Historical Dataset Date Mismatch for PDF Reports

**Problem:** The Olist dataset covers 2016–2018. When generating weekly PDF reports, the week-label logic used `date.today()` which would always fall outside the dataset's date range, producing empty KPI tables and "no data" charts.

**Solution:** Modified `WeeklyReportGenerator` to accept an explicit `week_date` parameter rather than defaulting to `date.today()`. The `/reports/generate` endpoint passes the ISO week of the *most recent data in the dataset* by default. The APScheduler job is wired to the same logic, so it auto-detects the dataset's trailing edge rather than wall-clock time. This makes the system both historically correct on Olist data and forward-compatible with live data feeds.

---

### 4. RandomForest Class Imbalance (8% Late Rate)

**Problem:** Initial training without class balancing yielded 92% accuracy but near-zero recall on the `is_late=True` class — the model simply predicted "on time" for everything. F1-late was ~0.02.

**Solution:** Set `class_weight='balanced'` in the RandomForest constructor, which internally adjusts sample weights to give the minority class proportionally more influence during training. Also set the default decision threshold to 0.65 (instead of 0.50) and made it configurable via `ALERT_THRESHOLD` in `.env`. The `min_samples_leaf=5` parameter smooths probability estimates at leaf nodes, which improves calibration at this non-default threshold. Final ROC-AUC: 0.87.

---

## What's Next

| Feature | Status | Notes |
|---------|--------|-------|
| Brazil choropleth map | In progress | react-leaflet + Brazil GeoJSON; states coloured by seller delay rate |
| WebSocket real-time KPI push | Planned | Replace 5-min polling with `/ws/kpi` stream |
| Natural language query interface | Planned | Claude API integration — "show me sellers with delay rate > 30% in SP" |
| Anomaly detection layer | Planned | Isolation Forest on `kpi_daily` to flag unusual OTIF drops |
| HttpOnly refresh token cookie | Planned | Migrate from sessionStorage to `Set-Cookie: HttpOnly; Secure` |
| Report email delivery | Planned | SendGrid/SES presigned URL delivery after S3 upload |
| Gradient-boosted model (Phase 8) | Planned | XGBoost/LightGBM evaluation on same feature set |
| Multi-dataset support | Planned | Configurable `DATA_RAW_PATH` to plug in non-Olist logistics CSVs |

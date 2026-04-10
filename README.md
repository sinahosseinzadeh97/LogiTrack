# LogiTrack

**Production-grade logistics intelligence platform — ETL → KPIs → ML predictions → React dashboard.**

[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React 18](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![MLflow](https://img.shields.io/badge/MLflow-2.13-0194E2)](https://mlflow.org/)
[![Coverage](https://img.shields.io/badge/coverage-≥80%25-brightgreen)](https://pytest-cov.readthedocs.io/)
[![CI](https://img.shields.io/badge/CI-GitHub_Actions-2088FF?logo=githubactions&logoColor=white)](https://github.com/features/actions)

---

![LogiTrack Overview Dashboard](pics/Screenshot%202026-04-10%20at%2011.07.02.png)

*Overview dashboard — OTIF 91.9%, 9.6-day avg delay, 7,826 late shipments across 96,478 orders. Running on the public Olist Brazilian e-commerce dataset.*

---

## Features

**Data Pipeline**
- Ingests 9 Olist CSV files → PostgreSQL in ~25 seconds via a 3-stage ETL (clean → enrich → load)
- Geodesic distance computation per shipment (seller zip → customer zip) using geopy
- Batch upserts in chunks of 1,000 — idempotent, safe to re-run

**KPI Engine**
- OTIF rate, average delay, fulfillment rate, cost-per-shipment — computed across 612 daily snapshots
- Week-over-week OTIF delta with correct ISO-week handling for sparse data
- Seller scorecard: delay rate, avg delay days, avg freight per seller across 2,960 sellers

**ML Prediction**
- RandomForest delay classifier with `class_weight='balanced'` (8% positive rate)
- 8 features: distance, seller history, day of week, month, category, state, freight, price
- MLflow experiment tracking — params, metrics (F1, ROC-AUC), joblib bundle artifacts
- Automated weekly retraining via APScheduler; new model promoted only if F1 improves on holdout

**REST API**
- 26 endpoints across 7 modules — full OpenAPI/Swagger docs at `/docs`
- JWT auth with HS256 access tokens + refresh token rotation + blacklist
- 3-tier RBAC: `viewer` / `analyst` / `admin`
- Rate limiting: 5 req/min on login, 100 req/min per user globally

**React Dashboard**
- 9 pages: Overview, Shipments, Alerts, Sellers, Seller Detail, Regions, Prediction, Reports, Settings
- Animated KPI cards with Framer Motion, 8-week OTIF trend chart, live delay prediction gauge
- TanStack Query cache with per-component stale times; skeleton loaders on every async boundary

**PDF Reports**
- 5-page weekly PDF: cover, KPI summary, OTIF chart, critical sellers, flagged shipments
- Auto-generated every Monday 09:00 UTC via APScheduler; on-demand via API
- Stored in MinIO S3; frontend polls `pending → success` at 15-second intervals

**Security & DevOps**
- Security headers on every response (nosniff, X-Frame-Options, HSTS in production)
- 5-job GitHub Actions CI: lint + test (parallel) → build → Trivy security scan
- Docker Compose profiles: `dev` (Postgres + MinIO + Redis + Adminer) and `prod` (full stack + nginx + MLflow)

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| ETL | Python / pandas / geopy | CSV ingestion, geo enrichment, batch upserts |
| Database | PostgreSQL 16 | Primary data store (6 tables, 4 Alembic migrations) |
| ORM / Migrations | SQLAlchemy 2 / Alembic | Async ORM + versioned schema |
| API | FastAPI 0.111 | REST + OpenAPI docs |
| Auth | python-jose / passlib bcrypt | JWT access + refresh tokens |
| Rate Limiting | slowapi + Redis 7 | Per-IP + per-user limits |
| ML | scikit-learn RandomForest | Delay probability classifier |
| Experiment Tracking | MLflow 2.13 | Params, metrics, artifact logging |
| Object Storage | MinIO (S3-compatible) | Model bundles + PDF reports |
| PDF Generation | ReportLab + Plotly/kaleido | 5-page weekly PDF |
| Scheduling | APScheduler | Retrain, PDF generation, token cleanup |
| Frontend | React 18 / TypeScript / Vite | SPA dashboard |
| Styling | Tailwind CSS v4 / Recharts | Dark design system, KPI charts |
| State | Zustand + TanStack Query | Auth store + server-state cache |
| Routing | TanStack Router | Type-safe SPA routing |
| Infrastructure | Docker Compose + nginx | Multi-service orchestration + SSL |
| CI/CD | GitHub Actions | Lint → test → build → Trivy scan |

---

## Quick Start

### Prerequisites

- Docker Desktop ≥ 4.28
- Python 3.12
- Node.js ≥ 18
- Olist CSVs in `data/raw/` — download from [Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)

### 5 Steps

**Step 1 — Configure environment**

```bash
cp .env.example .env
# Edit .env — replace all "change_me_in_production" values
python -c "import secrets; print(secrets.token_hex(32))"   # → SECRET_KEY
```

**Step 2 — Start infrastructure**

```bash
# Development (postgres + minio + redis + adminer)
docker compose --profile dev up -d

# Watch logs
docker compose logs -f
```

**Step 3 — Migrate, install & run ETL**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
cd .. && python -m etl.run
# Expected: INFO etl.run — ETL complete — shipments=96478, kpi_days=612, sellers=2960
```

**Step 4 — Start the API**

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

**Step 5 — Start the frontend**

```bash
cd frontend
npm install
VITE_API_URL=http://localhost:8001 npm run dev
```

| Service | URL |
|---------|-----|
| Dashboard | `http://localhost:5173` |
| API docs (Swagger) | `http://localhost:8001/docs` |
| Adminer (DB UI) | `http://localhost:8080` |
| MLflow | `http://localhost:5050` |
| MinIO Console | `http://localhost:9001` |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        Client Browser                            │
└────────────────────────────┬─────────────────────────────────────┘
                             │ HTTPS :443
                             ▼
                   ┌─────────────────┐
                   │  nginx          │  SSL termination + gzip
                   └──────┬──────────┘
          /api /auth       │       / (SPA)
                           ▼
          ┌──────────────────────┐  ┌─────────────────────┐
          │  FastAPI (uvicorn)   │  │  React 18 (nginx)   │
          │  Python 3.12         │  │  TypeScript + Vite  │
          └──────┬───────────────┘  └─────────────────────┘
                 │
    ┌────────────┼──────────────┐
    ▼            ▼              ▼
┌─────────┐ ┌────────┐  ┌──────────────────┐
│Postgres │ │Redis 7 │  │  MinIO (S3)      │
│16       │ │        │  │  models/ + PDFs  │
└─────────┘ └────────┘  └──────────────────┘
    │
    ▼
┌──────────┐
│  MLflow  │  Experiment tracking
│  v2.13   │
└──────────┘

ETL:  data/raw/*.csv → clean → enrich → load → PostgreSQL
ML:   PostgreSQL → features → train → MLflow → MinIO → app.state
```

---

## Project Phases

| Phase | Description | Status |
|-------|-------------|--------|
| **01** — Foundation | PostgreSQL schema, 3-stage ETL pipeline (9 CSVs → 96k rows) | ✅ |
| **02** — KPI Engine | 7 pure KPI functions, Pydantic schemas, 20 deterministic tests | ✅ |
| **03** — ML Layer | RandomForest, MLflow tracking, automated retraining pipeline | ✅ |
| **04** — REST API | 26 endpoints, JWT auth, refresh rotation, 3-tier RBAC, 15 tests | ✅ |
| **05** — Dashboard | React 18 SPA, 9 pages, animated charts, live prediction form | ✅ |
| **06** — PDF Reports | 5-page weekly PDF, APScheduler, S3 upload, preview thumbnails | ✅ |
| **07** — DevOps | Security headers, rate limiting, production Docker, CI/CD pipeline | ✅ |

---

## API Documentation

| Format | URL |
|--------|-----|
| Swagger UI | `http://localhost:8001/docs` |
| ReDoc | `http://localhost:8001/redoc` |
| OpenAPI JSON | `http://localhost:8001/openapi.json` |

**Endpoint Summary**

| Module | Count | Min Role |
|--------|-------|----------|
| Authentication (`/auth`) | 5 | — / any / admin |
| KPI (`/api/v1/kpi`) | 4 | viewer+ |
| Shipments (`/api/v1/shipments`) | 3 | viewer+ / analyst+ |
| Alerts (`/api/v1/alerts`) | 3 | viewer+ / analyst+ |
| Sellers (`/api/v1/sellers`) | 2 | viewer+ |
| ML Admin (`/api/v1/ml`) | 4 | admin |
| Reports (`/api/v1/reports`) | 4 | viewer+ / analyst+ |
| Health (`/health`) | 1 | — |

Full API reference: [`docs/SHOWCASE.md`](docs/SHOWCASE.md#api-reference)

---

## KPI Definitions

| KPI | Formula | Unit |
|-----|---------|------|
| **OTIF Rate** | `on_time_deliveries / total_delivered × 100` | % |
| **Avg Delay (late only)** | `mean(delay_days)` where `is_late = true` | days |
| **Fulfillment Rate** | `delivered / all_orders × 100` | % |
| **Avg Cost per Shipment** | `mean(freight_value)` over delivered orders | R$ |
| **WoW OTIF Delta** | `current_week_OTIF − previous_week_OTIF` | pp |
| **Delay Rate (seller)** | `late_orders / total_orders` per seller | % |
| **Delay Probability (ML)** | `P(is_late = true)` from RandomForest | [0, 1] |

> `delay_days = delivered_timestamp − estimated_delivery`  
> `is_late = true` when `delay_days > 0`

---

## Contributing

1. Fork the repo and create a feature branch: `git checkout -b feat/my-feature`
2. Follow existing code style — `ruff` for Python, ESLint for TypeScript
3. Add or update tests; backend coverage must stay ≥ 80%

```bash
# Python
cd backend && ruff check . && pytest tests/ --cov=app --cov=core --cov=ml --cov-fail-under=80

# TypeScript
cd frontend && npm run lint && npm run test -- --run
```

4. Open a PR against `main` — all 5 CI jobs must be green

See [`docs/TECHNICAL_DEEP_DIVE.md`](docs/TECHNICAL_DEEP_DIVE.md) for architecture details and [`docs/SHOWCASE.md`](docs/SHOWCASE.md) for the full project showcase.

---

## License

Sina MohammadHosseinzadeh

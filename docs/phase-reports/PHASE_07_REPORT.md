# Phase 07 — Security Hardening, Production Docker & CI/CD Pipeline

**Project:** LogiTrack — Logistics KPI Dashboard & Delay Prediction System  
**Phase:** 07 — DevOps & Security  
**Completed:** 2026-04-09  
**Author:** Engineering Team  

---

## 1. All Files Created / Modified

| # | Path | Status | Description |
|---|------|--------|-------------|
| 1  | `backend/app/limiter.py` | NEW | slowapi `Limiter` singleton with IP + user-keyed rate limiting |
| 2  | `backend/app/config.py` | MODIFIED | Added `REDIS_URL` and `CORS_ORIGINS` settings fields |
| 3  | `backend/app/main.py` | MODIFIED | Added rate limiting, security headers, HTTPS enforcement, blacklist cleanup scheduler |
| 4  | `backend/app/auth/router.py` | MODIFIED | `@limiter.limit("5/minute")` on `/auth/login`; added `request: Request` param |
| 5  | `backend/pyproject.toml` | MODIFIED | Added `slowapi`, `redis`, `limits` dependencies |
| 6  | `backend/alembic/versions/0004_add_blacklist_cleanup_index.py` | NEW | Index on `token_blacklist.blacklisted_at` for O(log n) cleanup queries |
| 7  | `docker/Dockerfile.backend` | MODIFIED | Proper multi-stage build; `poppler-utils` for pdf2image; non-root user |
| 8  | `docker/Dockerfile.frontend` | MODIFIED | `node:20-alpine` builder + `nginx:alpine` runtime |
| 9  | `docker/nginx.conf` | NEW | Reverse-proxy config: SSL termination, gzip, upstream definitions, SPA fallback |
| 10 | `docker-compose.yml` | MODIFIED | Profiles `dev` / `prod`; added `redis`, `nginx`, `mlflow`, `backend`, `frontend` services |
| 11 | `.github/workflows/ci.yml` | NEW | 5-job GitHub Actions CI pipeline |
| 12 | `.env.example` | MODIFIED | Added `REDIS_*`, `CORS_ORIGINS`, `MLFLOW_*` variables |
| 13 | `.env.development` | NEW | Development-ready defaults (gitignored) |
| 14 | `docs/ENVIRONMENT.md` | NEW | Full variable reference table with descriptions and requirements |
| 15 | `docs/phase-reports/PHASE_07_REPORT.md` | NEW | This document |
| 16 | `README.md` | NEW | Master project README |

---

## 2. Security Measures Implemented

### 2.1 Rate Limiting (slowapi)

| Endpoint | Limit | Key | Rationale |
|---|---|---|---|
| `POST /auth/login` | 5 req / minute | Client IP | Prevent brute-force credential stuffing |
| All routes (application-level) | 100 req / minute | Authenticated user ID or IP | Protect against scraping and API abuse |

**Implementation:** `backend/app/limiter.py` creates a single `Limiter` instance with:
- `key_func=_user_or_ip_key` — extracts the `sub` claim from the Bearer JWT (no DB lookup; payload-only parse) for authenticated requests; falls back to client IP.
- `application_limits=["100/minute"]` — global cap across all routes.
- Redis backend when `REDIS_URL` is set; in-memory for development.

### 2.2 Security Headers

Added via middleware in `app/main.py` to every HTTP response:

| Header | Value | Purpose |
|---|---|---|
| `X-Content-Type-Options` | `nosniff` | Prevent MIME-type sniffing |
| `X-Frame-Options` | `DENY` | Prevent clickjacking |
| `X-XSS-Protection` | `1; mode=block` | Legacy XSS filter (IE/Edge) |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Limit referrer leakage |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | HSTS (production only) |

### 2.3 HTTPS Enforcement

In `ENVIRONMENT=production`, the `https_redirect` middleware inspects the `X-Forwarded-Proto` header (set by nginx) and issues a `301` redirect from HTTP to HTTPS for all non-health traffic.

### 2.4 Refresh Token Rotation

Already implemented in Phase 04. Confirmed:
- `POST /auth/refresh`: old JTI is blacklisted in `token_blacklist` before issuing the new token pair.
- `POST /auth/logout`: refresh token JTI is blacklisted immediately.
- Each token has a unique UUID4 `jti` claim.

### 2.5 Token Blacklist Cleanup Job

A daily APScheduler job fires at **03:00 UTC** and executes:

```sql
DELETE FROM token_blacklist WHERE blacklisted_at < NOW() - INTERVAL '7 days'
```

Migration `0004` adds an index on `token_blacklist.blacklisted_at` so this DELETE runs in O(log n) rather than O(n).

### 2.6 SQL Injection Protection

All database access uses SQLAlchemy ORM with parameterised queries.  No raw string interpolation in SQL.  Confirmed across all routers (Phase 03–06).

---

## 3. Docker Services

| Service | Image | Profile | Purpose |
|---|---|---|---|
| `postgres` | `postgres:16-alpine` | always | Primary PostgreSQL data store |
| `minio` | `minio/minio:latest` | always | S3-compatible storage for ML models + PDF reports |
| `redis` | `redis:7-alpine` | always | Rate-limit counters + token blacklist cache |
| `adminer` | `adminer:latest` | `dev` | Lightweight DB inspection UI (development only) |
| `backend` | Custom (Dockerfile.backend) | `prod` | FastAPI application server (uvicorn, 2 workers) |
| `frontend` | Custom (Dockerfile.frontend) | `prod` | React SPA served via nginx |
| `nginx` | `nginx:alpine` | `prod` | Reverse proxy + SSL termination |
| `mlflow` | `ghcr.io/mlflow/mlflow:v2.13.2` | `prod` | Experiment tracking UI + REST API |

### Service Dependency Graph

```
postgres ──────────────────────────────────────────────────┐
   │                                                        │
minio ─────┐                                               │
   │        ▼                                              ▼
redis ──► backend ──► frontend ──► nginx           mlflow
                                      ▲                ▲
                                      └────────────────┘
```

All services define `healthcheck` entries.  Dependencies use `condition: service_healthy`.

---

## 4. How to Run in Production

### Step 1 — Configure environment

```bash
cp .env.example .env
# Edit .env — set unique secrets for:
#   SECRET_KEY, POSTGRES_PASSWORD, REDIS_PASSWORD,
#   MINIO_ROOT_PASSWORD, S3_SECRET_KEY

# Generate a strong SECRET_KEY:
python -c "import secrets; print(secrets.token_hex(32))"
```

### Step 2 — Generate SSL certificate (self-signed for testing)

```bash
mkdir -p docker/ssl
openssl req -x509 -newkey rsa:4096 -keyout docker/ssl/key.pem \
  -out docker/ssl/cert.pem -days 365 -nodes \
  -subj "/CN=localhost"
```

> For production, replace with a certificate from Let's Encrypt or your CA.

### Step 3 — Create the MLflow database

```bash
docker compose up -d postgres
docker exec logitrack_postgres \
  psql -U "$POSTGRES_USER" -c "CREATE DATABASE mlflow;"
```

### Step 4 — Run the full production stack

```bash
docker compose --profile prod up -d
# All services start in dependency order thanks to healthchecks.
```

### Step 5 — Apply Alembic migrations

```bash
docker exec logitrack_backend \
  alembic upgrade head
```

### Step 6 — Initialise MinIO bucket

```bash
docker exec logitrack_minio \
  mc alias set local http://localhost:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
docker exec logitrack_minio mc mb local/logitrack
```

### Step 7 — Verify

| URL | Service |
|---|---|
| `https://localhost` | React dashboard |
| `https://localhost/docs` | Swagger UI |
| `https://localhost/health` | Health check JSON |
| `http://localhost:5050` | MLflow UI |

---

## 5. CI/CD Pipeline Description

File: `.github/workflows/ci.yml`

**Triggers:** push to `main`, pull requests targeting `main`.  
**Concurrency:** running workflows for the same branch are cancelled when a new commit is pushed.

| Job | Depends on | What it does |
|---|---|---|
| `lint` | — | `ruff check` on all Python modules; `eslint` on TypeScript |
| `test-backend` | — | pytest with real PostgreSQL service container; coverage threshold ≥ 80% |
| `test-frontend` | — | vitest run |
| `build` | `lint` | Docker Buildx builds both images (no push); uses GHA layer cache |
| `security-scan` | `build` | Trivy scans backend image for CRITICAL/HIGH CVEs; uploads SARIF to GitHub Security tab |

`lint`, `test-backend`, and `test-frontend` run in **parallel**.  
`build` waits for `lint`. `security-scan` waits for `build`.

---

## 6. Pre-Production Checklist

- [ ] Replace `SECRET_KEY` with a securely generated 64-char hex value
- [ ] Replace all `change_me_in_production` passwords with strong unique values
- [ ] Replace self-signed SSL cert (`docker/ssl/`) with a CA-issued certificate
- [ ] Set `ENVIRONMENT=production` in `.env`
- [ ] Set `CORS_ORIGINS` to the actual frontend domain (not `*` or `localhost`)
- [ ] Set `REDIS_URL` to point to the production Redis instance
- [ ] Set `MLFLOW_TRACKING_URI` to the production MLflow server
- [ ] Run `alembic upgrade head` against the production database
- [ ] Create the `logitrack` bucket in MinIO / S3 and verify ML model upload works
- [ ] Run the ETL pipeline to seed the database: `python -m etl.run`
- [ ] Train the initial ML model: `POST /api/v1/ml/retrain` (admin token required)
- [ ] Verify `GET /health` returns `{"status": "healthy", "model_loaded": true}`
- [ ] Confirm `GET /api/v1/kpi/summary` returns real data
- [ ] Check Trivy scan passes with no CRITICAL vulnerabilities
- [ ] Confirm CI pipeline is green on `main`
- [ ] Set up log aggregation (Loki / Datadog / CloudWatch)
- [ ] Set up uptime monitoring with alerting (PagerDuty / OpsGenie)

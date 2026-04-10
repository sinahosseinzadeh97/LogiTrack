# LogiTrack — Technical Deep Dive

For senior engineers reviewing the codebase. Covers schema, data flow, ML architecture, auth, security, and operational concerns.

---

## 1. Database Schema

Six tables across three Alembic migrations. All timestamps are `TIMESTAMPTZ` (UTC-aware). All primary keys are autoincrement integers except where noted.

### `shipments` — Core fact table

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | `BIGINT PK` | No | Autoincrement |
| `order_id` | `VARCHAR(50)` | No | **UNIQUE**, indexed — natural key from Olist |
| `customer_id` | `VARCHAR(50)` | No | Indexed |
| `seller_id` | `VARCHAR(50)` | No | Indexed |
| `product_id` | `VARCHAR(50)` | Yes | — |
| `category_name` | `VARCHAR(100)` | Yes | Portuguese; 73 distinct values in Olist |
| `seller_state` | `VARCHAR(5)` | Yes | Indexed — Brazilian state code (SP, RJ, …) |
| `customer_state` | `VARCHAR(5)` | Yes | — |
| `purchase_timestamp` | `TIMESTAMPTZ` | Yes | Indexed — range filter anchor |
| `delivered_timestamp` | `TIMESTAMPTZ` | Yes | NULL = in-transit (used by ML alert filter) |
| `estimated_delivery` | `TIMESTAMPTZ` | Yes | From `olist_orders_dataset` |
| `price` | `NUMERIC(10,2)` | No | DEFAULT 0 |
| `freight_value` | `NUMERIC(10,2)` | No | DEFAULT 0 |
| `payment_value` | `NUMERIC(10,2)` | Yes | Sum across all payment types/installments |
| `delay_days` | `FLOAT` | Yes | `delivered_timestamp − estimated_delivery` in days |
| `is_late` | `BOOLEAN` | No | DEFAULT false, **indexed** — primary alert flag |
| `distance_km` | `FLOAT` | Yes | Geodesic seller→customer (geopy) |
| `cost_per_km` | `FLOAT` | Yes | `freight_value / distance_km` |
| `seller_lat` | `FLOAT` | Yes | From geolocation join |
| `seller_lng` | `FLOAT` | Yes | From geolocation join |
| `customer_lat` | `FLOAT` | Yes | From geolocation join |
| `customer_lng` | `FLOAT` | Yes | From geolocation join |
| `day_of_week` | `SMALLINT` | Yes | 0=Mon … 6=Sun (derived from purchase_timestamp) |
| `month` | `SMALLINT` | Yes | 1–12 (derived from purchase_timestamp) |
| `seller_historical_delay_rate` | `FLOAT` | Yes | Per-seller mean(is_late); training-time look-ahead |
| `review_score` | `SMALLINT` | Yes | 1–5; excluded from ML (post-delivery label) |
| `created_at` | `TIMESTAMPTZ` | No | `server_default=NOW()` |

**Key indexes:** `order_id` (UNIQUE), `seller_id`, `is_late`, `seller_state`, `purchase_timestamp`

---

### `kpi_daily` — Daily KPI aggregate

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | `INTEGER PK` | No | — |
| `date` | `DATE` | No | **UNIQUE**, indexed — one row per calendar day |
| `otif_rate` | `FLOAT` | Yes | Fraction on-time [0,1] (not percentage) |
| `avg_delay_days` | `FLOAT` | Yes | Mean delay across all delivered orders that day |
| `fulfillment_rate` | `FLOAT` | Yes | Fraction of orders with delivered status |
| `avg_cost_per_shipment` | `FLOAT` | Yes | Mean `freight_value` |
| `total_shipments` | `INTEGER` | Yes | Count per date |
| `flagged_count` | `INTEGER` | No | DEFAULT 0; ML-flagged shipments count |
| `updated_at` | `TIMESTAMPTZ` | No | `server_default=NOW()` |

**612 rows** in the loaded Olist dataset covering purchase dates 2016–2018.

---

### `seller_stats` — Per-seller aggregate

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | `INTEGER PK` | No | — |
| `seller_id` | `VARCHAR(50)` | No | **UNIQUE**, indexed |
| `seller_state` | `VARCHAR(5)` | Yes | State code |
| `total_orders` | `INTEGER` | Yes | Count of all orders for this seller |
| `delay_rate` | `FLOAT` | Yes | `mean(is_late)` — fraction, not percentage |
| `avg_delay_days` | `FLOAT` | Yes | Mean delay for late orders only |
| `avg_cost` | `FLOAT` | Yes | Mean `freight_value` |
| `updated_at` | `TIMESTAMPTZ` | No | `server_default=NOW()` |

**2,960 rows** post-ETL.

---

### `ml_model_versions` — ML model registry

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | `INTEGER PK` | No | — |
| `version` | `VARCHAR(50)` | No | MLflow `run_id` (UUID hex) |
| `trained_at` | `TIMESTAMPTZ` | No | `server_default=NOW()` |
| `accuracy` | `FLOAT` | Yes | Overall accuracy |
| `precision_late` | `FLOAT` | Yes | Precision on `is_late=True` class |
| `recall_late` | `FLOAT` | Yes | Recall on `is_late=True` class |
| `f1_late` | `FLOAT` | Yes | Primary promotion metric |
| `threshold` | `FLOAT` | No | DEFAULT 0.65; configurable via `ALERT_THRESHOLD` |
| `is_active` | `BOOLEAN` | No | DEFAULT false; only one row `TRUE` at a time |
| `storage_path` | `VARCHAR(500)` | Yes | `s3://logitrack/models/<run_id>/model_bundle.joblib` |
| `notes` | `TEXT` | Yes | Promotion notes |

---

### `users` — Auth user accounts (Migration 0002)

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | `INTEGER PK` | No | — |
| `email` | `VARCHAR(255)` | No | **UNIQUE**, indexed |
| `hashed_password` | `TEXT` | No | bcrypt hash (cost factor 12) |
| `full_name` | `VARCHAR(100)` | Yes | Display name |
| `role` | `userrole ENUM` | No | `viewer` / `analyst` / `admin` |
| `is_active` | `BOOLEAN` | No | DEFAULT true; soft-disable without deletion |
| `created_at` | `TIMESTAMPTZ` | No | `server_default=NOW()` |

---

### `token_blacklist` — Revoked refresh tokens (Migration 0002)

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | `INTEGER PK` | No | — |
| `jti` | `VARCHAR(36)` | No | **UNIQUE**, indexed — UUID4 from JWT claim |
| `blacklisted_at` | `TIMESTAMPTZ` | No | `server_default=NOW()` — indexed (Migration 0004) for O(log n) cleanup |

---

### `reports_log` — PDF report generation log (Migration 0003)

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | `INTEGER PK` | No | — |
| `week` | `VARCHAR(10)` | No | ISO week string: `"2025-W15"` |
| `generated_at` | `TIMESTAMPTZ` | No | `server_default=NOW()` |
| `s3_path` | `VARCHAR(500)` | Yes | S3 key after successful upload |
| `status` | `VARCHAR(20)` | No | `pending` / `success` / `failed` |
| `file_size_bytes` | `INTEGER` | Yes | PDF size in bytes |
| `error_message` | `VARCHAR(2000)` | Yes | Exception text on failure |

---

### Entity Relationships

```
shipments ──────────────────────────────────── (central fact table)
    │ seller_id                      │ purchase_timestamp
    ▼                                ▼
seller_stats                     kpi_daily
(one per seller)              (one per date)

ml_model_versions ──────── (independent; loaded into app.state at startup)

users ──────── token_blacklist  (jti is blacklisted on refresh/logout)

reports_log ──────── (independent; references S3 by path only)
```

---

## 2. ETL Pipeline Design

### Stage 1: `clean.py` — Ingest & Merge

**Input:** 9 Olist CSV files from `data/raw/`  
**Output:** `df_delivered` (orders with status=`delivered`) + `df_all` (all statuses)

```
olist_orders_dataset.csv           ←── primary join anchor
olist_order_items_dataset.csv      ←── price, freight_value, seller_id, product_id
olist_sellers_dataset.csv          ←── seller_state
olist_customers_dataset.csv        ←── customer_state
olist_products_dataset.csv         ←── category_name (Portuguese key)
product_category_name_translation.csv ←── Portuguese → English (not used in v1)
olist_order_payments_dataset.csv   ←── payment_value (sum per order)
olist_order_reviews_dataset.csv    ←── review_score (max per order)
olist_geolocation_dataset.csv      ←── zip prefix → lat/lng (used in Stage 2)
```

Key operations:
- Explicit dtype casting to prevent silent coercion (`str` for IDs, `float` for numerics)
- `parse_timestamps()`: `pd.to_datetime(..., utc=True, errors='coerce')` — bad rows produce `NaT`, not exceptions
- Deduplication: multi-item orders retain `order_item_id=1` (first item only)
- `delay_days = delivered_timestamp - estimated_delivery` (timedelta → float days)
- `is_late = delay_days > 0`

**Row counts:** ~99,441 raw orders → ~96,478 delivered → post-merge drop of <0.5% due to null join keys

---

### Stage 2: `enrich.py` — Feature Engineering

**Input:** `df_delivered` + geolocation DataFrame  
**Output:** `df_enriched`

| Function | Operation | Output Column |
|----------|-----------|---------------|
| `add_geo_features()` | Zip-prefix → lat/lng join (seller + customer); `geopy.distance.geodesic()` | `distance_km`, `seller_lat/lng`, `customer_lat/lng` |
| `add_temporal_features()` | Extract from `purchase_timestamp` | `day_of_week` (0=Mon), `month` (1–12) |
| `add_seller_delay_rate()` | `groupby('seller_id')['is_late'].mean()` join | `seller_historical_delay_rate` |
| `compute_cost_per_km()` | `freight_value / distance_km` | `cost_per_km` |

Geolocation handling: 1,000,163 raw rows deduplicated to ~19,015 unique zip prefixes (first coordinate per prefix kept). ~2% of orders have no matching zip and receive `NaN` distance (imputed in ML stage).

---

### Stage 3: `load.py` — Database Write

**Input:** `df_enriched`, `df_all`  
**Output:** PostgreSQL tables (`shipments`, `kpi_daily`, `seller_stats`)

| Function | Strategy | Batch Size |
|----------|----------|-----------|
| `upsert_shipments()` | `INSERT ... ON CONFLICT(order_id) DO UPDATE SET ...` | 1,000 rows |
| `compute_and_load_kpi_daily()` | `groupby(date)` → aggregate → upsert | Single batch |
| `compute_and_load_seller_stats()` | `groupby(seller_id)` → aggregate → upsert | Single batch |

`ON CONFLICT DO UPDATE` makes the ETL fully idempotent — re-running on the same data produces no duplicate rows and updates any changed fields (useful when enrichment logic is updated).

---

## 3. ML Feature Engineering

All 8 features are computed at ETL time (or at inference time via `encode_single_row`) and reside in the `shipments` table.

| Feature | Source Column | Transform | Importance (approx.) | Rationale |
|---------|--------------|-----------|----------------------|-----------|
| `distance_km` | `distance_km` | Median imputation for NaN | ~35% | Longest single predictor — transit time scales with distance |
| `seller_historical_delay_rate` | `seller_stats.delay_rate` | Global mean for NaN (new sellers) | ~20% | Seller track record is the clearest leading indicator |
| `month` | `month` | None (ordinal 1–12) | ~15% | Q4 peak volume correlates with higher delay rates |
| `freight_value` | `freight_value` | None | ~10% | Proxy for package weight/bulk |
| `price` | `price` | None | ~8% | Proxy for handling fragility |
| `category_encoded` | `category_name` | `LabelEncoder` (fill null → "unknown") | ~5% | Heavy/oversized categories have longer carrier SLAs |
| `day_of_week` | `day_of_week` | None (ordinal 0–6) | ~4% | Friday orders lose same-day processing window |
| `seller_state_encoded` | `seller_state` | `LabelEncoder` (fill null → "unknown") | ~3% | State-level logistics infrastructure varies significantly |

**Not included:**
- `review_score` — measured post-delivery; using it would be look-ahead label leakage
- `payment_value` — collinear with `price`; redundant after feature importance testing
- `cost_per_km` — derived from `freight_value` and `distance_km`; removed to avoid multicollinearity

**Unseen values at inference:** `encode_single_row()` handles new categories/states by mapping to `-1` (not a trained label index). The tree splits route these to the majority-class leaf, which is conservative and preferable to raising an exception.

---

## 4. API Authentication Flow

### JWT Token Architecture

```
POST /auth/login
├── bcrypt.verify(plain_password, hashed_password)
├── create_access_token:
│   └── {sub: user_id, role: UserRole, type: "access", exp: now+30min, iat: now}
└── create_refresh_token:
    └── {sub: user_id, type: "refresh", jti: UUID4, exp: now+7days, iat: now}

Authenticated request flow:
GET /api/v1/kpi/summary
├── OAuth2PasswordBearer extracts "Bearer <token>" from Authorization header
├── decode_token(token) → validates signature + expiry
├── assert payload["type"] == "access"
├── SELECT user WHERE id = payload["sub"]
└── require_role("viewer") → raises 403 if user.role not in {viewer, analyst, admin}

POST /auth/refresh
├── decode_token(refresh_token) → validates signature + expiry
├── assert payload["type"] == "refresh"
├── SELECT jti FROM token_blacklist → raises 401 if found (token reuse attack)
├── INSERT jti INTO token_blacklist (revoke old token atomically)
└── Issue new access_token + refresh_token pair

POST /auth/logout
└── INSERT refresh_token.jti INTO token_blacklist
```

### Token Claims

| Claim | Access Token | Refresh Token | Notes |
|-------|-------------|---------------|-------|
| `sub` | user_id (str) | user_id (str) | Used for DB user lookup |
| `role` | UserRole value | — | Eliminates DB round-trip on every request |
| `type` | `"access"` | `"refresh"` | Prevents token type confusion attacks |
| `jti` | — | UUID4 | Unique ID for blacklisting; absent from access tokens |
| `exp` | now + 30 min | now + 7 days | Both configurable via `.env` |
| `iat` | issued-at UTC | issued-at UTC | Audit trail |

### Security Properties

- **Token reuse detection**: After refresh, old JTI is atomically blacklisted before issuing a new pair. An attacker who intercepts a refresh token cannot reuse it after the legitimate user has already refreshed.
- **Stateless access tokens**: Role is embedded in the JWT payload — no DB lookup on every authenticated request (only on the first request per connection via `get_current_user`).
- **No access token blacklisting**: By design. 30-minute TTL provides acceptable revocation lag without the complexity of an access token blacklist. Production can reduce `ACCESS_TOKEN_EXPIRE_MINUTES=15`.

---

## 5. RBAC Matrix

Three roles with strict hierarchy: `viewer ⊂ analyst ⊂ admin`.

| Endpoint | viewer | analyst | admin |
|----------|:------:|:-------:|:-----:|
| `POST /auth/login` | ✅ | ✅ | ✅ |
| `POST /auth/refresh` | ✅ | ✅ | ✅ |
| `GET /auth/me` | ✅ | ✅ | ✅ |
| `POST /auth/logout` | ✅ | ✅ | ✅ |
| `POST /auth/register` | ❌ | ❌ | ✅ |
| `GET /api/v1/kpi/*` | ✅ | ✅ | ✅ |
| `GET /api/v1/shipments` | ✅ | ✅ | ✅ |
| `GET /api/v1/shipments/{id}` | ✅ | ✅ | ✅ |
| `GET /api/v1/shipments/export` | ❌ | ✅ | ✅ |
| `GET /api/v1/alerts` | ✅ | ✅ | ✅ |
| `GET /api/v1/alerts/stats` | ✅ | ✅ | ✅ |
| `POST /api/v1/alerts/predict` | ❌ | ✅ | ✅ |
| `GET /api/v1/sellers/*` | ✅ | ✅ | ✅ |
| `POST /api/v1/reports/generate` | ❌ | ✅ | ✅ |
| `GET /api/v1/reports` | ✅ | ✅ | ✅ |
| `GET /api/v1/reports/{id}/download` | ✅ | ✅ | ✅ |
| `GET /api/v1/reports/{id}/preview` | ✅ | ✅ | ✅ |
| `GET /api/v1/ml/model-info` | ❌ | ❌ | ✅ |
| `GET /api/v1/ml/feature-importance` | ❌ | ❌ | ✅ |
| `POST /api/v1/ml/retrain` | ❌ | ❌ | ✅ |
| `GET /api/v1/ml/retrain-status/*` | ❌ | ❌ | ✅ |
| `GET /health` | ✅ | ✅ | ✅ |

**Implementation:** `require_role(*roles)` is a factory that returns a FastAPI `Depends`-compatible async function. It raises `HTTPException(403)` when the authenticated user's role is not in the allowed set. Role is read from the JWT payload — no DB query.

---

## 6. Retraining Pipeline Logic

### Trigger Decision (`should_retrain`)

```python
# Condition A — Data volume (fires roughly every 3 weeks at 25 orders/day)
COUNT(shipments WHERE created_at > last_trained_at) >= 500

# OR

# Condition B — Accuracy drift (detects concept drift)
stored_accuracy < 0.78
OR abs(stored_accuracy - (1 - recent_late_rate)) > 0.22
```

Condition B uses the raw late-rate on the last 30 days as a proxy for accuracy drift. This is a heuristic — a proper drift detector would run the active model on recent data, but that requires features to be populated for fresh rows (not guaranteed). The 0.22 tolerance is set wide enough to avoid false positives from normal variance.

### Promotion Rule

```
new_f1_holdout > old_f1_holdout
```

Where `holdout = last 10% of the dataset chronologically` — shared between old and new model evaluation. This prevents the trivial case where a new model "improves" because it saw different training data.

### Full Pipeline Steps

```
1. SELECT * FROM shipments WHERE is_late IS NOT NULL  →  df (labelled rows)
2. build_feature_matrix(df)  →  X (features), y (labels)
3. Reserve last 10% as shared holdout
4. train_model(df[:-holdout])  →  new_model, new_threshold, new_metrics
5. load_active_model(engine, settings)  →  old_model, old_encoders, old_threshold
6. Evaluate old_model on holdout  →  old_f1
7. Evaluate new_model on holdout  →  new_f1
8. log_experiment(...)  →  MLflow run_id + S3 upload
9. if new_f1 > old_f1:
       promote_model(run_id)
       UPDATE ml_model_versions SET is_active=FALSE (all)
       INSERT ml_model_versions (is_active=TRUE)
       S3 copy_object: models/<run_id>/ → models/active/
```

The `models/active/` S3 slot is a pointer-swap (copy-object) that takes effect immediately. The app loads from `models/active/` at startup, so zero downtime during promotion. Rollback requires manually setting `is_active=TRUE` on a previous model version row and updating `models/active/`.

### APScheduler Registration

```python
# Fires every Monday at 02:00 UTC
CronTrigger(day_of_week="mon", hour=2, minute=0)
```

Registered in `lifespan()` after DB connection is verified. Uses a `BackgroundScheduler` (daemon thread) — does not block application shutdown.

---

## 7. PDF Generation Pipeline

### Architecture

```
POST /api/v1/reports/generate
│
├── INSERT reports_log (status='pending')  →  report_id returned immediately
│
└── FastAPI BackgroundTask:
    _run_report_generation(report_id, week_date)
    │
    ├── WeeklyReportGenerator.__init__(db_engine, week_date)
    │   └── Normalise week_date to ISO Monday
    │
    ├── generate_with_dark_cover()
    │   │
    │   ├── Page 1: _build_cover_page()
    │   │   └── Canvas callback: fills background #0a0c10
    │   │       Helvetica-Bold title, week label, generation timestamp
    │   │
    │   ├── Page 2: _build_kpi_summary()
    │   │   └── 2×2 Table: OTIF %, Avg Delay, Fulfillment %, Avg Cost
    │   │       WoW delta: ↑ (green) / ↓ (red) arrows
    │   │       ReportLab TableStyle for alternating row colours
    │   │
    │   ├── Page 3: _build_otif_chart()
    │   │   └── plotly.graph_objects.Figure()
    │   │       ├── kaleido.scope.plotly.transform(fig) → PNG bytes
    │   │       └── ReportLab Image(BytesIO(png_bytes))
    │   │
    │   ├── Page 4: _build_seller_critical_list()
    │   │   └── TOP 5 sellers by delay_rate this week
    │   │       Columns: seller_id, state, orders, late, delay%, avg_delay, avg_cost
    │   │
    │   └── Page 5: _build_flagged_shipments()
    │       └── All is_late=TRUE orders in the week (up to 200)
    │           Columns: order_id, seller_id, seller_state, customer_state,
    │                    category, delay_days, freight_value
    │
    ├── s3.put_object(Bucket, Key="reports/weekly_report_YYYY-WW.pdf", Body=pdf_bytes)
    │
    └── UPDATE reports_log SET status='success', s3_path=…, file_size_bytes=…
        (or status='failed', error_message=str(exc) on any exception)
```

### Design Constraints

- **No external fonts**: Helvetica throughout. `Helvetica`, `Helvetica-Bold` are PDF built-in fonts — no font file loading, no encoding issues across platforms.
- **No headless browser**: Plotly → kaleido is a pure Python pipeline (`pip install kaleido`); no Puppeteer, no Chrome required in Docker.
- **poppler dependency**: `pdf2image` (used by the preview endpoint) requires `poppler-utils` at the OS level. Handled in `Dockerfile.backend` via `apt-get install -y poppler-utils`.

---

## 8. Docker Service Graph

### Services and Profiles

| Service | Image | Profile | Internal Port | Healthcheck |
|---------|-------|---------|---------------|-------------|
| `postgres` | `postgres:16-alpine` | always | 5432 | `pg_isready` |
| `minio` | `minio/minio:latest` | always | 9000, 9001 | `mc ready local` |
| `redis` | `redis:7-alpine` | always | 6379 | `redis-cli ping` |
| `adminer` | `adminer:latest` | `dev` | 8080 | HTTP |
| `backend` | `Dockerfile.backend` | `prod` | 8000 | `GET /health` |
| `frontend` | `Dockerfile.frontend` | `prod` | 80 | HTTP |
| `nginx` | `nginx:alpine` | `prod` | 80, 443 | HTTP |
| `mlflow` | `ghcr.io/mlflow/mlflow:v2.13.2` | `prod` | 5050 | HTTP |

### Dependency Order

```
postgres ──────────────────────────────────────────────────┐
   │                                                        │
minio ─────┐                                               │
   │        ▼                                              ▼
redis ──► backend ──► frontend ──► nginx           mlflow
```

All `prod` services depend on their upstream via `condition: service_healthy` — Docker Compose will not start `backend` until `postgres`, `minio`, and `redis` all report healthy. This prevents the common race condition where the app starts before the DB is ready.

### Backend Dockerfile (multi-stage)

```dockerfile
# Stage 1: Builder
FROM python:3.12-slim AS builder
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[prod]"

# Stage 2: Runtime
FROM python:3.12-slim
RUN apt-get install -y poppler-utils    # for pdf2image
RUN useradd --no-create-home appuser    # non-root user
COPY --from=builder /app /app
USER appuser
HEALTHCHECK CMD curl -f http://localhost:8000/health || exit 1
```

The non-root user prevents privilege escalation if the container is compromised. The multi-stage build keeps the final image smaller by not including pip/build tools.

---

## 9. Known Limitations

| Category | Limitation | Severity | Mitigation / Roadmap |
|----------|-----------|----------|----------------------|
| **ML — class imbalance** | 8% positive rate; F1-late of 0.31 is modest despite `class_weight='balanced'` | Medium | Evaluate XGBoost/LightGBM in Phase 8; apply threshold tuning via Precision-Recall curve |
| **ML — model drift** | No automated drift detection beyond the accuracy heuristic in `should_retrain()` | Medium | Add Isolation Forest on feature distributions; integrate Evidently AI |
| **ML — single model** | One active model globally; no per-seller or per-category model sharding | Low | Multi-model registry with routing by category in Phase 9 |
| **Auth — access token revocation** | Access tokens cannot be revoked before their 30-min TTL expires | Low | Acceptable for current scope; reduce TTL to 15 min for higher-security deployments |
| **Auth — sessionStorage** | Refresh token stored in `sessionStorage` (XSS-readable) | Medium | Migrate to `Set-Cookie: HttpOnly; Secure; SameSite=Strict` in Phase 8 |
| **ETL — one item per order** | Multi-item orders use only `order_item_id=1` for features | Low | Aggregate item-level features (count, max price) in Phase 2 ETL revision |
| **ETL — static geo** | Geolocation uses the first coordinate per zip prefix; some prefixes span large areas | Low | Cluster coordinates per zip in Phase 2; use centroid |
| **KPI — fulfillment rate** | `kpi_daily.fulfillment_rate` is computed only from delivered orders (always 1.0 in Phase 1 ETL) | Medium | The API recomputes fulfillment live from `df_all`; the stored value is stale |
| **API — no WebSocket** | KPI dashboard polls every 5 minutes; not truly real-time | Low | Planned `/ws/kpi` WebSocket endpoint |
| **Reports — no email delivery** | PDF reports are not automatically emailed after generation | Low | Planned SendGrid/SES integration |
| **Frontend — large bundle** | Single JS bundle >1MB (uncompressed); lucide-react contributes ~400KB | Low | Per-icon imports or vite-plugin tree-shaking in Phase 8 |
| **Database — no read replica** | All reads and writes go to the same Postgres instance | Low | Add PgBouncer + read replica for >1000 RPS production workloads |

---

## 10. Security Measures

### Rate Limiting

```
POST /auth/login:  5 req / minute per IP
All endpoints:     100 req / minute per (user_id or IP)
```

Implementation (`app/limiter.py`): slowapi `Limiter` with a custom key function that extracts `sub` from the Bearer JWT payload (payload-only decode — no DB lookup) for authenticated requests, falling back to `request.client.host` for unauthenticated requests. Redis backend when `REDIS_URL` is configured; in-memory `MemoryStorage` for development.

### HTTP Security Headers

Applied via `@app.middleware("http")` to **every** response:

| Header | Value | Protection |
|--------|-------|-----------|
| `X-Content-Type-Options` | `nosniff` | MIME sniffing → XSS vectors |
| `X-Frame-Options` | `DENY` | Clickjacking in all browsers |
| `X-XSS-Protection` | `1; mode=block` | Legacy IE/Edge XSS filter |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Referrer header leakage |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | HSTS (production only) |

### HTTPS Enforcement

In `ENVIRONMENT=production`, the `https_redirect` middleware inspects `X-Forwarded-Proto` (set by nginx) and issues a `301` redirect for any HTTP request. nginx itself terminates TLS and strips the header for internal traffic.

### SQL Injection

100% parameterised queries via SQLAlchemy ORM across all 7 routers. No string interpolation in SQL. Confirmed by code review of all `text()` calls (only in ETL bulk operations, using `engine.begin()` with bound parameters).

### Token Security

- **Refresh token rotation**: old JTI blacklisted atomically before issuing new pair
- **Token type binding**: `payload["type"]` assertion prevents access tokens from being used as refresh tokens and vice versa
- **Daily blacklist cleanup**: `DELETE FROM token_blacklist WHERE blacklisted_at < NOW() - INTERVAL '7 days'` at 03:00 UTC; indexed on `blacklisted_at` for O(log n) performance
- **bcrypt cost factor 12**: ~250ms verification time — acceptable latency, impractical to brute-force

### Container Security

- Non-root user in both backend and frontend Docker images
- Multi-stage builds to exclude build tools from runtime image
- Trivy CRITICAL/HIGH CVE scan on every CI build; SARIF uploaded to GitHub Security tab
- `.gitignore` excludes `.env`, `data/raw/`, `*.joblib`, `mlruns/`, all secrets

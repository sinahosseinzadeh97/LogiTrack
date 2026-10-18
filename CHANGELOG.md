# Changelog

## 1.0.0 — 2026-10-18

A rewrite of the v0 prototype. The visual design is kept; the data pipeline, model, API, frontend
data layer, infrastructure and tests are new. See "Project history" in the README for why.

### Added

- **Point-in-time features** built from due events with `merge_asof`, so no order sees its own outcome
  or anything from its future: seller order history and smoothed miss rate, the 14-day network miss
  rate, 7-day order volume, and the promise compared with last week's typical promise.
- **Out-of-time evaluation**: train before 1 Feb 2018 (with labels knowable at the cutoff), test once on
  everything after; feature set chosen by rolling-origin CV inside the training window; threshold chosen
  on a time-based validation slice.
- **Model card** with metrics against single-feature baselines, a monthly breakdown that exposes drift,
  and permutation importance; served by `GET /api/v1/ml/model`.
- **Alert backtest**: `GET /api/v1/alerts?as_of=…` replays the in-transit queue of any morning after the
  cutoff and reports precision, recall and lift against the real outcomes; new At-risk queue page.
- **What-if scoring**: `POST /api/v1/ml/predict` (analyst role) and a form on the Model page.
- **Regions** tile map of the 27 states, a seller detail page, and an order drawer showing the features
  the model saw.
- **Demo accounts** (`viewer@`, `analyst@`, `admin@logitrack.dev`) created by `python -m app.seed`, with
  one-click fill on the sign-in page when built with `VITE_DEMO_PASSWORD`.
- **Bundled 25% sample** of the dataset (`data/sample/`, sampled by seller) so the demo runs without a
  download; `python -m etl.sample` regenerates it.
- **One-command Docker stack**: `docker compose up` migrates, loads, trains and seeds on first start and
  is idempotent afterwards; `WEB_PORT` picks the host port.
- **CI** that lints and tests both halves against PostgreSQL 16 and then boots the whole stack.
- Tests that fail if leakage is re-introduced, API tests against real PostgreSQL through the Alembic
  migration, and frontend unit tests.

### Changed

- One fact table, `shipments`, holds every order (all statuses), its outcome, features and model
  score. KPIs, scorecards and the backtest are SQL aggregates instead of pandas over the whole table.
- "Late" now means delivered on a later calendar day than promised (the promise is a date).
- Order totals sum all items instead of using the first item only.
- Model: `HistGradientBoostingClassifier` inside a single scikit-learn `Pipeline` (replacing a random
  forest with a separate dict of label encoders), unweighted so its probabilities stay meaningful.
- ETL loads with `TRUNCATE` + `COPY` in one transaction: about 3 seconds instead of about 25.
- Auth uses PyJWT and bcrypt directly (replacing python-jose and passlib), checks issuer and audience,
  rotates refresh tokens atomically, and keeps no raw tokens in the database.
- Frontend data layer rewritten against the new API: typed TanStack Query hooks, a single shared token
  refresh, lazily loaded pages, a responsive layout.
- The database schema is a single fresh Alembic migration.

### Removed

- MinIO, Redis, the MLflow server, the nginx SSL proxy, Adminer, three in-process APScheduler jobs, and
  the PDF report generator (it depended on Chrome through kaleido).
- The `kpi_daily`, `seller_stats`, `ml_model_versions` and `reports_log` tables.
- Reports, Settings and Prediction pages (prediction now lives on the Model page), a theme toggle
  that had no light theme, and 14 unused npm dependencies.
- Committed artefacts and local files: `mlflow.db`, `mlruns/`, `tsconfig.tsbuildinfo`,
  `.claude/settings.local.json`, and generated marketing documents.

### Fixed

- Target leakage in the seller delay-rate feature and a random split on time-ordered data, which had
  inflated ROC-AUC to 0.80 (the out-of-time value is 0.653).
- The Alerts page was always empty because the ETL never loaded undelivered orders.
- Fulfillment rate always read 100%.
- A fresh install had no way to create the first user.
- The frontend build (TypeScript errors, an undefined `setPage` that crashed the Alerts filters), all
  ESLint and ruff errors, and the 8 failing backend tests.
- The trend chart's y-axis showing "9608%".
- Seller rankings dominated by sellers with only one or two delivered orders.
- Missing `greenlet` dependency for SQLAlchemy's async engine, found by the first clean Docker build.

## 0.x — 2026-04

Initial prototype: ETL, KPI engine, random-forest delay classifier with MLflow tracking, FastAPI with
JWT auth, React dashboard, PDF reports and a multi-service Docker setup.

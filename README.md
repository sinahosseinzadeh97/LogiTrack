# LogiTrack

**Delivery-performance analytics and an honestly evaluated late-delivery model, built on 99,441 real e-commerce orders.**

[![CI](https://github.com/sinahosseinzadeh97/LogiTrack/actions/workflows/ci.yml/badge.svg)](https://github.com/sinahosseinzadeh97/LogiTrack/actions/workflows/ci.yml)
![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![PostgreSQL 16](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![scikit-learn](https://img.shields.io/badge/scikit--learn-F7931E?logo=scikitlearn&logoColor=white)
![React 19](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![Docker](https://img.shields.io/badge/Docker_Compose-2496ED?logo=docker&logoColor=white)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)

![The at-risk queue replayed on the morning of 15 March 2018](docs/screenshots/backtest.png)

```bash
docker compose up --build      # then open http://localhost:8080 and pick a demo account
```

---

## Contents

- [What it is](#what-it-is)
- [Quick start](#quick-start)
- [Features](#features)
- [Evaluating the model without fooling yourself](#evaluating-the-model-without-fooling-yourself)
- [Results](#results)
- [How it works](#how-it-works)
- [Data model](#data-model)
- [Definitions](#definitions)
- [API reference](#api-reference)
- [Security](#security)
- [Configuration](#configuration)
- [Development without Docker](#development-without-docker)
- [Testing and CI](#testing-and-ci)
- [Project structure](#project-structure)
- [Project history: from v0 to v1](#project-history-from-v0-to-v1)
- [Known limitations and roadmap](#known-limitations-and-roadmap)
- [Data, license and author](#data-license-and-author)

---

## What it is

Every order on an e-commerce marketplace comes with a promise: *"arrives by 18 October"*. LogiTrack is
the operations dashboard for keeping that promise. It runs on the public
[Olist Brazilian e-commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce):
99,441 real orders placed between September 2016 and October 2018 by customers in all 27 Brazilian
states, sold by 3,095 sellers.

It answers two questions:

1. **How well are we keeping our delivery promises?** On-time rate, fulfillment rate, delivery time,
   and where it goes wrong: which weeks, product categories, sellers and destination states.
2. **Which orders that are in transit right now are likely to arrive late?** A model scores every
   order at checkout, so an operations team could act before the customer complains.

Because the data is historical, "right now" is simulated: the **at-risk queue backtest** lets you pick
any morning after the model's training cutoff and see the orders that were in transit that day, which
ones the model flagged, and how each one actually ended. That turns "the model has an AUC of X" into
"on 15 March 2018, 75% of the orders it flagged really were late, against 39% of the whole queue".

| Headline numbers (full dataset) | |
|---|---|
| Orders / delivered | 99,441 / 96,470 |
| On-time rate | 93.2% |
| Fulfillment rate | 97.0% |
| Average purchase-to-doorstep time | 12.6 days |
| Average delay when late | 10.6 days |
| Model ROC-AUC / PR-AUC, out-of-time | 0.653 / 0.142 (base rate 0.080) |

---

## Quick start

Requirements: Docker with Compose v2.

```bash
git clone https://github.com/sinahosseinzadeh97/LogiTrack.git
```

```bash
cd LogiTrack && docker compose up --build
```

Open <http://localhost:8080>. If that port is taken, run `WEB_PORT=8090 docker compose up --build`
and open port 8090 instead.

The sign-in page has buttons that fill in a demo account. All three use the password `logitrack-demo`:

| Account | Role | Can |
|---|---|---|
| `viewer@logitrack.dev` | viewer | read every page |
| `analyst@logitrack.dev` | analyst | also export CSV and run what-if predictions |
| `admin@logitrack.dev` | admin | also create users through the API |

**What the first start does.** The API container migrates the database, loads the bundled 25% sample
of the dataset, trains the model, writes a risk score for every order, and creates the demo accounts.
That takes about a minute after the images are built. Every step is idempotent, so later starts skip
straight to serving.

**Using all 99k orders.** Download the dataset from Kaggle, unzip the nine CSV files into `data/raw/`,
and start from an empty database so the ETL and training run again:

```bash
docker compose down -v
```

```bash
docker compose up --build
```

---

## Features

| Page | What it shows |
|---|---|
| **Overview** | Headline KPIs for any purchase-date range, weekly on-time trend, the categories most often late, the hardest destination states, and a summary of the model |
| **At-risk queue** | The backtest: choose a morning after the training cutoff and see the in-transit queue, the flagged orders, and precision, recall and lift against the real outcomes |
| **Orders** | All 99k orders with filters for status, destination state, outcome, date range and order ID; sort by date, risk or delay; CSV export for analysts |
| **Sellers** | A scorecard sortable by late rate, average delay, volume and freight, with a minimum-volume filter, plus a page per seller with a monthly trend and their orders |
| **Regions** | A tile map of the 27 states coloured by on-time rate, next to a sortable table with delivery time, freight and distance |
| **Model** | The model card: metrics against baselines, month-by-month quality, permutation feature importance, and a what-if form that scores a hypothetical order |

Every order opens a detail drawer that shows the outcome, the risk score, and the exact
features the model saw when the order was placed.

![Overview](docs/screenshots/overview.png)

![Regions](docs/screenshots/regions.png)

---

## Evaluating the model without fooling yourself

The first version of this project reported a ROC-AUC of **0.80**. That number was wrong, for two
reasons that are easy to miss and common in real projects:

1. **Target leakage.** The strongest feature was each seller's late-delivery rate, computed over *all*
   of the seller's orders, including the order being predicted and every order placed after it. Nobody
   knows that number at checkout.
2. **A random train/test split** on time-ordered data, so the test set shared months (and the leak)
   with the training data.

The rebuild fixes both. Each rule below is enforced in code and covered by tests:

| Rule | Implementation |
|---|---|
| A feature may only use what was knowable at purchase time | History features are built from *due events*: the day after an order's promised date we know whether it made it. `pd.merge_asof(..., allow_exact_matches=False)` looks up running totals strictly before each purchase ([`backend/etl/features.py`](backend/etl/features.py)). |
| Test data comes strictly after training data | Train on orders bought before **1 February 2018** whose promised date is also before it, so no training label comes from the future. Test on every order bought afterwards ([`backend/ml/train.py`](backend/ml/train.py)). |
| The test set is used exactly once | The feature set is chosen by rolling-origin cross-validation *inside* the training window (four folds, each with an earlier cutoff), and the alert threshold on the last 15% of the training window by time. The test period is scored a single time, at the end. |
| Results are reproducible | Fixed row order and random seeds. Two training runs, and a run inside Docker on another machine, produce identical model cards. |
| Leaks get caught automatically | `test_an_orders_own_outcome_never_changes_its_features` and a brute-force recount of every seller feature. Re-introducing a 60-day look-ahead makes both tests fail. |

An honest model looks worse on paper, and that is the point. In this data, lateness is driven mostly
by network-wide shocks (holiday peaks, strikes, backlogs) rather than by anything about an individual
order, so there is a hard ceiling on what any per-order model can predict.

---

## Results

### Held-out period: February to August 2018

45,708 delivered orders, 8.0% of them late. The model was trained on 44,494 orders from September 2016
to January 2018 (5.6% late).

| Score on the test period | ROC-AUC | PR-AUC |
|---|---|---|
| **This model** (HistGradientBoosting, 15 inputs) | **0.653** | **0.142** |
| Seller history alone | 0.498 | 0.082 |
| Recent network-wide miss rate alone | 0.526 | 0.081 |
| Random guessing | 0.500 | 0.080 |

At the chosen threshold (P(late) ≥ 27.5%) the model flags 6.5% of orders. 19.8% of those are late,
and it catches 16.0% of all late orders. Its top 10% riskiest orders are late **2.2×** as often as
average.

### The backtest

| Morning of | In transit | Flagged | Flagged that were late | Late rate of whole queue | Lift |
|---|---|---|---|---|---|
| 15 Mar 2018 (Feb–Mar backlog) | 3,753 | 360 | 74.7% | 39.0% | 1.9× |
| 20 Apr 2018 | 2,701 | 194 | 28.9% | 15.5% | 1.9× |
| 24 May 2018 (national truckers' strike) | 2,163 | 271 | 29.2% | 24.5% | **1.2×** |
| 10 Jul 2018 | 1,579 | 105 | 15.2% | 7.3% | 2.1× |

### Month by month

| Purchase month | Orders | Late rate | ROC-AUC | PR-AUC |
|---|---|---|---|---|
| 2018-02 | 6,555 | 14.1% | 0.688 | 0.283 |
| 2018-03 | 7,003 | 19.0% | 0.687 | 0.353 |
| 2018-04 | 6,798 | 4.5% | 0.714 | 0.093 |
| 2018-05 | 6,749 | 6.6% | 0.697 | 0.127 |
| 2018-06 | 6,096 | 1.2% | 0.723 | 0.046 |
| 2018-07 | 6,156 | 3.4% | 0.597 | 0.055 |
| 2018-08 | 6,351 | 6.2% | **0.439** | 0.056 |

Two findings the model card surfaces on its own:

- **It cannot see a strike coming.** On 24 May the lift collapses. Nothing about an order placed a
  week earlier predicted a nationwide stoppage.
- **It drifts.** In August 2018 Olist shortened its promised delivery windows from about 24 days to
  about 15. The model, trained before that change, ranks worse than chance that month. In production
  that is the signal to retrain. Here it is shown on the Model page rather than hidden.

### What the model relies on

Permutation importance on the test set: how much PR-AUC drops when one column is shuffled.

| Feature | Importance |
|---|---|
| Customer (destination) state | 0.037 |
| Promised delivery window | 0.018 |
| Orders placed network-wide in the previous 7 days | 0.009 |
| Seller state | 0.007 |
| Items in the order | 0.002 |
| Recent network-wide miss rate | **−0.014** |

The negative value means shuffling the recent miss rate *improves* test performance. The training
window contains essentially one big shock (Black Friday 2017), so the model learned a relationship
between recent misses and future lateness that did not hold in 2018. Cross-validation inside the
training window still preferred keeping it, and the test set was not used to overrule that choice.

![Model card](docs/screenshots/model.png)

---

## How it works

```mermaid
flowchart LR
    CSV[(Olist CSVs<br/>full data or 25% sample)] --> ETL
    subgraph backend [Python backend]
        ETL[etl.run<br/>extract → transform →<br/>point-in-time features → COPY] --> PG[(PostgreSQL<br/>shipments · users ·<br/>revoked_tokens)]
        PG --> TRAIN[ml.train<br/>CV · threshold · test once ·<br/>model card]
        TRAIN -->|model.joblib + model_card.json| API
        TRAIN -->|delay_probability for every order| PG
        PG --> API[FastAPI<br/>JWT auth · roles · SQL aggregates]
    end
    API <--> NGINX[nginx<br/>static SPA + /api proxy] <--> UI[React 19 SPA<br/>TanStack Router + Query]
```

### 1. ETL (`backend/etl/`, about 3 seconds on the full data)

| Step | Module | What it does |
|---|---|---|
| Extract | `extract.py` | Reads the nine CSVs (plain or gzipped), only the columns it needs, and fails with a clear message if a file or column is missing. Zip codes stay strings so leading zeros survive. |
| Transform | `transform.py` | Joins them into one row per order, for every status. Price and freight are summed across items; seller and category come from the first item. Distance is a vectorised haversine between zip-code centroids (median of the in-Brazil points). "Late" means delivered on a later calendar day than promised. |
| Features | `features.py` | Point-in-time features from due events: the seller's earlier orders and their smoothed miss rate, the network-wide miss rate over the last 14 days, order volume over the last 7 days, and how this order's promise compares with the previous week's typical promise. |
| Load | `load.py` | Replaces the table in one transaction (`TRUNCATE` + `COPY`). Readers keep seeing the old rows until it commits, and re-running is always safe. |

### 2. Training (`backend/ml/`, about 25 seconds on the full data)

1. Split at the cutoff with the "labels knowable at the cutoff" rule.
2. Choose the feature set (order only, plus seller history, plus network signals) by rolling-origin CV
   on PR-AUC.
3. Choose the threshold that maximises F1 on the last 15% of the training window.
4. Refit on the whole training window and score the test period once: metrics, baselines, monthly
   breakdown, permutation importance.
5. Save the scikit-learn `Pipeline` (derived features → ordinal encoding → `HistGradientBoostingClassifier`)
   and the model card, then write `delay_probability` for every order back to the database.

Because preprocessing lives inside the pipeline, the API and the trainer can never disagree about how
a column is encoded, and categories the model has never seen are handled natively.

### 3. Serving (`backend/app/`)

FastAPI loads the model once at startup. KPIs, scorecards and the backtest are plain SQL aggregates
over the `shipments` table with bound parameters, so there are no derived tables to keep in sync and
no request loads 100k rows into Python.

### 4. Frontend (`frontend/`)

React 19 and TypeScript with Vite, TanStack Router (type-safe routes, lazily loaded pages) and TanStack
Query (the data is historical, so responses are cached indefinitely). Charts use Recharts. The axios
client attaches the access token and, when several requests get a 401 at once, performs a single
shared refresh and replays them.

### 5. Container startup (`backend/docker-entrypoint.sh`)

```
alembic upgrade head          # schema
python -m etl.run --if-empty  # full data in data/raw if present, else data/sample
python -m ml.train --if-missing
python -m app.seed            # only when SEED_DEMO_USERS=true
uvicorn app.main:app ...
```

---

## Data model

**`shipments`**: one row per order, every status.

| Group | Columns |
|---|---|
| Identity | `order_id` (PK), `order_status`, `customer_id`, `customer_state`, `seller_id`, `seller_state`, `category` |
| Timeline | `purchase_ts`, `approved_ts`, `carrier_ts`, `delivered_ts`, `estimated_delivery` |
| Order | `n_items`, `n_sellers`, `price`, `freight_value`, `weight_g`, `distance_km`, `review_score` |
| Outcome (NULL until delivered) | `delay_days`, `is_late` |
| Features known at purchase | `promised_days`, `purchase_dow`, `seller_prior_orders`, `seller_prior_late_rate`, `network_late_rate_14d`, `network_orders_7d`, `promise_gap_7d` |
| Model output | `delay_probability` |

**`users`**: `id`, `email` (unique), `hashed_password` (bcrypt), `full_name`, `role`
(`viewer` / `analyst` / `admin`), `is_active`, `created_at`.

**`revoked_tokens`**: `jti` (PK), `expires_at`. Used refresh tokens; expired rows are pruned
opportunistically.

Olist timestamps are local time (America/Sao_Paulo) and are stored as-is. The schema is versioned with
Alembic (`backend/alembic/versions/`).

---

## Definitions

| Term | Definition |
|---|---|
| Late | Delivered on a calendar day after the promised date (`delay_days > 0`) |
| On-time rate | Share of delivered orders that were not late |
| Fulfillment rate | Share of all orders that were delivered |
| Delivery time | Purchase timestamp to delivery timestamp, delivered orders only |
| Due event | The day after an order's promised date, when it becomes known whether the promise was kept |
| In transit (backtest) | Bought in the 60 days before the as-of morning, not delivered by then, not cancelled, not yet due, and not part of the training set |
| Precision (backtest) | Share of flagged orders that turned out late (never-delivered orders count as late) |
| Recall (backtest) | Share of the queue's late orders that were flagged |
| Lift | Precision ÷ late rate of the whole queue |
| PR-AUC | Area under the precision–recall curve; for a random model it equals the base rate |

---

## API reference

Interactive documentation is served at `/docs` (Swagger UI) and `/redoc`. All endpoints except
`/health` and `/auth/login|refresh|logout` need `Authorization: Bearer <access token>`.

| Method | Path | Minimum role | Parameters |
|---|---|---|---|
| GET | `/health` | none | |
| POST | `/auth/login` | none (5/min per IP) | `email`, `password` |
| POST | `/auth/refresh` | none | `refresh_token` (single use) |
| POST | `/auth/logout` | none | `refresh_token` |
| GET | `/auth/me` | any signed-in user | |
| POST | `/auth/users` | admin | `email`, `password`, `full_name`, `role` |
| GET | `/api/v1/kpi/summary` | viewer | `start`, `end` |
| GET | `/api/v1/kpi/trend` | viewer | `start`, `end`, `granularity` = `week` \| `month` |
| GET | `/api/v1/kpi/categories` | viewer | `start`, `end`, `limit` |
| GET | `/api/v1/kpi/regions` | viewer | `start`, `end` |
| GET | `/api/v1/shipments` | viewer | `status`, `customer_state`, `seller_id`, `category`, `is_late`, `start`, `end`, `search`, `sort`, `order`, `page`, `page_size` |
| GET | `/api/v1/shipments/export` | analyst | same filters; streams CSV |
| GET | `/api/v1/shipments/{order_id}` | viewer | |
| GET | `/api/v1/sellers` | viewer | `start`, `end`, `min_orders`, `sort`, `order`, `page`, `page_size` |
| GET | `/api/v1/sellers/{seller_id}` | viewer | |
| GET | `/api/v1/alerts/window` | viewer | |
| GET | `/api/v1/alerts` | viewer | `as_of` (date on or after the cutoff), `limit` |
| GET | `/api/v1/ml/model` | viewer | |
| POST | `/api/v1/ml/predict` | analyst | any model inputs; omitted ones use typical values |

Example, against the Docker stack:

```bash
TOKEN=$(curl -s -X POST localhost:8080/auth/login -H 'content-type: application/json' \
  -d '{"email":"viewer@logitrack.dev","password":"logitrack-demo"}' | jq -r .access_token)
```

```bash
curl -s -H "Authorization: Bearer $TOKEN" "localhost:8080/api/v1/alerts?as_of=2018-03-15&limit=5" | jq .stats
```

---

## Security

- **Tokens.** HS256 JWTs with issuer, audience and expiry checked on every request. Access tokens last
  30 minutes; refresh tokens 7 days and are single use.
- **Refresh rotation is atomic.** Revoking a refresh token is one `INSERT … ON CONFLICT DO NOTHING
  RETURNING`, so two concurrent refreshes with the same token cannot both succeed.
- **Passwords.** bcrypt; inputs over bcrypt's 72-byte limit are rejected rather than silently
  truncated. A login with an unknown e-mail costs the same bcrypt time as a wrong password and returns
  the same message.
- **Roles** are ranked (`viewer < analyst < admin`) and enforced in the API, not just hidden in the UI.
- **Rate limiting** on login: 5 attempts per minute per client IP (uvicorn trusts nginx's
  `X-Forwarded-For`).
- **SQL** uses bound parameters throughout; the only inlined values (sort column, direction,
  granularity) are restricted to fixed lists by request validation.
- **Headers.** nginx sends a Content-Security-Policy, `X-Frame-Options: DENY`, `nosniff` and a
  referrer policy; the API sets the same basic headers.
- **Configuration.** The API refuses to start with `ENVIRONMENT=production` and the built-in
  development secret. Demo accounts are only created when `SEED_DEMO_USERS=true`, and the sign-in page
  only shows them when the frontend is built with `VITE_DEMO_PASSWORD`.

---

## Configuration

Copy `.env.example` to `.env` to override the Docker defaults. Every variable is optional for a local
demo.

| Variable | Default | Used by | Purpose |
|---|---|---|---|
| `WEB_PORT` | `8080` | compose | Host port for the web UI |
| `SECRET_KEY` | development key | API | JWT signing key; required in production |
| `ENVIRONMENT` | `development` | API | `development`, `test` or `production` |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `logitrack` | compose | Database credentials |
| `SEED_DEMO_USERS` | `true` | entrypoint | Create the three demo accounts |
| `DEMO_PASSWORD` | `logitrack-demo` | API, frontend build | Password of the demo accounts |
| `DATABASE_URL` | built by compose | API | Plain `postgresql://` DSN; async and sync drivers are derived from it |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | API | |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | API | |
| `LOGIN_RATE_LIMIT` | `5/minute` | API | |
| `CORS_ORIGINS` | the web origin | API | Comma-separated |
| `DATA_DIR` | `/data/raw` | ETL | Where to look for the full CSVs |
| `MODEL_DIR` | `/app/artifacts` | API, training | Where the model and model card live |

---

## Development without Docker

Requirements: Python 3.12, Node 22, PostgreSQL 14 or newer.

```bash
cd backend && python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
```

```bash
export DATABASE_URL=postgresql://user:pass@localhost:5432/logitrack
```

```bash
alembic upgrade head && python -m etl.run && python -m ml.train && python -m app.seed
```

```bash
uvicorn app.main:app --reload
```

In a second terminal:

```bash
cd frontend && npm install && VITE_DEMO_PASSWORD=logitrack-demo npm run dev
```

The Vite dev server runs on <http://localhost:5173> and proxies `/api` and `/auth` to
`localhost:8000` (override with `API_PROXY_TARGET`).

Useful commands, all run from `backend/`:

| Command | Does |
|---|---|
| `python -m etl.run --data-dir ../data/raw` | Reload the database from a specific folder |
| `python -m ml.train --cutoff 2018-03-01` | Retrain with another train/test cutoff |
| `python -m etl.sample --fraction 0.25` | Regenerate `data/sample/` from the full data |
| `python -m app.seed` | Create the demo accounts |

---

## Testing and CI

```bash
cd backend && TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/logitrack_test pytest --cov=app --cov=etl --cov=ml
```

```bash
cd frontend && npm run lint && npm test && npm run build
```

`TEST_DATABASE_URL` must point at a database you can throw away: the tests drop and rebuild it.

**Backend: 32 tests, 93% coverage.** The API tests run against real PostgreSQL built by the Alembic
migration, with synthetic Olist-shaped data loaded through the real ETL command. They cover:

- the leakage rules: brute-force recount of point-in-time features, and an order's own outcome
  never changing its features;
- the out-of-time split, threshold selection, and training on data with a known signal;
- the backtest endpoint against an independent pandas recount, and the KPI summary against pandas;
- authentication: single-use refresh tokens, logout, the rate limit, and every role boundary.

**Frontend: 8 tests** for the formatting helpers and the pagination component, plus ESLint and a strict
TypeScript build.

**CI** (GitHub Actions, on every push to `main` and every pull request):

1. Backend: `ruff check`, `ruff format --check`, the test suite against a PostgreSQL 16 service, coverage
   gate at 85%.
2. Frontend: `npm ci`, lint, tests, production build.
3. Docker: builds and boots the whole stack from the bundled sample, then logs in through nginx and
   reads the KPI summary.

---

## Project structure

```
backend/
  app/
    auth/            models, JWT + bcrypt service, role dependencies, routes
    routers/         kpi, shipments, sellers, alerts (backtest), ml (model card, predict)
    config.py        settings from environment variables
    database.py      async engine and session dependency
    main.py          app factory, middleware, health check
    models.py        the shipments table
    schemas.py       response and request models
    seed.py          demo accounts
  etl/               extract → transform → features → load; run.py (CLI), sample.py
  ml/                features.py (pipeline), train.py (split, CV, evaluation, scoring), model_store.py
  alembic/           schema migrations
  tests/             factory.py (synthetic data), unit tests, API tests
  docker-entrypoint.sh
frontend/src/
  api/               axios client with token refresh, typed TanStack Query hooks, API types
  pages/             one file per screen
  components/        charts, shipment table/filters/drawer, layout, shared UI
  lib/               formatting helpers, Brazil state tile layout
  stores/            auth store
data/sample/         25% sample of the dataset (gzipped), so the demo needs no download
data/raw/            put the full CSVs here (git-ignored)
docker/              Dockerfiles and nginx config
docs/screenshots/    images used in this README
```

---

## Project history: from v0 to v1

LogiTrack started as a broader, faster-built prototype (v0). Version 1.0 is a rewrite that keeps its
visual design but replaces almost everything underneath. The full list is in
[CHANGELOG.md](CHANGELOG.md).

**What was wrong with v0**

| Problem | Effect |
|---|---|
| The seller late-rate feature was computed from all orders, including future ones, and the data was split randomly | The reported ROC-AUC of 0.80 was inflated by leakage |
| The ETL loaded only delivered orders, while the Alerts page looked for undelivered ones | The core ML feature always showed an empty list |
| Fulfillment rate was computed from a hard-coded `'delivered'` status | It always read 100% |
| Only admins could create users and nothing created the first admin | A fresh install had no way to log in |
| The frontend build failed, ESLint and ruff reported errors, 8 of 45 backend tests failed | The CI pipeline could not pass |
| The trend chart multiplied a percentage by 100 again | Its axis read "9608%" |
| MinIO, Redis, an MLflow server, nginx with SSL, three in-process schedulers and a PDF generator that needed Chrome | A lot to run, little of it working together |

**What v1 does instead**

- Point-in-time features, an out-of-time split, feature selection by time-series CV, a threshold chosen
  without the test set, baselines, a drift breakdown, and reproducible training.
- The Alerts page became a backtest that can be checked against what actually happened.
- One fact table, KPIs as SQL aggregates, ETL in 3 seconds instead of about 25.
- PyJWT and bcrypt instead of python-jose and passlib, atomic refresh rotation, seeded demo accounts.
- One `docker compose up` that works from a fresh clone, and CI that proves it.
- Tests against real PostgreSQL, including tests that fail if the leak comes back.

---

## Known limitations and roadmap

- **Retraining is manual** (`python -m ml.train`). The August 2018 drift shows it should be scheduled
  and gated on a monitored metric.
- **Probabilities are not calibration-checked.** A reliability curve on the test period is the next
  evaluation to add.
- **Network-shock features.** With essentially one major shock in the training window, signals like
  the recent miss rate do not generalise. Longer history or external signals (holidays, strikes,
  carrier capacity) would be needed.
- **Order grain.** Seller and category come from an order's first item; 1.3% of orders have several
  sellers.
- **Rate limiting is per process** (in memory), so the API runs a single worker. A Redis storage
  backend would allow scaling out.
- **Tokens live in `sessionStorage`.** A hardened deployment would keep the refresh token in an
  `httpOnly` cookie.

---

## Data, license and author

- **Code:** MIT, see [LICENSE](LICENSE).
- **Data:** © Olist, licensed [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/).
  `data/sample/` is redistributed under the same license; see [data/sample/README.md](data/sample/README.md).

Built by **Sina Mohammadhosseinzadeh** · [LinkedIn](https://www.linkedin.com/in/sina-hosseinzade20/)

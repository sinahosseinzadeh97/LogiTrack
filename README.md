# LogiTrack

**Delivery-performance analytics and an honestly-evaluated late-delivery model for 99,441 real e-commerce orders.**

[![CI](https://github.com/sinahosseinzadeh97/LogiTrack/actions/workflows/ci.yml/badge.svg)](https://github.com/sinahosseinzadeh97/LogiTrack/actions/workflows/ci.yml)

FastAPI · PostgreSQL · pandas · scikit-learn · React 19 + TypeScript · Docker Compose · GitHub Actions

![The at-risk queue replayed on 15 March 2018](docs/screenshots/backtest.png)

LogiTrack loads the public [Olist Brazilian e-commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
into PostgreSQL, serves delivery KPIs through a FastAPI backend, and scores every order's risk of
arriving after the date promised at checkout. The centrepiece is a **backtest of the alert queue**:
pick any day after the model's training cutoff and see the orders that were in transit that morning,
which ones the model flagged, and how each one actually ended.

```bash
docker compose up --build      # then open http://localhost:8080 and pick a demo account
```

---

## The part worth reading: evaluating the model without fooling yourself

The first version of this project reported a ROC-AUC of **0.80**. It was wrong, for two reasons that
are easy to miss and common in real projects:

1. **Target leakage.** The strongest feature was each seller's late-delivery rate, computed over *all*
   of the seller's orders — including the order being predicted and every order after it. At checkout
   you cannot know that number.
2. **A random train/test split** on time-ordered data, so the test set shared months (and the leak)
   with the training set.

The rebuild fixes both, and every claim below is enforced by a test:

| Rule | How it is implemented |
|---|---|
| A feature may only use what was knowable at purchase time | History features are built from *due events*: the day after an order's promised date we know whether it made it. `pd.merge_asof(..., allow_exact_matches=False)` looks up the running totals strictly before each purchase ([`etl/features.py`](backend/etl/features.py)). |
| The test period is strictly later than training | Train on orders bought before **1 Feb 2018** whose promised date is also before it (so no training label comes from the future), test on everything bought after ([`ml/train.py`](backend/ml/train.py)). |
| The test set is used once | The feature set is chosen by rolling-origin CV *inside* the training window and the alert threshold on its last 15%. The test period is scored a single time. |
| Results are reproducible | Fixed row order and seeds; two training runs produce identical model cards. |
| Leaks get caught | `test_an_orders_own_outcome_never_changes_its_features` and a brute-force recount of every seller feature. Re-introducing a 60-day look-ahead makes both fail. |

### Results on the held-out period (Feb–Aug 2018, 45,708 orders, 8.0% late)

| Score | ROC-AUC | PR-AUC |
|---|---|---|
| **This model** (HistGradientBoosting, 15 inputs) | **0.653** | **0.142** |
| Seller history alone | 0.498 | 0.082 |
| Recent network-wide miss rate alone | 0.526 | 0.081 |
| Random guessing | 0.500 | 0.080 |

The honest number is lower, and that is the point: lateness in this data is driven mostly by
network-wide shocks rather than by anything about an individual order. The model still earns its
keep as a ranking tool. Its top 10% riskiest orders are late **2.2×** as often as average, and in the
backtest:

| Morning of | In transit | Flagged | Flagged that were late | Late rate of whole queue | Lift |
|---|---|---|---|---|---|
| 15 Mar 2018 (Feb–Mar backlog) | 3,753 | 360 | 74.7% | 39.0% | 1.9× |
| 20 Apr 2018 | 2,701 | 194 | 28.9% | 15.5% | 1.9× |
| 24 May 2018 (national truckers' strike) | 2,163 | 271 | 29.2% | 24.5% | **1.2×** |
| 10 Jul 2018 | 1,579 | 105 | 15.2% | 7.3% | 2.1× |

Two findings the model card surfaces on its own:

- **It cannot see a strike coming.** On 24 May the lift collapses: nothing about an order bought
  a week earlier predicted a nationwide stoppage.
- **It drifts.** In August 2018 Olist shortened its promised windows from ~24 to ~15 days, and the
  model, trained before that, ranks worse than chance that month (ROC-AUC 0.44). In production this
  is the signal to retrain; here it is shown on the Model page rather than hidden.

![Model card](docs/screenshots/model.png)

---

## What's in the app

| Page | What it answers |
|---|---|
| **Overview** | On-time rate, fulfillment rate, delivery time, weekly trend, worst categories and destinations, for any date range |
| **At-risk queue** | The backtest above: replay any morning after the cutoff, inspect each flagged order and the exact features the model saw |
| **Orders** | Filter all 99k orders by status, state, outcome and date; sort by risk; CSV export (analyst role) |
| **Sellers** | Scorecard sortable by late rate, delay and freight, with a per-seller monthly trend |
| **Regions** | Tile map of the 27 states coloured by on-time rate |
| **Model** | The model card: metrics vs. baselines, monthly drift, permutation importance, and a what-if scorer (analyst role) |

![Overview](docs/screenshots/overview.png)

---

## Architecture

```mermaid
flowchart LR
    CSV[(Olist CSVs<br/>full or 25% sample)] --> ETL
    subgraph backend [Python backend]
        ETL[etl.run<br/>extract → transform →<br/>point-in-time features → COPY] --> PG[(PostgreSQL<br/>shipments, users,<br/>revoked_tokens)]
        PG --> TRAIN[ml.train<br/>CV, threshold, test once,<br/>model card]
        TRAIN -->|model.joblib + model_card.json| API
        TRAIN -->|delay_probability per order| PG
        PG --> API[FastAPI<br/>JWT auth · RBAC · SQL aggregates]
    end
    API <--> NGINX[nginx<br/>SPA + /api proxy] <--> UI[React 19 SPA<br/>TanStack Router + Query]
```

- **One fact table.** `shipments` holds one row per order (every status), its outcome, its
  point-in-time features and its model score. KPIs are plain SQL aggregates over it, so there are no
  derived tables to keep in sync.
- **Batch, not streaming.** The ETL replaces the table in one transaction (`TRUNCATE` + `COPY`) in
  about 3 seconds; training takes about 15 seconds and writes every order's score back to the table.
  On container start both run only if needed.
- **Preprocessing travels with the model.** The saved file is a scikit-learn `Pipeline` (derived
  features → ordinal encoding → boosted trees), so the API and the trainer cannot disagree on
  encoding, and unseen categories are handled natively.

### Auth

JWT access tokens (30 min) and single-use refresh tokens (7 days). Rotation is one atomic
`INSERT … ON CONFLICT DO NOTHING` into `revoked_tokens`, so two concurrent refreshes with the same
token cannot both succeed. Roles are ranked (`viewer < analyst < admin`): viewers read, analysts also
export and run what-ifs, admins create users. Login is rate-limited (5/min per IP), unknown e-mails
cost the same bcrypt time as wrong passwords, and the API refuses to start in production with the
default secret.

---

## Running it

### With Docker (recommended)

```bash
docker compose up --build
```

Open <http://localhost:8080> (if that port is taken, run `WEB_PORT=8090 docker compose up --build`).
The sign-in page offers three demo accounts
(`viewer@`, `analyst@`, `admin@logitrack.dev`, password `logitrack-demo`). The first start migrates the
database, loads the bundled 25% sample, trains the model and seeds the accounts (about a minute).

To use all 99k orders, download the dataset from Kaggle, unzip the nine CSVs into `data/raw/`, and
rebuild from scratch:

```bash
docker compose down -v
```

```bash
docker compose up --build
```

### Without Docker

Requires Python 3.12, Node 22 and a PostgreSQL database.

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

```bash
cd frontend && npm install && VITE_DEMO_PASSWORD=logitrack-demo npm run dev
```

The dev server proxies `/api` and `/auth` to `localhost:8000` (override with `API_PROXY_TARGET`).
API docs are at <http://localhost:8000/docs>.

---

## Tests

```bash
cd backend && TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/logitrack_test pytest --cov=app --cov=etl --cov=ml
```

```bash
cd frontend && npm run lint && npm test && npm run build
```

- **Backend (32 tests, 93% coverage).** API tests run against a real PostgreSQL built by the Alembic
  migration, with synthetic Olist-shaped data loaded through the real ETL command. Highlights: the
  leakage tests above; the backtest endpoint checked against an independent pandas recount; KPI
  summary checked against pandas; refresh-token reuse, logout, rate limiting and every role boundary.
- **Frontend.** Formatting helpers and the pagination component; ESLint and `tsc` in CI.
- **CI** (GitHub Actions): lint + tests for both halves, then boots the full Docker stack and logs in
  through nginx.

## Project layout

```
backend/
  app/          FastAPI app: auth/, routers/, models.py, schemas.py, seed.py
  etl/          extract.py → transform.py → features.py (point-in-time) → load.py; run.py, sample.py
  ml/           features.py (pipeline), train.py (split, CV, evaluation, scoring), model_store.py
  alembic/      schema migrations
  tests/        factory.py (synthetic data), unit tests, API tests
frontend/src/
  api/          axios client with token refresh, typed TanStack Query hooks
  pages/        one file per screen
  components/   charts, shipments table/drawer, shared UI
data/sample/    25% sample of the dataset (gzipped), so the demo needs no download
docker/         Dockerfiles and nginx config
```

## Definitions

| Term | Definition |
|---|---|
| Late | Delivered on a calendar day after the promised date (`delay_days > 0`) |
| On-time rate | Share of delivered orders that were not late |
| Fulfillment rate | Share of all orders that were delivered |
| In transit (backtest) | Bought before the as-of morning, not delivered by then, not cancelled, not yet due, and not part of the training set |
| Lift | Late rate among flagged orders ÷ late rate of the whole queue |

## Known limitations and next steps

- **Retraining is manual** (`python -m ml.train`). The August drift says it should be scheduled and
  gated on a monitored metric.
- **Probabilities are not calibration-checked**; a reliability curve on the test period is the next
  evaluation to add.
- **Order grain.** Seller and category come from an order's first item; 1.3% of orders have several
  sellers.
- **Rate limiting is per process** (in memory), so the API runs one worker. Use a Redis backend to
  scale out.
- **Tokens live in `sessionStorage`.** A hardened deployment would keep the refresh token in an
  `httpOnly` cookie.

## Data and license

Code: MIT. Data © Olist, [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/);
`data/sample/` is redistributed under the same license.

Built by [Sina Mohammadhosseinzadeh](https://www.linkedin.com/in/sina-hosseinzade20/).

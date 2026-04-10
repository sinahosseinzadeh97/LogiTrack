# LogiTrack — LinkedIn Announcement Post

> **Instructions**: Copy the post below. Add 1-2 screenshots from `pics/` before posting (Overview dashboard + Prediction page work best). Tag any collaborators if applicable. Post on a Tuesday or Wednesday morning for best reach.

---

## Post

I just finished building LogiTrack — a full-stack logistics intelligence platform, from raw CSVs to a production-ready React dashboard with ML-powered delay prediction.

Here's what it does and what I learned building it:

**The problem it solves:**
Logistics teams are reactive. They find out about delays *after* customers complain. LogiTrack turns 96,000 real Brazilian e-commerce orders into proactive intelligence — live KPIs, seller scorecards, and a RandomForest classifier that scores shipment delay risk *before* orders ship.

**What I built — end to end:**

→ A 3-stage ETL pipeline that ingests 9 CSV files into PostgreSQL in ~25 seconds. Geodesic distance computed per shipment, batch upserted in chunks of 1,000. Fully idempotent — safe to re-run.

→ A KPI engine producing 612 daily snapshots: OTIF rate (91.9%), average delay, fulfillment rate, cost per shipment, week-over-week deltas, and per-seller scorecards across 2,960 sellers.

→ An ML layer: RandomForest with `class_weight='balanced'` on 8% imbalanced data. MLflow tracks every experiment. The model auto-retrains weekly and is only promoted if F1 improves on the holdout set. Zero-downtime promotion via a pointer swap in MinIO S3.

→ 26 REST endpoints with JWT auth, refresh token rotation, 3-tier RBAC (viewer / analyst / admin), and rate limiting via Redis.

→ A React 18 dashboard — 9 pages, animated KPI cards, live prediction gauge, PDF report generation.

→ 5-job GitHub Actions CI: lint + test in parallel → build → Trivy container security scan. Backend coverage gate at 80%.

**Numbers:**
- 96,478 orders ingested
- 612 KPI daily snapshots
- 2,960 seller scorecards
- 26 API endpoints
- 7,826 late shipments flagged
- ~25s ETL runtime
- F1 0.62 / ROC-AUC 0.78 on imbalanced delay classification
- 80%+ test coverage

**What I'd do differently:**
I'd add real-time ingestion via Kafka from day one. Polling works, but streaming would unlock same-day alerting instead of next-day. I'd also swap APScheduler for Celery + Redis for better observability into job failures.

The full project — code, docs, architecture diagrams, and a 5-minute demo script — is on GitHub. Link in comments.

If you're working on logistics analytics, supply chain visibility, or ML-powered operations tooling, I'd love to connect.

#Python #FastAPI #React #MachineLearning #MLflow #PostgreSQL #Docker #DataEngineering #FullStack #Logistics #SupplyChain #OpenSource

---

## Shorter Variant (for lower-scroll feed)

I spent the last few months building a production-grade logistics analytics platform from scratch. Here's the one-line pitch: ingest 96,000 real shipping orders → compute live KPIs → score delay risk with ML → deliver everything through a React dashboard.

The stack: FastAPI + PostgreSQL + scikit-learn + MLflow + React 18 + Docker Compose + GitHub Actions CI.

The part I'm most proud of: the ML retraining pipeline. Every week it retrains on fresh data, evaluates F1 on a holdout set, and only promotes the new model if it's actually better. The old model is never deleted. Zero-downtime promotion via a model-bundle pointer swap in S3.

Full code + docs on GitHub. Link in comments.

#Python #MachineLearning #FastAPI #React #DataEngineering #FullStack

---

## Comment to Pin (paste as first comment after posting)

GitHub repo: [link]
Live demo walkthrough: [link to SHOWCASE.md or video if available]
Technical deep dive: [link to TECHNICAL_DEEP_DIVE.md]

# LogiTrack — 5-Minute Live Demo Script

> **Audience**: Potential employer (technical interview) or business client (stakeholder demo)  
> **Format**: Timestamped sections — what to **SAY** and what to **CLICK / SHOW**  
> **Setup before you present**: API running on `:8001`, frontend on `:5175` (or `:5173`), logged in as admin

---

## [TIME: 0:00 – 0:30] — Introduction

**SAY:**
> "I'm going to show you LogiTrack — a production-grade logistics intelligence platform I built end-to-end. It ingests 96,000 real Brazilian e-commerce orders, computes live KPIs, runs an ML delay-risk classifier, and delivers everything through a React dashboard. I'll walk you through it in five minutes."

**SHOW:**
- Have the **Overview dashboard** already open at `http://localhost:5175`
- Make sure the top KPI cards are visible — let the animated numbers draw the eye

---

## [TIME: 0:30 – 1:30] — Problem & Solution

**SAY:**
> "The problem logistics teams face is reactive visibility — they find out about delays *after* customers complain. LogiTrack solves this with three layers:
> 
> **Layer 1 — Historical truth.** A 3-stage ETL pipeline ingests 9 CSV files, computes geodesic distances per shipment, and loads 96,000 orders into PostgreSQL in about 25 seconds. That gives us 612 daily KPI snapshots.
>
> **Layer 2 — Live alerting.** The KPI engine flags shipments crossing risk thresholds — OTIF rate, delay trends, seller scorecards — so operations teams see problems forming, not after they've landed.
>
> **Layer 3 — Predictive.** A RandomForest classifier scores any new shipment for delay probability before it ships. That's the proactive piece."

**SHOW:**
- Stay on the **Overview page**
- Point to the four KPI cards: OTIF 91.9%, Avg Delay 9.6 days, Fulfillment Rate, Avg Cost
- Point to the **8-week OTIF trend chart** — "this shows the week-over-week direction"
- Scroll down to show the **Recent Shipments** or late-shipment summary at the bottom

---

## [TIME: 1:30 – 3:00] — Live Demo Walkthrough

### 1:30 — Overview Dashboard

**CLICK:** Stay on Overview — highlight KPI cards  
**SAY:**
> "The four headline KPIs update in real time from the API. OTIF is 91.9% — we have about 7,800 late shipments out of 96,000 orders. The trend chart shows whether we're improving week over week. All of this is computed server-side; the frontend just queries the cache."

---

### 1:50 — Drill into Sellers

**CLICK:** Navigate to **Sellers** page  
**SAY:**
> "Every seller gets a scorecard — delay rate, average delay days, average freight cost. This is sortable. If I click *Delay Rate* descending..."

**CLICK:** Click the **Delay Rate** column header to sort  
**SAY:**
> "...I instantly see which sellers are dragging down my OTIF. Click any row..."

**CLICK:** Click a seller row to open the **Seller Detail** page  
**SAY:**
> "...and I get their full history — volume trend, top categories, worst shipments. This is the drill-down that operations teams need to have vendor conversations."

---

### 2:20 — Alerts

**CLICK:** Navigate to **Alerts** page  
**SAY:**
> "The alerts engine runs the ML classifier across all open shipments and surfaces anything above 65% delay probability. High-risk is above 80%. I can filter to just High Risk..."

**CLICK:** Click **High Risk (>80%)** filter button  
**SAY:**
> "...and immediately see the shipments that need attention today. Clicking a row opens the full shipment detail."

**CLICK:** Click one alert row to open the **ShipmentDrawer**  
**SAY:**
> "Order ID, seller, buyer state, distance, estimated vs actual delivery — everything in one panel."

**CLICK:** Close the drawer

---

### 2:45 — Prediction Form

**CLICK:** Navigate to **Prediction** page  
**SAY:**
> "This is the proactive piece. Before a shipment even enters the system, I can score it. Let me try a worst-case scenario — 3,000 km from São Paulo to Amazonas, heavy furniture, Friday dispatch."

**CLICK/TYPE:** Set values — Distance: `3000`, State: `AM`, Category: `moveis_decoracao`, Day: `Friday`, Freight: `80`, Price: `600`  
**CLICK:** Click **Predict Delay Risk**  
**SAY:**
> "The model returns a probability and a risk band. The gauge animates to the result. This is a RandomForest trained on 8 features with MLflow tracking every experiment — F1 score, ROC-AUC, hyperparameters. If a retrain next week produces a better F1 on the holdout set, it gets auto-promoted. The old model is never deleted."

---

### 3:00 — PDF Report (briefly)

**CLICK:** Navigate to **Reports** page  
**SAY:**
> "Every Monday at 09:00 UTC, the system auto-generates a 5-page PDF — KPI summary, OTIF chart, critical sellers, flagged shipments. I can also trigger one on demand."

**CLICK:** Click **Generate Report** button (don't wait — just show the `pending → success` polling)  
**SAY:**
> "It's stored in MinIO S3 and the frontend polls every 15 seconds. The download link appears when it's ready."

---

## [TIME: 3:00 – 4:00] — Technical Highlights

**SAY:**
> "A few things I'm proud of technically:"

**SHOW:** Switch to a terminal or the **Swagger UI** at `http://localhost:8001/docs`

1. **SAY:** "26 REST endpoints, full OpenAPI spec. JWT auth with HS256 access tokens, refresh rotation, and a JTI blacklist in Redis. Three-tier RBAC — viewer, analyst, admin. Rate limiting: 5 req/min on login, 100 per user globally via slowapi."

2. **SAY:** "The ETL is fully idempotent — `ON CONFLICT DO UPDATE` in Postgres means I can re-run it any time without duplicating data. Geodesic distance via geopy runs for every seller-to-customer pair."

3. **SAY:** "The ML pipeline logs to MLflow — I can show you the experiment runs, the feature importances, the F1 and ROC-AUC on holdout. The model bundle — model, encoders, threshold — lives in MinIO and loads into `app.state` at startup. Zero-downtime promotion is a pointer swap in S3."

4. **SAY:** "GitHub Actions CI has 5 jobs: lint and test run in parallel, then build, then a Trivy container security scan. Coverage gate is 80%."

**SHOW** (optional — if time allows): Open `http://localhost:5050` (MLflow) to show the experiment tracking UI

---

## [TIME: 4:00 – 5:00] — Questions & What's Next

**SAY:**
> "That's the system. Happy to go deeper on any layer — the ETL, the ML pipeline, the auth system, the Docker setup, or the React architecture."

**Prepare for these likely questions:**

| Likely Question | Talking Point |
|---|---|
| "How does it handle data freshness?" | ETL is idempotent and re-runnable; APScheduler handles weekly retraining |
| "What's the model accuracy?" | F1 ~0.62, ROC-AUC ~0.78 on 8% imbalanced class; `class_weight='balanced'` handles skew |
| "How would you scale this?" | Add read replicas for Postgres, move to Celery/SQS for async jobs, add Redis query cache |
| "Why RandomForest over XGBoost?" | Interpretability + scikit-learn ecosystem; XGBoost is the obvious next model to benchmark |
| "What would you build next?" | Real-time Kafka ingestion, WebSocket notifications for new high-risk alerts, multi-tenant RBAC |

**SAY (closing):**
> "The full code is available — it's a complete production-grade system: migrations, tests at 80%+ coverage, Docker Compose for local and prod, CI/CD. I'm happy to walk through any piece in detail."

---

## Quick Reference — URLs to Have Open

| Tab | URL | Purpose |
|-----|-----|---------|
| Dashboard | `http://localhost:5175` | Main demo surface |
| API Docs | `http://localhost:8001/docs` | Show OpenAPI spec |
| MLflow | `http://localhost:5050` | Show experiment tracking |
| MinIO Console | `http://localhost:9001` | Show model/PDF storage |
| DB (Adminer) | `http://localhost:8080` | Show schema if asked |

---

## Timing Cheat Sheet

```
0:00  Open — intro sentence
0:30  Problem → 3-layer solution
1:30  Overview KPI cards + trend chart
1:50  Sellers → sort by delay → click into seller
2:20  Alerts → filter HIGH → open drawer
2:45  Prediction → fill form → fire prediction
3:00  Reports page → trigger PDF
3:15  Technical highlights (JWT, ETL, MLflow, CI)
4:00  Q&A — use prep table above
```

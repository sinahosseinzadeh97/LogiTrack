# Phase 06 — Automated Weekly PDF Report Generation

**Project:** LogiTrack — Logistics KPI Dashboard & Delay Prediction System
**Phase:** 06 — PDF Reporting
**Completed:** 2026-04-09
**Author:** Engineering Team

---

## 1. All Files Created / Modified

| # | Path | Status | Description |
|---|------|--------|-------------|
| 1 | `backend/reports/__init__.py` | NEW | Reports package init |
| 2 | `backend/reports/report_gen.py` | NEW | `WeeklyReportGenerator` class — 5-page ReportLab PDF |
| 3 | `backend/app/models/report_log.py` | NEW | `ReportLog` SQLAlchemy ORM model |
| 4 | `backend/app/models/__init__.py` | MODIFIED | Added `ReportLog` export |
| 5 | `backend/app/routers/reports.py` | NEW | FastAPI reports router (4 endpoints) |
| 6 | `backend/app/main.py` | MODIFIED | Mounted reports router + APScheduler weekly PDF job |
| 7 | `backend/alembic/versions/0003_add_reports_log.py` | NEW | Alembic migration: `reports_log` table |
| 8 | `backend/pyproject.toml` | MODIFIED | Added `reportlab`, `plotly`, `kaleido`, `pdf2image` |
| 9 | `frontend/src/api/reports.ts` | NEW | Typed API client for reports endpoints |
| 10 | `frontend/src/pages/ReportPage.tsx` | MODIFIED | Full implementation replacing Phase 05 placeholder |
| 11 | `docs/phase-reports/PHASE_06_REPORT.md` | NEW | This document |

---

## 2. Architecture

### PDF Generation Pipeline

```
POST /api/v1/reports/generate
        │
        ▼
Insert pending row → reports_log
        │
        ▼ (BackgroundTask)
_run_report_generation(report_id, week_date)
        │
        ├── WeeklyReportGenerator.__init__()
        │       └── Normalise week to ISO Monday
        │
        ├── generate_with_dark_cover()
        │       ├── _build_cover_page()      → dark bg, white Helvetica text
        │       ├── _build_kpi_summary()     → 2×2 KPI table + WoW delta
        │       ├── _build_otif_chart()      → Plotly → kaleido PNG → Image
        │       ├── _build_seller_critical_list() → top-5 worst sellers
        │       └── _build_flagged_shipments()    → all late orders this week
        │
        ├── s3.put_object(Key="reports/weekly_report_YYYY-WW.pdf")
        │
        └── UPDATE reports_log SET status='success', s3_path=…, file_size_bytes=…
              (or status='failed', error_message=… on exception)
```

### Scheduler

```
lifespan startup
    └── _schedule_weekly_report(sync_engine)
            └── APScheduler BackgroundScheduler
                    └── CronTrigger(day_of_week="mon", hour=9, minute=0, tz=UTC)
                            └── _job()
                                    ├── Insert pending ReportLog row
                                    └── _run_report_generation(report_id, monday)
```

---

## 3. API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/reports/generate` | analyst+ | Trigger PDF generation (BackgroundTask) |
| `GET`  | `/api/v1/reports` | viewer+ | List all reports from `reports_log` |
| `GET`  | `/api/v1/reports/{id}/download` | viewer+ | 307 redirect to presigned S3 URL (15 min) |
| `GET`  | `/api/v1/reports/{id}/preview` | viewer+ | First 3 pages as base64 PNG (pdf2image) |

### POST /generate Response
```json
{
  "message": "Report generation started for week 2025-W15.",
  "report_id": 3
}
```

### GET /reports Response
```json
[
  {
    "id": 3,
    "week": "2025-W15",
    "generated_at": "2025-04-14T09:00:01Z",
    "s3_path": "reports/weekly_report_2025-W15.pdf",
    "status": "success",
    "file_size_bytes": 182340
  }
]
```

---

## 4. Database Model — `reports_log`

| Column | Type | Description |
|--------|------|-------------|
| `id` | `INTEGER PK` | Auto-increment primary key |
| `week` | `VARCHAR(10)` | ISO week string, e.g. `"2025-W15"` |
| `generated_at` | `TIMESTAMPTZ` | Server-side `NOW()` on insert |
| `s3_path` | `VARCHAR(500)` | S3 key set after successful upload |
| `status` | `VARCHAR(20)` | `pending` / `success` / `failed` |
| `file_size_bytes` | `INTEGER` | PDF size in bytes |
| `error_message` | `VARCHAR(2000)` | Exception text on failure |

Migration: `0003_add_reports_log.py` (revises `0002`).

---

## 5. PDF Content

| Page | Content |
|------|---------|
| 1 — Cover | Dark background (`#0a0c10`), LogiTrack title, ISO week label, date range, generated timestamp |
| 2 — KPI Summary | 2×2 table: OTIF %, Avg Delay, Fulfillment %, Avg Cost/Shipment — WoW delta with ↑ (green) / ↓ (red); plus totals row |
| 3 — OTIF Trend | Plotly 8-week line chart exported via kaleido as PNG, embedded as `Image` flowable |
| 4 — Critical Sellers | Top-5 worst-delay-rate sellers: seller ID, state, orders, late, delay %, avg delay, avg cost |
| 5 — Flagged Shipments | All `is_late=TRUE` orders this week (up to 200): order ID, seller, states, category, delay days, value R$ |

### Design Rules Implemented

- **No external fonts** — Helvetica throughout (`Helvetica`, `Helvetica-Bold`)
- **Cover**: dark background via `onFirstPage` canvas callback (`draw_cover_background`)
- **Table headers**: `#0a0c10` background, white text, `Helvetica-Bold`
- **Alternating rows**: white / `#f8f8f8`
- **Positive delta**: green `↑` arrow; negative: red `↓` arrow
- **Currency**: `R$` format throughout

---

## 6. Frontend — ReportPage.tsx

| Feature | Detail |
|---------|--------|
| Report list | Table with week label, generated date, status badge, file size, actions |
| Status badges | `pending` (amber spinner), `success` (green checkmark), `failed` (red X) |
| Live polling | `refetchInterval: 15_000` — catches `pending → success` without manual refresh |
| Generate Now | Visible to `analyst` / `admin` only; disabled during mutation |
| Download | `window.open` to presigned URL via `GET /{id}/download` redirect |
| Preview modal | Fetches base64 PNG thumbnails from `GET /{id}/preview`; shows first 3 pages |
| Schedule card | Shows next Monday 09:00 UTC calculated client-side |
| Stats bar | Total / Ready / Pending / Failed counts |
| Empty state | Friendly message + Generate button for analysts |

---

## 7. Dependencies Added

| Package | Version | Purpose |
|---------|---------|---------|
| `reportlab` | ≥ 4.1.0 | PDF layout engine (pure Python, no font deps) |
| `plotly` | ≥ 5.21.0 | OTIF chart figure creation |
| `kaleido` | ≥ 0.2.1 | Server-side Plotly → PNG export |
| `pdf2image` | ≥ 1.17.0 | PDF → PNG for preview thumbnails |

> **Note:** `pdf2image` requires `poppler` installed at the OS level.
> On macOS: `brew install poppler`
> On Ubuntu/Docker: `apt-get install -y poppler-utils`

---

## 8. How to Apply the Migration

```bash
cd backend
source .venv/bin/activate

# Apply the new migration
alembic upgrade head

# Verify
alembic current
# Expected: 0003 (head)
```

---

## 9. How to Run

```bash
# Backend
cd backend && uvicorn app.main:app --reload

# Frontend
cd frontend && npm run dev
```

Navigate to `/reports` in the dashboard. Use an analyst account to click
**Generate Now**. The row will appear with `pending` status and flip to
`success` within seconds (or `failed` if S3 is unreachable).

---

## 10. Notes for Phase 07

| Topic | Detail |
|-------|--------|
| **Brazil Choropleth Map** | `RegionsPage.tsx` is still a placeholder. Install `react-leaflet` + Brazil GeoJSON; color states by `seller_state` delay rate from the seller-scorecard endpoint. |
| **HttpOnly Refresh Token** | Migrate `refresh_token` from `sessionStorage` to a `Set-Cookie: HttpOnly; Secure; SameSite=Strict` response header. |
| **WebSocket KPI Push** | Wire `GET /ws/kpi` to `useKPISummary` — replace polling with a WebSocket stream for sub-second dashboard updates. |
| **Report Email Delivery** | After S3 upload, send the presigned URL via email (SendGrid / SES) to subscribed analysts. |
| **PDF Caching** | Add a check in `POST /generate` — if a `success` report already exists for the current ISO week, return the existing `report_id` instead of regenerating. |

# Phase 02 — KPI Engine, Test Suite & API Schemas

**Project:** LogiTrack — Logistics KPI Dashboard & Delay Prediction System  
**Phase:** 02 — KPI Engine  
**Completed:** 2026-04-09  
**Author:** Engineering Team  

---

## 1. Files Created

| # | Path | Description |
|---|------|-------------|
| 1 | `backend/core/__init__.py` | Core package marker |
| 2 | `backend/core/kpi_engine.py` | Pure-function KPI calculation engine (single source of truth) |
| 3 | `backend/core/schemas.py` | Pydantic v2 response schemas for Phase 3 API routers |
| 4 | `backend/tests/__init__.py` | Test package marker |
| 5 | `backend/tests/test_kpis.py` | 20 pytest tests with deterministic synthetic fixtures |
| 6 | `docs/phase-reports/PHASE_02_REPORT.md` | This document |

---

## 2. KPI Formula Reference

| KPI | Formula | Edge Cases Handled |
|-----|---------|-------------------|
| **OTIF Rate** | `(rows where is_late == False) / total_rows × 100` | `ValueError` on empty DataFrame |
| **Avg Delay Days (scalar)** | `mean(delay_days) where is_late == True` (default) or over all rows when `only_late=False` | Returns `NaN` when no late rows exist after filter; `ValueError` on empty df |
| **Avg Delay Days (grouped)** | Same as scalar but per `group_by` column; joined back to group index | Groups with zero late orders receive `NaN` avg_delay_days |
| **Fulfillment Rate** | `(rows where order_status == 'delivered') / total_rows × 100` applied to `df_all` | `ValueError` on empty DataFrame; correctly handles cancelled / unavailable statuses |
| **Cost per Shipment** | `mean(freight_value)` over delivered rows | `ValueError` on empty DataFrame |
| **Weekly OTIF Trend** | Per ISO week: `(~is_late).sum() / week_row_count × 100`; anchors to latest timestamp in dataset, not wall-clock | Weeks with no deliveries return `NaN`; total row count always equals `weeks` param |
| **Delay by Category** | Per `category_name`: `mean(delay_days) where is_late == True` + `count(*)` | `NaN` category rows dropped; categories with no late orders receive `NaN` avg |
| **Seller Scorecard** | Per `seller_id`: `count`, `mean(is_late)` as `delay_rate`, `mean(delay_days where is_late)`, `mean(freight_value)` | Sellers with zero late orders receive `NaN` avg_delay_days; sorted by `delay_rate` desc |
| **KPI Summary** | Calls all 6 KPIs above; adds `total_shipments`, `late_shipments`; computes week-over-week OTIF delta from the two most recent ISO weeks in df | `wow_delta` is `None` when dataset has fewer than 2 distinct weeks |

---

## 3. Test Coverage Summary

### Fixture Design

The synthetic fixture (`sample_df`) encodes exact, auditable quantities:

| Property | Value |
|----------|-------|
| Total rows | 110 |
| Late rows | 24 (≈21.8%) |
| On-time rows | 86 |
| `freight_value` | 10.0 (all rows) → `cost_per_shipment = 10.0` |
| Categories | `"electronics"` (70 rows, 14 late), `"furniture"` (40 rows, 10 late) |
| Sellers | `"seller_A"` (70 rows, 14 late), `"seller_B"` (40 rows, 10 late) |
| ISO weeks | 2 distinct weeks |

`sample_df_all` = `sample_df` (110 rows, status=delivered) + 10 cancelled rows → 120 total.  
Expected fulfillment rate = 110/120 × 100 ≈ 91.667%.

### Test Inventory

| # | Test Name | Function Tested | What is Asserted |
|---|-----------|----------------|-----------------|
| 1 | `test_otif_returns_100_when_all_on_time` | `calculate_otif` | Returns exactly 100.0 on all-on-time fixture |
| 2 | `test_otif_returns_0_when_all_late` | `calculate_otif` | Returns exactly 0.0 on all-late fixture |
| 3 | `test_otif_returns_correct_percentage` | `calculate_otif` | Returns `(on_time / total) × 100` matching hand-computed expected value |
| 4 | `test_otif_raises_on_empty_dataframe` | `calculate_otif` | Raises `ValueError` containing "must not be empty" |
| 5 | `test_avg_delay_scalar_when_no_group_by` | `calculate_avg_delay` | Return type is `float` when `group_by=None` |
| 6 | `test_avg_delay_excludes_on_time_when_only_late_true` | `calculate_avg_delay` | Result equals `mean(delay_days[is_late])` |
| 7 | `test_avg_delay_includes_all_when_only_late_false` | `calculate_avg_delay` | Result equals `mean(delay_days)` over all rows |
| 8 | `test_avg_delay_grouped_returns_dataframe` | `calculate_avg_delay` | Return type is `pd.DataFrame` |
| 9 | `test_avg_delay_grouped_has_correct_columns` | `calculate_avg_delay` | Columns are exactly `[group_by, 'avg_delay_days']` |
| 10 | `test_avg_delay_raises_on_empty_dataframe` | `calculate_avg_delay` | Raises `ValueError` |
| 11 | `test_fulfillment_rate_correct_ratio` | `calculate_fulfillment_rate` | Returns `delivered / total × 100` |
| 12 | `test_fulfillment_rate_raises_on_empty` | `calculate_fulfillment_rate` | Raises `ValueError` |
| 13 | `test_cost_per_shipment_correct_mean` | `calculate_cost_per_shipment` | Returns 10.0 (all freight_value = 10.0) |
| 14 | `test_cost_per_shipment_raises_on_empty` | `calculate_cost_per_shipment` | Raises `ValueError` |
| 15 | `test_weekly_otif_trend_returns_correct_week_count` | `calculate_weekly_otif_trend` | `len(result) == weeks` param |
| 16 | `test_weekly_otif_trend_columns` | `calculate_weekly_otif_trend` | Columns are `['week_start', 'otif_rate']` |
| 17 | `test_delay_by_category_sorted_descending` | `calculate_delay_by_category` | `avg_delay_days` column is non-increasing |
| 18 | `test_seller_scorecard_sorted_by_delay_rate` | `calculate_seller_scorecard` | `delay_rate` column is non-increasing |
| 19 | `test_kpi_summary_contains_all_keys` | `calculate_kpi_summary` | Dict has exactly the 7 specified keys |
| 20 | `test_kpi_summary_week_over_week_delta_is_correct` | `calculate_kpi_summary` | Delta equals independently computed `current_week_OTIF - prev_week_OTIF` |

### Edge Cases Covered

- Empty DataFrame → `ValueError` (tests 4, 10, 12, 14)  
- All rows on-time → OTIF = 100 (test 1)  
- All rows late → OTIF = 0 (test 2)  
- `only_late=False` includes on-time rows in average (test 7)  
- Grouped result preserves correct column names (test 9)  
- Weeks with no data appear with `NaN` OTIF (implicit in test 15 reindex logic)  
- `week_over_week_otif_delta` computed against live data, not hard-coded (test 20)  

---

## 4. Pydantic Schema List

| Schema | Used By | Key Fields |
|--------|---------|------------|
| `KPISummaryResponse` | `GET /api/v1/kpi/summary` | 7 top-level KPI fields; `week_over_week_otif_delta` is nullable |
| `OTIFTrendPoint` | `GET /api/v1/kpi/otif-trend` | `week_start: date`, `otif_rate: float \| None` |
| `DelayByCategoryItem` | `GET /api/v1/kpi/delay-by-category` | `category_name`, `avg_delay_days`, `order_count` |
| `SellerScorecardItem` | `GET /api/v1/sellers/scorecard` | `seller_id`, `seller_state`, `total_orders`, `delay_rate`, `avg_delay_days`, `avg_cost` |
| `ShipmentDetail` | `GET /api/v1/shipments/{order_id}` + list | Full row with optional `prediction_probability` for ML enrichment |
| `PaginatedShipments` | `GET /api/v1/shipments` | `items: list[ShipmentDetail]`, `total`, `page`, `page_size`, `total_pages` |

All schemas use Pydantic `Field(...)` with:
- `description` — human-readable API docs string
- `ge` / `le` — numeric bounds where applicable
- `| None` union type for optional fields with `default=None`

---

## 5. How to Run Tests

```bash
# From the backend/ directory with venv activated
cd backend
source .venv/bin/activate   # or: .venv\Scripts\activate on Windows

# Install dependencies (if not already done)
pip install -e ".[dev]"

# Run the full KPI test suite
pytest tests/ -v --tb=short

# With coverage report
pytest tests/ -v --tb=short --cov=core --cov-report=term-missing
```

Expected output (all 20 tests green):
```
tests/test_kpis.py::test_otif_returns_100_when_all_on_time         PASSED
tests/test_kpis.py::test_otif_returns_0_when_all_late              PASSED
tests/test_kpis.py::test_otif_returns_correct_percentage            PASSED
tests/test_kpis.py::test_otif_raises_on_empty_dataframe            PASSED
tests/test_kpis.py::test_avg_delay_scalar_when_no_group_by         PASSED
tests/test_kpis.py::test_avg_delay_excludes_on_time_when_only_late_true  PASSED
tests/test_kpis.py::test_avg_delay_includes_all_when_only_late_false     PASSED
tests/test_kpis.py::test_avg_delay_grouped_returns_dataframe       PASSED
tests/test_kpis.py::test_avg_delay_grouped_has_correct_columns     PASSED
tests/test_kpis.py::test_avg_delay_raises_on_empty_dataframe       PASSED
tests/test_kpis.py::test_fulfillment_rate_correct_ratio            PASSED
tests/test_kpis.py::test_fulfillment_rate_raises_on_empty          PASSED
tests/test_kpis.py::test_cost_per_shipment_correct_mean            PASSED
tests/test_kpis.py::test_cost_per_shipment_raises_on_empty         PASSED
tests/test_kpis.py::test_weekly_otif_trend_returns_correct_week_count  PASSED
tests/test_kpis.py::test_weekly_otif_trend_columns                 PASSED
tests/test_kpis.py::test_delay_by_category_sorted_descending       PASSED
tests/test_kpis.py::test_seller_scorecard_sorted_by_delay_rate     PASSED
tests/test_kpis.py::test_kpi_summary_contains_all_keys             PASSED
tests/test_kpis.py::test_kpi_summary_week_over_week_delta_is_correct   PASSED

========================= 20 passed in X.XXs =========================
```

---

## 6. Notes for Phase 3 (API Layer)

### What the API needs to know

| Topic | Detail |
|-------|--------|
| **Data source** | All KPI functions expect in-memory DataFrames. The API router must load data from the DB via SQLAlchemy and convert to DataFrame *before* calling the engine. A `get_shipments_df()` dependency helper is recommended. |
| **`df` vs `df_all`** | `df` = `SELECT * FROM shipments` (delivered, post-ETL). `df_all` = all orders including cancelled — requires a separate query or a union with status filtering. |
| **`fulfillment_rate`** | Phase 1 ETL sets `kpi_daily.fulfillment_rate = 1.0` (placeholder). Phase 3 must recompute it live from `df_all` via `calculate_fulfillment_rate`. |
| **`week_over_week_otif_delta`** | Returns `None` if dataset has < 2 ISO weeks. API serialiser must handle `null` JSON. `KPISummaryResponse.week_over_week_otif_delta` is already typed `float \| None`. |
| **`prediction_probability`** | `ShipmentDetail.prediction_probability` is optional. Populate it only when `ml_model_versions.is_active == True`. Otherwise leave as `None`. |
| **Pagination** | The `PaginatedShipments` schema is framework-agnostic. The router must compute `total_pages = ceil(total / page_size)` before constructing the response. |
| **Filter parameters** | Phase 3 should support `seller_id`, `seller_state`, `is_late`, `date_from`, `date_to`, `category_name` as optional query params on the shipments endpoint. |
| **Performance** | For dashboards serving realtime traffic, cache `get_shipments_df()` with a short TTL (e.g. 60 s via `functools.lru_cache` keyed on query hash or a Redis cache). The KPI engine itself is stateless and requires no caching. |
| **Schema location** | Import from `core.schemas`, not from `app.*`, to keep the engine layer independent of FastAPI. |

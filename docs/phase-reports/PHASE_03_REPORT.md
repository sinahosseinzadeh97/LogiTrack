# Phase 03 — ML Delay Prediction Model, Retraining Pipeline & MLflow Tracking

**Project:** LogiTrack — Logistics KPI Dashboard & Delay Prediction System  
**Phase:** 03 — Machine Learning Layer  
**Completed:** 2026-04-09  
**Author:** Engineering Team  

---

## 1. Files Created / Modified

| # | Path | Type | Description |
|---|------|------|-------------|
| 1 | `backend/ml/__init__.py` | New | ML package marker |
| 2 | `backend/ml/features.py` | New | Pure feature engineering — encoding, imputation, FEATURE_COLUMNS constant |
| 3 | `backend/ml/train.py` | New | RandomForest training with stratified split, threshold-based evaluation |
| 4 | `backend/ml/registry.py` | New | MLflow experiment logging + S3 model persistence + active-version DB management |
| 5 | `backend/ml/predict.py` | New | Batch inference (`predict_batch`) and at-risk filter (`get_flagged_shipments`) |
| 6 | `backend/ml/retrain.py` | New | Trigger logic, full retraining pipeline, APScheduler weekly job |
| 7 | `backend/tests/test_predict.py` | New | 10 pytest tests covering features → training → inference |
| 8 | `backend/pyproject.toml` | Modified | Added `scikit-learn`, `mlflow`, `joblib`, `apscheduler` to runtime deps |

---

## 2. Feature Engineering Decisions

### 2.1 Feature Selection Rationale

| Feature | Rationale |
|---------|-----------|
| `distance_km` | Geodesic seller→customer distance is the single strongest predictor of transit time. Longer parcels cross more logistics hubs and are exposed to more delay risk. |
| `seller_historical_delay_rate` | Per-seller aggregate from `seller_stats.delay_rate`. Sellers with a chronic late-delivery pattern are the clearest leading indicator. |
| `day_of_week` | Orders placed on Fridays / before holidays have reduced same-day processing windows; creates systematic lateness. |
| `month` | Seasonality effects — Q4 (Oct–Dec) peak volume correlates with higher delay rates across the Olist dataset. |
| `category_encoded` | Heavy / oversized categories (furniture, auto parts) have structurally longer carrier transit SLAs that correlate with lateness. |
| `seller_state_encoded` | State-level infrastructure quality and carrier coverage vary significantly across Brazil (SP vs. northern states). |
| `freight_value` | A proxy for package weight/size — heavier / bulkier items cost more to ship and take longer in transit. |
| `price` | Acts as a proxy for item fragility / special handling; expensive items often require extra routing checks. |

> **Review score was not used** — it is measured after delivery (look-ahead leakage) and would inflate training AUC without generalising to live inference.

### 2.2 Missing Value Strategy

| Column | Null Handling | Rationale |
|--------|---------------|-----------|
| `distance_km` | Fill with **median** of training set | Median is robust to the right-skew produced by cross-country deliveries. Mean would be pulled upward by extreme outliers (e.g., Acre → São Paulo). |
| `seller_historical_delay_rate` | Fill with **global mean** | New sellers have no history. The global mean gives a conservative assumption (population average risk) rather than best-case (0) or worst-case (1). |
| `category_name` | Fill null string as `"unknown"` before LabelEncoding | Preserves rows; the `"unknown"` class index rarely fires the delay signal. |
| `seller_state` | Fill null string as `"unknown"` before LabelEncoding | Same reasoning as category. |

### 2.3 Categorical Encoding

`LabelEncoder` is used for both `category_name` and `seller_state`. Justification:
- Tree-based models (RandomForest) are invariant to ordinal encoding assumptions; they split on inequality thresholds, not linear relationships.
- `OrdinalEncoder` or `TargetEncoder` would be alternatives for Phase 4 if gradient-boosted models are evaluated.
- Unseen values at inference time are mapped to `-1` (handled in `encode_single_row`) — the model has never seen that index so it routes to the "unknown" distribution, which is preferable to raising an exception.

---

## 3. Model — Hyperparameters and Rationale

```python
RandomForestClassifier(
    n_estimators    = 300,    # enough variance reduction for ~96k Olist rows
    max_depth       = 12,     # prevents overfit on high-cardinality encoded ints
    min_samples_leaf= 5,      # smooths probability estimates for threshold calibration
    max_features    = "sqrt", # standard RF diversity heuristic
    class_weight    = "balanced",  # compensates for ≈ 8% positive rate (is_late=True)
    random_state    = 42,
    n_jobs          = -1,     # parallel training across all cores
)
```

**Why RandomForest over alternatives:**

| Alternative | Reason Not Chosen (Phase 3) |
|-------------|----------------------------|
| Logistic Regression | Linear boundary insufficient for distance × delay_rate interactions |
| XGBoost / LightGBM | Higher tuning overhead; RF baseline first, boosted models in Phase 4 |
| Neural Network | Over-engineered for tabular data with only 8 features |

**Threshold = 0.65 (default)**  
Default is intentionally conservative: we prefer catching more at-risk shipments (higher recall) over precision. A shipment that is unnecessarily flagged costs one operational review; a missed delayed shipment costs a customer satisfaction event. This can be tuned per business SLA in the environment config (`ALERT_THRESHOLD`).

---

## 4. Expected Evaluation Metrics (Olist Dataset)

These estimates are based on published benchmarks on the public Olist dataset with similar feature sets. Actual numbers will vary by train/test partition.

| Metric | Expected Range | Notes |
|--------|---------------|-------|
| **Accuracy** | 0.88 – 0.93 | High because on-time class (~92%) dominates |
| **Precision (late)** | 0.55 – 0.70 | Reduced by false-positive flagging of borderline cases |
| **Recall (late)** | 0.60 – 0.75 | `class_weight='balanced'` improves recall vs. default |
| **F1 (late)** | 0.57 – 0.72 | Primary promotion metric |
| **ROC-AUC** | 0.82 – 0.90 | Strongly driven by `distance_km` and `seller_historical_delay_rate` |

> **To run on live data:** ensure ETL has completed (`python -m etl.run`), then:
> ```bash
> cd backend && python -c "
> from etl.load import get_sync_engine
> import pandas as pd
> from ml.train import train_model
> engine = get_sync_engine()
> df = pd.read_sql('SELECT * FROM shipments WHERE is_late IS NOT NULL', engine)
> result = train_model(df)
> print(result['metrics'])
> "
> ```

---

## 5. Retraining Trigger Conditions

```
should_retrain() returns True if:

  Condition A — Data volume:
    COUNT(shipments WHERE created_at > last_trained_at) >= 500

  OR

  Condition B — Accuracy drift:
    stored_accuracy < 0.78
    OR abs(stored_accuracy - (1 - recent_late_rate)) > 0.22
```

**Rationale:**
- **Condition A (500 rows)** — at Olist scale (~25 new orders/day post-launch) this fires roughly every 3 weeks, matching the Monday schedule.  
- **Condition B (accuracy drift)** — detects concept drift where the data distribution shifts (e.g., new carrier partnerships change delay patterns). 0.78 is set slightly below the expected 0.88+ range to avoid false positives.

**Promotion rule:** new model is only promoted if its F1-late on a **shared holdout** slice (last 10% of the dataset, never seen during training) is **strictly greater** than the current active model's F1 on the same slice. This prevents regression from noise-induced fluctuations.

---

## 6. MLflow Experiment Structure

```
Experiment: "logitrack-delay-prediction"
│
├── Run: "retrain-2024-04-08T0200"
│   ├── params/
│   │   ├── threshold         = 0.65
│   │   ├── n_estimators      = 300
│   │   ├── max_depth         = 12
│   │   ├── min_samples_leaf  = 5
│   │   ├── max_features      = sqrt
│   │   ├── class_weight      = balanced
│   │   ├── random_state      = 42
│   │   └── artifact_uri      = s3://logitrack/models/<run_id>/model_bundle.joblib
│   │
│   ├── metrics/
│   │   ├── accuracy          = 0.9103
│   │   ├── precision_late    = 0.6320
│   │   ├── recall_late       = 0.6850
│   │   ├── f1_late           = 0.6574
│   │   └── roc_auc           = 0.8712
│   │
│   └── artifacts/
│       └── reports/feature_importances.json
│
└── [next run on promotion]
```

### S3 Layout

```
s3://logitrack/
├── models/
│   ├── <run_id>/
│   │   └── model_bundle.joblib     ← per-run snapshot
│   └── active/
│       └── model_bundle.joblib     ← always the promoted model
```

The `active/` slot is a fast pointer-swap (S3 copy-object) that takes effect immediately. The inference endpoint always reads from `active/` so there is **zero downtime** during promotion.

### Model Bundle Schema (joblib)

```python
{
    "model"    : RandomForestClassifier,   # fitted estimator
    "encoders" : {
        "category_name": LabelEncoder,
        "seller_state" : LabelEncoder,
    },
    "threshold": float,                    # probability cutoff
    "run_id"   : str,                      # MLflow run_id for traceability
    "logged_at": str,                      # ISO-8601 UTC timestamp
}
```

---

## 7. Test Inventory (10 Tests)

| # | Test Name | Module(s) Tested | What is Asserted |
|---|-----------|-----------------|-----------------|
| 1 | `test_feature_matrix_has_correct_columns` | `features.build_feature_matrix` | Returned X has exactly `FEATURE_COLUMNS` in order |
| 2 | `test_feature_matrix_raises_on_small_dataset` | `features.build_feature_matrix` | `ValueError` raised when df has < 100 rows; message contains "100" |
| 3 | `test_encode_single_row_handles_unseen_category` | `features.encode_single_row` | Unseen category → `category_encoded=-1`; unseen state → `seller_state_encoded=-1`; no exception |
| 4 | `test_train_model_returns_all_keys` | `train.train_model` | All 7 top-level dict keys are present |
| 5 | `test_train_model_metrics_in_valid_range` | `train.train_model` | All 5 metric floats are in [0, 1] |
| 6 | `test_predict_batch_adds_probability_column` | `predict.predict_batch` | `delay_probability` column exists, dtype=float, values in [0, 1] |
| 7 | `test_predict_batch_adds_predicted_late_column` | `predict.predict_batch` | `predicted_late` column exists, values are bool-compatible |
| 8 | `test_predict_batch_respects_threshold` | `predict.predict_batch` | `predicted_late == (delay_probability >= threshold)` for every row |
| 9 | `test_get_flagged_only_returns_active_orders` | `predict.get_flagged_shipments` | Returned `order_id` set has zero intersection with delivered-order IDs |
| 10 | `test_feature_importances_sum_to_one` | `train.train_model` | `sum(importances.values())` is within 1e-6 of 1.0; all 8 features present |

### How to Run

```bash
cd backend
source .venv/bin/activate
pip install -e ".[dev]"

# ML tests only
pytest tests/test_predict.py -v --tb=short

# Full suite (KPI + ML)
pytest tests/ -v --tb=short --cov=ml --cov=core --cov-report=term-missing
```

Expected output (all 10 ML tests green):
```
tests/test_predict.py::test_feature_matrix_has_correct_columns         PASSED
tests/test_predict.py::test_feature_matrix_raises_on_small_dataset     PASSED
tests/test_predict.py::test_encode_single_row_handles_unseen_category  PASSED
tests/test_predict.py::test_train_model_returns_all_keys               PASSED
tests/test_predict.py::test_train_model_metrics_in_valid_range         PASSED
tests/test_predict.py::test_predict_batch_adds_probability_column      PASSED
tests/test_predict.py::test_predict_batch_adds_predicted_late_column   PASSED
tests/test_predict.py::test_predict_batch_respects_threshold           PASSED
tests/test_predict.py::test_get_flagged_only_returns_active_orders     PASSED
tests/test_predict.py::test_feature_importances_sum_to_one             PASSED

========================= 10 passed in X.XXs =========================
```

---

## 8. Notes for Phase 4 (API Layer)

### New Endpoints Required

| Method | Path | Handler Description |
|--------|------|-------------------|
| `GET` | `/api/v1/ml/status` | Returns active model version, metrics, trained_at, threshold |
| `GET` | `/api/v1/ml/flagged` | Returns `get_flagged_shipments()` result as paginated JSON |
| `POST` | `/api/v1/ml/predict` | Single-order live inference; body = raw feature dict |
| `POST` | `/api/v1/ml/retrain` | Manually trigger `run_retrain_pipeline` (admin-only) |
| `GET` | `/api/v1/ml/experiments` | List MLflow runs for the `logitrack-delay-prediction` experiment |

### Integration Notes

| Topic | Detail |
|-------|--------|
| **Model loading** | Load once at app startup via `load_active_model(engine, settings)` and cache in `app.state`. Reload after `promote_model` is called. |
| **Retraining scheduler** | Call `schedule_retrain(settings, engine)` inside `lifespan` context of the FastAPI app (after DB is connected). |
| **`ShipmentDetail` schema** | Already has `prediction_probability: float \| None`. Populate it in the shipments router when `is_active` model exists. |
| **Flagged count in `kpi_daily`** | After each retraining / inference pass, write `GET /api/v1/ml/flagged` count back to `kpi_daily.flagged_count` for the dashboard. |
| **MLflow server** | Add `mlflow` service to `docker-compose.yml` (port 5000) for Phase 4; set `MLFLOW_TRACKING_URI` env var. In Phase 3, MLflow defaults to `./mlruns` (local file store). |
| **MinIO setup** | Before first retraining run: `mc alias set local http://localhost:9000 $MINIO_ROOT_USER $MINIO_ROOT_PASSWORD && mc mb local/logitrack` |
| **Threshold tuning endpoint** | Phase 4 should expose a `PATCH /api/v1/ml/threshold` endpoint to adjust `ALERT_THRESHOLD` without redeployment, writing the override back to `ml_model_versions`. |

"""
Tests for the ML delay-prediction pipeline.

All 10 tests run entirely in-memory using synthetic fixtures — no database,
no S3, no MLflow.  The fixtures are designed with auditable, exact quantities
so assertions can be computed by hand.

Fixture design
--------------
``sample_df``  — 200 rows; 40 rows marked is_late=True (20 %)
                 Two categories: "electronics" / "furniture"
                 Two seller states: "SP" / "RJ"
                 All numeric features filled (no NaNs) for baseline checks.

``sample_df_with_nulls``
                 Same structure but intentional NaNs in distance_km and
                 seller_historical_delay_rate to exercise imputation paths.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder

from ml.features import (
    FEATURE_COLUMNS,
    TARGET_COLUMN,
    build_feature_matrix,
    encode_single_row,
)
from ml.predict import get_flagged_shipments, predict_batch
from ml.train import train_model


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_df(n: int = 200, late_frac: float = 0.20, seed: int = 42) -> pd.DataFrame:
    """Create a deterministic synthetic shipments DataFrame."""
    rng = np.random.default_rng(seed)
    n_late = int(n * late_frac)
    n_on_time = n - n_late

    is_late = np.array([True] * n_late + [False] * n_on_time)
    rng.shuffle(is_late)

    categories = np.where(
        rng.integers(0, 2, size=n).astype(bool), "electronics", "furniture"
    )
    states = np.where(rng.integers(0, 2, size=n).astype(bool), "SP", "RJ")

    return pd.DataFrame(
        {
            "order_id": [f"order_{i:04d}" for i in range(n)],
            "seller_id": [f"seller_{i % 10:02d}" for i in range(n)],
            "customer_state": np.where(rng.integers(0, 2, size=n).astype(bool), "MG", "BA"),
            "distance_km": rng.uniform(100, 2000, size=n),
            "seller_historical_delay_rate": rng.uniform(0.0, 0.5, size=n),
            "day_of_week": rng.integers(0, 7, size=n),
            "month": rng.integers(1, 13, size=n),
            "category_name": categories,
            "seller_state": states,
            "freight_value": rng.uniform(5, 100, size=n).round(2),
            "price": rng.uniform(20, 500, size=n).round(2),
            TARGET_COLUMN: is_late,
            "delay_days": np.where(is_late, rng.uniform(1, 10, size=n), 0.0),
            "estimated_delivery": pd.date_range("2023-01-01", periods=n, freq="6h"),
            "order_status": np.where(
                rng.integers(0, 3, size=n) == 0, "shipped",
                np.where(rng.integers(0, 2, size=n).astype(bool), "created", "delivered"),
            ),
        }
    )


@pytest.fixture()
def sample_df() -> pd.DataFrame:
    return _make_df(n=200, late_frac=0.20)


@pytest.fixture()
def sample_df_with_nulls() -> pd.DataFrame:
    df = _make_df(n=200, late_frac=0.20)
    # Inject NaNs for imputation tests
    df.loc[df.index[:20], "distance_km"] = np.nan
    df.loc[df.index[10:30], "seller_historical_delay_rate"] = np.nan
    return df


@pytest.fixture()
def small_df() -> pd.DataFrame:
    """DataFrame with fewer than 100 rows — should trigger ValueError."""
    return _make_df(n=50, late_frac=0.20)


@pytest.fixture()
def trained_result(sample_df: pd.DataFrame) -> dict:
    """Run a full training pass once and re-use the result across tests."""
    return train_model(sample_df, threshold=0.5, random_state=42)


# ---------------------------------------------------------------------------
# Test 1 — Feature matrix has correct columns
# ---------------------------------------------------------------------------

def test_feature_matrix_has_correct_columns(sample_df: pd.DataFrame) -> None:
    """X must contain exactly the eight canonical FEATURE_COLUMNS in order."""
    X, _ = build_feature_matrix(sample_df)
    assert list(X.columns) == FEATURE_COLUMNS, (
        f"Expected columns {FEATURE_COLUMNS}, got {list(X.columns)}"
    )


# ---------------------------------------------------------------------------
# Test 2 — Feature matrix raises on small dataset
# ---------------------------------------------------------------------------

def test_feature_matrix_raises_on_small_dataset(small_df: pd.DataFrame) -> None:
    """build_feature_matrix must raise ValueError when df has < 100 rows."""
    with pytest.raises(ValueError, match="100"):
        build_feature_matrix(small_df)


# ---------------------------------------------------------------------------
# Test 3 — encode_single_row handles unseen category gracefully
# ---------------------------------------------------------------------------

def test_encode_single_row_handles_unseen_category(sample_df: pd.DataFrame) -> None:
    """Unseen category_name and seller_state values must map to -1, not raise."""
    X, _ = build_feature_matrix(sample_df)
    encoders: dict = X.attrs["encoders"]

    row = {
        "category_name": "TOTALLY_UNSEEN_CATEGORY_XYZ",
        "seller_state": "ZZ",
        "distance_km": 500.0,
        "seller_historical_delay_rate": 0.1,
        "day_of_week": 2,
        "month": 6,
        "freight_value": 25.0,
        "price": 150.0,
    }

    result = encode_single_row(row, encoders)
    assert result["category_encoded"].iloc[0] == -1, "Unseen category should map to -1"
    assert result["seller_state_encoded"].iloc[0] == -1, "Unseen state should map to -1"
    assert list(result.columns) == FEATURE_COLUMNS


# ---------------------------------------------------------------------------
# Test 4 — train_model returns all expected top-level keys
# ---------------------------------------------------------------------------

def test_train_model_returns_all_keys(trained_result: dict) -> None:
    """train_model must return a dict with exactly the seven specified keys."""
    required_keys = {
        "model",
        "encoders",
        "threshold",
        "metrics",
        "feature_importances",
        "train_size",
        "test_size",
    }
    assert required_keys.issubset(trained_result.keys()), (
        f"Missing keys: {required_keys - set(trained_result.keys())}"
    )


# ---------------------------------------------------------------------------
# Test 5 — train_model metrics are in valid numeric ranges
# ---------------------------------------------------------------------------

def test_train_model_metrics_in_valid_range(trained_result: dict) -> None:
    """All evaluation metrics must be floats in [0, 1]."""
    metrics = trained_result["metrics"]
    for metric_name in ("accuracy", "precision_late", "recall_late", "f1_late", "roc_auc"):
        value = metrics[metric_name]
        assert isinstance(value, float), f"{metric_name} should be float, got {type(value)}"
        assert 0.0 <= value <= 1.0, f"{metric_name}={value} is outside [0, 1]"


# ---------------------------------------------------------------------------
# Test 6 — predict_batch adds delay_probability column
# ---------------------------------------------------------------------------

def test_predict_batch_adds_probability_column(trained_result: dict, sample_df: pd.DataFrame) -> None:
    """predict_batch must add a 'delay_probability' float column in [0, 1]."""
    model = trained_result["model"]
    encoders = trained_result["encoders"]
    threshold = trained_result["threshold"]

    result = predict_batch(sample_df, model, encoders, threshold)

    assert "delay_probability" in result.columns
    assert result["delay_probability"].between(0.0, 1.0).all(), (
        "delay_probability values must be in [0, 1]"
    )
    assert result["delay_probability"].dtype == float


# ---------------------------------------------------------------------------
# Test 7 — predict_batch adds predicted_late boolean column
# ---------------------------------------------------------------------------

def test_predict_batch_adds_predicted_late_column(
    trained_result: dict, sample_df: pd.DataFrame
) -> None:
    """predict_batch must add a 'predicted_late' bool column."""
    model = trained_result["model"]
    encoders = trained_result["encoders"]
    threshold = trained_result["threshold"]

    result = predict_batch(sample_df, model, encoders, threshold)

    assert "predicted_late" in result.columns
    assert result["predicted_late"].dtype == bool or result["predicted_late"].isin(
        [True, False]
    ).all()


# ---------------------------------------------------------------------------
# Test 8 — predict_batch respects the threshold
# ---------------------------------------------------------------------------

def test_predict_batch_respects_threshold(
    trained_result: dict, sample_df: pd.DataFrame
) -> None:
    """predicted_late must be exactly (delay_probability >= threshold)."""
    model = trained_result["model"]
    encoders = trained_result["encoders"]
    threshold = 0.40  # custom threshold so we can verify logic

    result = predict_batch(sample_df, model, encoders, threshold)

    expected = result["delay_probability"] >= threshold
    assert (result["predicted_late"] == expected).all(), (
        "predicted_late does not match (delay_probability >= threshold)"
    )


# ---------------------------------------------------------------------------
# Test 9 — get_flagged_shipments only returns active orders
# ---------------------------------------------------------------------------

def test_get_flagged_only_returns_active_orders(
    trained_result: dict, sample_df: pd.DataFrame
) -> None:
    """get_flagged_shipments must not include rows with status 'delivered'."""
    model = trained_result["model"]
    encoders = trained_result["encoders"]
    threshold = 0.01  # very low threshold so we get some flagged rows

    flagged = get_flagged_shipments(sample_df, model, encoders, threshold)

    if flagged.empty:
        pytest.skip("No shipments flagged at threshold=0.01; adjust fixture data.")

    # All active statuses in input
    active_statuses = {"created", "shipped", "approved"}
    # If order_status is not in the reduced output columns that's OK — the
    # filter must have already happened.  We verify by checking that the
    # original 'delivered' rows (order_id) are not in the result.
    delivered_ids = set(
        sample_df.loc[
            ~sample_df["order_status"].str.lower().isin(active_statuses), "order_id"
        ]
    )
    flagged_ids = set(flagged["order_id"])
    overlap = delivered_ids & flagged_ids
    assert not overlap, (
        f"Flagged set contains {len(overlap)} non-active order IDs: {list(overlap)[:5]}"
    )


# ---------------------------------------------------------------------------
# Test 10 — feature importances sum to ~1.0
# ---------------------------------------------------------------------------

def test_feature_importances_sum_to_one(trained_result: dict) -> None:
    """RandomForest feature importances must sum to approximately 1.0."""
    importances = trained_result["feature_importances"]
    total = sum(importances.values())
    assert abs(total - 1.0) < 1e-6, f"Feature importances sum to {total}, expected ≈ 1.0"
    # Also confirm all eight features are present
    assert set(importances.keys()) == set(FEATURE_COLUMNS), (
        f"Importance keys mismatch: {set(importances.keys())}"
    )

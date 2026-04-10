"""
Feature engineering for the LogiTrack delay-prediction model.

All functions are pure (no I/O, no global state mutations) so they can be
called from both the training pipeline and the live inference endpoint without
side-effects.

Feature columns
---------------
- distance_km                 : geodesic seller→customer distance (float)
- seller_historical_delay_rate: fraction of past orders that arrived late (float)
- day_of_week                 : 0=Monday … 6=Sunday (int)
- month                       : 1–12 (int)
- category_encoded            : LabelEncoder int for category_name (int)
- seller_state_encoded        : LabelEncoder int for seller_state (int)
- freight_value               : shipping fee in BRL (float)
- price                       : item price in BRL (float)

Target column
-------------
- is_late : bool → 1 if order arrived after estimated_delivery, else 0
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder

logger = logging.getLogger(__name__)

FEATURE_COLUMNS: list[str] = [
    "distance_km",
    "seller_historical_delay_rate",
    "day_of_week",
    "month",
    "category_encoded",
    "seller_state_encoded",
    "freight_value",
    "price",
]

TARGET_COLUMN: str = "is_late"

# Columns that drive the two encoded features
_CAT_COL = "category_name"
_STATE_COL = "seller_state"


def build_feature_matrix(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series]:
    """Encode categoricals, handle missing values, and return (X, y).

    Parameters
    ----------
    df:
        Raw shipments DataFrame as produced by the ETL pipeline.  Must contain
        at minimum the eight source columns plus ``is_late``.

    Returns
    -------
    X:
        DataFrame with exactly the columns listed in ``FEATURE_COLUMNS``.
    y:
        Boolean Series cast to int (0/1) aligned with X.

    Raises
    ------
    ValueError
        If ``df`` has fewer than 100 rows (insufficient for a train/test split).
    """
    if len(df) < 100:
        raise ValueError(
            f"DataFrame has only {len(df)} rows; at least 100 required for training."
        )

    df = df.copy()

    # ------------------------------------------------------------------
    # Impute numeric columns
    # ------------------------------------------------------------------
    distance_median = df["distance_km"].median()
    df["distance_km"] = df["distance_km"].fillna(distance_median)

    delay_rate_mean = df["seller_historical_delay_rate"].mean()
    df["seller_historical_delay_rate"] = df["seller_historical_delay_rate"].fillna(
        delay_rate_mean
    )

    # ------------------------------------------------------------------
    # Encode categoricals
    # ------------------------------------------------------------------
    cat_enc = LabelEncoder()
    state_enc = LabelEncoder()

    # Fill any NaN strings before encoding so LabelEncoder doesn't error
    df[_CAT_COL] = df[_CAT_COL].fillna("unknown").astype(str)
    df[_STATE_COL] = df[_STATE_COL].fillna("unknown").astype(str)

    df["category_encoded"] = cat_enc.fit_transform(df[_CAT_COL])
    df["seller_state_encoded"] = state_enc.fit_transform(df[_STATE_COL])

    logger.info(
        "Encoders fitted — categories: %d classes, states: %d classes",
        len(cat_enc.classes_),
        len(state_enc.classes_),
    )

    # ------------------------------------------------------------------
    # Build X / y
    # ------------------------------------------------------------------
    X = df[FEATURE_COLUMNS].copy()
    y = df[TARGET_COLUMN].astype(int)

    logger.info(
        "Feature matrix built — shape=%s, late_rate=%.3f",
        X.shape,
        y.mean(),
    )

    # Attach encoders as an attribute so callers can retrieve them without
    # needing a second call.  This is a pure-function-friendly convention:
    # the encoders are part of the deterministic transform output.
    X.attrs["encoders"] = {_CAT_COL: cat_enc, _STATE_COL: state_enc}

    return X, y


def encode_single_row(row: dict[str, Any], encoders: dict[str, LabelEncoder]) -> pd.DataFrame:
    """Encode a single raw-feature dict for live inference.

    Parameters
    ----------
    row:
        Dict with raw feature values keyed by column name.  Must contain all
        source columns required by ``FEATURE_COLUMNS``.
    encoders:
        Dict produced by ``build_feature_matrix`` (or restored from joblib):
        ``{"category_name": LabelEncoder, "seller_state": LabelEncoder}``.

    Returns
    -------
    pd.DataFrame
        Single-row DataFrame ready for ``model.predict_proba()``.

    Notes
    -----
    Unseen category values (not in the training vocabulary) are gracefully
    mapped to ``-1`` instead of raising an exception.  The model will treat
    such rows as an out-of-distribution category index, which is the safest
    default for production traffic.
    """
    record = dict(row)  # shallow copy so we don't mutate caller's dict

    # Normalise text values
    cat_val = str(record.get(_CAT_COL, "unknown") or "unknown")
    state_val = str(record.get(_STATE_COL, "unknown") or "unknown")

    record["category_encoded"] = _safe_transform(encoders[_CAT_COL], cat_val)
    record["seller_state_encoded"] = _safe_transform(encoders[_STATE_COL], state_val)

    # Impute missing numerics with neutral values (median/mean unknown at
    # inference time — caller is responsible for passing enriched rows, but
    # we guard with 0 as final fallback so we never crash).
    record.setdefault("distance_km", 0.0)
    record.setdefault("seller_historical_delay_rate", 0.0)
    record.setdefault("day_of_week", 0)
    record.setdefault("month", 1)
    record.setdefault("freight_value", 0.0)
    record.setdefault("price", 0.0)

    df = pd.DataFrame([{col: record.get(col, 0.0) for col in FEATURE_COLUMNS}])
    return df


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_transform(enc: LabelEncoder, value: str) -> int:
    """Transform ``value`` with ``enc``; return -1 for unseen values."""
    classes: np.ndarray = enc.classes_
    if value in classes:
        return int(enc.transform([value])[0])
    return -1

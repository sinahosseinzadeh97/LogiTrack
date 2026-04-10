"""
Batch and single-shipment delay prediction.

This module handles two inference modes:

1. **Batch inference** (``predict_batch``) — scores an arbitrary DataFrame of
   shipments and appends probability + binary prediction columns.

2. **Flagged shipments** (``get_flagged_shipments``) — filters to active
   (in-transit) orders, runs batch inference, and returns only the rows the
   model believes are at risk of a late delivery, sorted by risk descending.

Both functions are stateless — the caller resolves and supplies the active
model artefacts (see ``ml.registry.load_active_model``).
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from ml.features import encode_single_row

logger = logging.getLogger(__name__)

_ACTIVE_STATUSES = {"created", "shipped", "approved"}

_FLAGGED_COLUMNS = [
    "order_id",
    "seller_id",
    "category_name",
    "seller_state",
    "customer_state",
    "distance_km",
    "delay_probability",
    "estimated_delivery",
    "days_until_delivery",
]


def predict_batch(
    df: pd.DataFrame,
    model: Any,
    encoders: dict[str, Any],
    threshold: float,
) -> pd.DataFrame:
    """Run delay inference on a DataFrame of shipments.

    Parameters
    ----------
    df:
        Shipments DataFrame.  Must contain at least the raw source columns
        required by ``encode_single_row`` (``category_name``, ``seller_state``,
        ``distance_km``, ``seller_historical_delay_rate``, ``day_of_week``,
        ``month``, ``freight_value``, ``price``).
    model:
        Fitted ``RandomForestClassifier`` (or any sklearn-compatible estimator
        with a ``predict_proba`` method).
    encoders:
        Dict of fitted ``LabelEncoder`` instances keyed by column name.
    threshold:
        Probability cutoff.  Rows with ``delay_probability >= threshold`` are
        flagged as ``predicted_late = True``.

    Returns
    -------
    pd.DataFrame
        Original ``df`` with two additional columns:
        - ``delay_probability`` : float in [0, 1]
        - ``predicted_late``    : bool
    """
    if df.empty:
        result = df.copy()
        result["delay_probability"] = pd.Series(dtype=float)
        result["predicted_late"] = pd.Series(dtype=bool)
        return result

    logger.info("Running batch inference on %d rows", len(df))

    # Build feature matrix row-by-row then concat — ensures encoder handling
    # is identical to single-row live inference.
    rows_encoded = [encode_single_row(row, encoders) for row in df.to_dict(orient="records")]
    X = pd.concat(rows_encoded, ignore_index=True)

    probabilities = model.predict_proba(X)[:, 1]

    result = df.copy()
    result["delay_probability"] = probabilities
    result["predicted_late"] = result["delay_probability"] >= threshold

    flagged_count = int(result["predicted_late"].sum())
    logger.info(
        "Batch inference complete — flagged=%d / %d (threshold=%.2f)",
        flagged_count,
        len(df),
        threshold,
    )

    return result


def get_flagged_shipments(
    df_active: pd.DataFrame,
    model: Any,
    encoders: dict[str, Any],
    threshold: float,
) -> pd.DataFrame:
    """Return at-risk shipments for the active (in-transit) order queue.

    Parameters
    ----------
    df_active:
        DataFrame of **all current** shipments — including those already
        delivered.  The function filters internally to the statuses that
        indicate a shipment is still in transit:
        ``{"created", "shipped", "approved"}``.
    model:
        Fitted delay-prediction model.
    encoders:
        Fitted label encoders.
    threshold:
        Probability cutoff for flagging.

    Returns
    -------
    pd.DataFrame
        Subset of rows where ``predicted_late == True``, sorted by
        ``delay_probability`` descending.  Columns are a standardised subset
        defined by ``_FLAGGED_COLUMNS``; missing columns are filled with
        ``None`` to make the schema predictable for API serialisation.
    """
    if df_active.empty:
        return _empty_flagged_result()

    # Filter to active / in-transit orders
    if "order_status" in df_active.columns:
        mask = df_active["order_status"].str.lower().isin(_ACTIVE_STATUSES)
        df_in_transit = df_active[mask].copy()
    else:
        # If column is absent treat the entire input as in-transit
        logger.warning("'order_status' column not found; treating all rows as active.")
        df_in_transit = df_active.copy()

    if df_in_transit.empty:
        logger.info("No active (in-transit) shipments found.")
        return _empty_flagged_result()

    # Run inference
    scored = predict_batch(df_in_transit, model, encoders, threshold)

    # Keep only flagged rows
    flagged = scored[scored["predicted_late"]].copy()

    if flagged.empty:
        return _empty_flagged_result()

    # Compute days_until_delivery if not already present
    if "days_until_delivery" not in flagged.columns:
        if "estimated_delivery" in flagged.columns:
            now = pd.Timestamp.utcnow().tz_localize(None)
            est = pd.to_datetime(flagged["estimated_delivery"], errors="coerce")
            if est.dt.tz is not None:
                est = est.dt.tz_localize(None)
            flagged["days_until_delivery"] = (est - now).dt.days
        else:
            flagged["days_until_delivery"] = None

    # Sort descending by risk
    flagged = flagged.sort_values("delay_probability", ascending=False)

    # Normalise output columns — add any that are missing
    for col in _FLAGGED_COLUMNS:
        if col not in flagged.columns:
            flagged[col] = None

    return flagged[_FLAGGED_COLUMNS].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _empty_flagged_result() -> pd.DataFrame:
    """Return an empty DataFrame with the canonical flagged-shipment schema."""
    return pd.DataFrame(columns=_FLAGGED_COLUMNS)

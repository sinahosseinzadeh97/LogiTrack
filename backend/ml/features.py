"""Model inputs and the sklearn pipeline that consumes them.

Every input is known at purchase time (see etl/features.py for the
point-in-time ones). Preprocessing lives inside the pipeline, so the saved
model file is all that is needed to score a row.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OrdinalEncoder

CATEGORICAL = ["category", "seller_state", "customer_state"]
ORDER = [
    "promised_days",
    "distance_km",
    "price",
    "freight_value",
    "weight_g",
    "n_items",
    "purchase_dow",
]
SELLER_HISTORY = ["seller_prior_orders", "seller_prior_late_rate"]
NETWORK = ["network_late_rate_14d", "network_orders_7d", "promise_gap_7d"]
NUMERIC = ORDER + SELLER_HISTORY + NETWORK
FEATURES = CATEGORICAL + NUMERIC
DERIVED = ["same_state", "freight_share"]

# Candidate numeric feature sets; ml.train picks one with time-series CV.
FEATURE_SETS: dict[str, list[str]] = {
    "order": ORDER,
    "order+seller": ORDER + SELLER_HISTORY,
    "order+seller+network": ORDER + SELLER_HISTORY + NETWORK,
}


def _derive(df: pd.DataFrame) -> pd.DataFrame:
    total = df["price"].astype(float) + df["freight_value"].astype(float)
    return df.assign(
        same_state=(df["seller_state"] == df["customer_state"]).astype(float),
        freight_share=(df["freight_value"].astype(float) / total.where(total > 0)),
    )


def build_pipeline(numeric: list[str] = NUMERIC, random_state: int = 42) -> Pipeline:
    encode = ColumnTransformer(
        [
            (
                "categorical",
                # Unseen or missing categories become NaN, which the booster handles natively.
                OrdinalEncoder(
                    handle_unknown="use_encoded_value",
                    unknown_value=np.nan,
                    encoded_missing_value=np.nan,
                ),
                CATEGORICAL,
            ),
            ("numeric", "passthrough", numeric + DERIVED),
        ]
    )
    is_categorical = [True] * len(CATEGORICAL) + [False] * (len(numeric) + len(DERIVED))
    model = HistGradientBoostingClassifier(
        learning_rate=0.05,
        max_iter=400,
        max_leaf_nodes=31,
        min_samples_leaf=50,
        l2_regularization=1.0,
        categorical_features=is_categorical,
        random_state=random_state,
    )
    return Pipeline(
        [("derive", FunctionTransformer(_derive)), ("encode", encode), ("model", model)]
    )


def as_frame(rows: pd.DataFrame) -> pd.DataFrame:
    """All model inputs with stable dtypes (objects for categoricals, floats otherwise)."""
    out = rows[FEATURES].copy()
    for col in CATEGORICAL:
        out[col] = out[col].astype(object).where(out[col].notna(), np.nan)
    for col in NUMERIC:
        out[col] = pd.to_numeric(out[col], errors="coerce").astype(float)
    return out

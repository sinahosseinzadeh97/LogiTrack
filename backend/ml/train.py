"""
Model training module for LogiTrack delay prediction.

Trains a ``RandomForestClassifier`` with ``class_weight='balanced'`` to handle
the inherent class imbalance in the Olist dataset (≈ 8% late orders).

Usage
-----
    from ml.train import train_model
    result = train_model(df)
    model      = result["model"]
    encoders   = result["encoders"]
    threshold  = result["threshold"]
    metrics    = result["metrics"]
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

from ml.features import FEATURE_COLUMNS, TARGET_COLUMN, build_feature_matrix

logger = logging.getLogger(__name__)


def train_model(
    df: pd.DataFrame,
    threshold: float = 0.65,
    test_size: float = 0.2,
    random_state: int = 42,
) -> dict[str, Any]:
    """Train a RandomForestClassifier for shipment delay prediction.

    Parameters
    ----------
    df:
        Enriched shipments DataFrame (post-ETL).  Must have at least 100 rows.
    threshold:
        Probability cutoff for classifying a shipment as ``predicted_late``.
        Defaults to 0.65 — slightly conservative to reduce false negatives
        (we prefer catching more at-risk shipments than missing them).
    test_size:
        Fraction of data reserved for evaluation.  Defaults to 0.20.
    random_state:
        Seed for reproducibility across training runs.

    Returns
    -------
    dict with keys:
        - ``model``              : fitted RandomForestClassifier
        - ``encoders``           : dict[str, LabelEncoder] — category_name + seller_state
        - ``threshold``          : float — probability cutoff used
        - ``metrics``            : evaluation metrics on the held-out test set
        - ``feature_importances``: dict[str, float] summing to ≈ 1.0
        - ``train_size``         : int — number of training rows
        - ``test_size``          : int — number of test rows

    Raises
    ------
    ValueError
        Propagated from ``build_feature_matrix`` if df has < 100 rows.
    """
    logger.info("Starting model training — df.shape=%s, threshold=%.2f", df.shape, threshold)

    # ------------------------------------------------------------------
    # Feature engineering
    # ------------------------------------------------------------------
    X, y = build_feature_matrix(df)
    encoders: dict[str, LabelEncoder] = X.attrs.get("encoders", {})

    # ------------------------------------------------------------------
    # Stratified train / test split
    # ------------------------------------------------------------------
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=test_size,
        random_state=random_state,
        stratify=y,
    )
    logger.info("Split — train=%d rows, test=%d rows", len(X_train), len(X_test))

    # ------------------------------------------------------------------
    # Model — hyperparameters chosen for balanced recall/precision
    # - n_estimators=300  : sufficient for Olist-scale data (~96k rows)
    # - max_depth=12      : prevents overfitting on high-cardinality encodings
    # - min_samples_leaf=5: smooths leaf probabilities for calibrated thresholds
    # - class_weight='balanced': compensates for ≈ 8% positive rate
    # - n_jobs=-1          : parallel fit on all CPU cores
    # ------------------------------------------------------------------
    clf = RandomForestClassifier(
        n_estimators=300,
        max_depth=12,
        min_samples_leaf=5,
        max_features="sqrt",
        class_weight="balanced",
        random_state=random_state,
        n_jobs=-1,
    )
    clf.fit(X_train[FEATURE_COLUMNS], y_train)
    logger.info("Model fitted — n_estimators=%d", clf.n_estimators)

    # ------------------------------------------------------------------
    # Evaluation — use threshold for binary classification
    # ------------------------------------------------------------------
    y_proba = clf.predict_proba(X_test[FEATURE_COLUMNS])[:, 1]
    y_pred = (y_proba >= threshold).astype(int)

    accuracy = float(accuracy_score(y_test, y_pred))
    precision_late = float(precision_score(y_test, y_pred, zero_division=0))
    recall_late = float(recall_score(y_test, y_pred, zero_division=0))
    f1_late = float(f1_score(y_test, y_pred, zero_division=0))
    roc_auc = float(roc_auc_score(y_test, y_proba))
    cls_report = classification_report(y_test, y_pred, target_names=["on_time", "late"])

    logger.info(
        "Evaluation — accuracy=%.4f, precision=%.4f, recall=%.4f, "
        "f1=%.4f, roc_auc=%.4f",
        accuracy,
        precision_late,
        recall_late,
        f1_late,
        roc_auc,
    )

    # ------------------------------------------------------------------
    # Feature importances
    # ------------------------------------------------------------------
    importances: dict[str, float] = {
        col: float(imp)
        for col, imp in zip(FEATURE_COLUMNS, clf.feature_importances_, strict=True)
    }

    return {
        "model": clf,
        "encoders": encoders,
        "threshold": threshold,
        "metrics": {
            "accuracy": accuracy,
            "precision_late": precision_late,
            "recall_late": recall_late,
            "f1_late": f1_late,
            "roc_auc": roc_auc,
            "classification_report": cls_report,
        },
        "feature_importances": importances,
        "train_size": len(X_train),
        "test_size": len(X_test),
    }

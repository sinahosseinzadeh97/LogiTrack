"""Train, evaluate and deploy the late-delivery model: ``python -m ml.train``.

Evaluation is out-of-time. With cutoff T:
  * train = orders bought before T whose promised date is also before T, so every
    training label was already knowable at T (late orders aren't dropped just
    because they arrived after T);
  * test  = orders bought on/after T.
The feature set is chosen by rolling-origin CV and the decision threshold on
the last 15% of the training window (by time); the test set is scored once,
at the end. Afterwards every order is scored and the score is written to
``shipments.delay_probability`` for the dashboard.
"""

from __future__ import annotations

import argparse
import io
import logging
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score
from sklearn.pipeline import Pipeline
from sqlalchemy import Engine, create_engine, text

from app.config import get_settings
from ml import model_store
from ml.features import CATEGORICAL, FEATURE_SETS, FEATURES, as_frame, build_pipeline

logger = logging.getLogger("ml.train")

DEFAULT_CUTOFF = "2018-02-01"
VALIDATION_SHARE = 0.15
TOP_SHARE = 0.10  # "if ops can only check 10% of orders, how many of those are late?"
IMPORTANCE_SAMPLE = 8_000
CV_FOLD_MONTHS = [8, 6, 4, 2]  # fold cutoffs, in months before the final cutoff


def split(df: pd.DataFrame, cutoff: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame]:
    labelled = df[df["is_late"].notna()].sort_values(["purchase_ts", "order_id"], kind="stable")
    promised = pd.to_datetime(labelled["estimated_delivery"])
    train = labelled[(labelled["purchase_ts"] < cutoff) & (promised < cutoff)]
    test = labelled[labelled["purchase_ts"] >= cutoff]
    return train, test


def select_feature_set(
    train_df: pd.DataFrame, cutoff: pd.Timestamp
) -> tuple[str, dict[str, float]]:
    """Rolling-origin CV inside the training window; the test set is never touched.

    Each fold reuses ``split`` with an earlier cutoff, so it follows the same
    "labels knowable at the cutoff" rule as the final evaluation.
    """
    fold_cutoffs = [cutoff - pd.DateOffset(months=m) for m in CV_FOLD_MONTHS]
    x_all = as_frame(train_df)
    mean_pr_auc = {}
    for name, numeric in FEATURE_SETS.items():
        fold_scores = []
        for start, end in zip(fold_cutoffs, [*fold_cutoffs[1:], cutoff], strict=True):
            fit, _ = split(train_df, start)
            hold = train_df[(train_df["purchase_ts"] >= start) & (train_df["purchase_ts"] < end)]
            pipe = build_pipeline(numeric).fit(x_all.loc[fit.index], fit["is_late"].astype(bool))
            p = pipe.predict_proba(x_all.loc[hold.index])[:, 1]
            fold_scores.append(average_precision_score(hold["is_late"].astype(bool), p))
        mean_pr_auc[name] = float(np.mean(fold_scores))
        logger.info("CV %-22s PR-AUC per fold %s", name, np.round(fold_scores, 3))
    return max(mean_pr_auc, key=mean_pr_auc.__getitem__), mean_pr_auc


def pick_threshold(y: pd.Series, p: np.ndarray) -> float:
    """Threshold that maximises F1 for the late class."""
    precision, recall, thresholds = precision_recall_curve(y, p)
    f1 = 2 * precision * recall / np.maximum(precision + recall, 1e-12)
    return float(thresholds[np.argmax(f1[:-1])])


def scores_at(y: pd.Series, p: np.ndarray, threshold: float) -> dict[str, float]:
    flagged = p >= threshold
    tp = int((flagged & y.to_numpy()).sum())
    top = p >= np.quantile(p, 1 - TOP_SHARE)
    precision = tp / max(flagged.sum(), 1)
    recall = tp / max(int(y.sum()), 1)
    return {
        "roc_auc": roc_auc_score(y, p),
        "pr_auc": average_precision_score(y, p),
        "base_rate": float(y.mean()),
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / max(precision + recall, 1e-12),
        "alert_rate": float(flagged.mean()),
        "precision_top_10pct": float(y.to_numpy()[top].mean()),
    }


def baseline_scores(test: pd.DataFrame, y: pd.Series) -> dict[str, dict[str, float]]:
    """Single-feature rules a reviewer would ask about first."""
    out = {}
    for name, col in [
        ("seller_history", "seller_prior_late_rate"),
        ("network_14d", "network_late_rate_14d"),
    ]:
        p = test[col].fillna(test[col].median()).to_numpy()
        out[name] = {"roc_auc": roc_auc_score(y, p), "pr_auc": average_precision_score(y, p)}
    return out


def monthly(test: pd.DataFrame, y: pd.Series, p: np.ndarray) -> list[dict[str, Any]]:
    frame = pd.DataFrame(
        {"month": test["purchase_ts"].dt.strftime("%Y-%m").to_numpy(), "y": y.to_numpy(), "p": p}
    )
    rows = []
    for month, g in frame.groupby("month"):
        both_classes = g["y"].nunique() == 2
        rows.append(
            {
                "month": month,
                "orders": len(g),
                "late_rate": float(g["y"].mean()),
                "roc_auc": roc_auc_score(g["y"], g["p"]) if both_classes else None,
                "pr_auc": average_precision_score(g["y"], g["p"]) if both_classes else None,
            }
        )
    return rows


def importance(
    pipe: Pipeline, x: pd.DataFrame, y: pd.Series, used: list[str]
) -> list[dict[str, Any]]:
    """Permutation importance on the test set: drop in PR-AUC when a column is shuffled."""
    sample = x.sample(min(IMPORTANCE_SAMPLE, len(x)), random_state=42)
    result = permutation_importance(
        pipe, sample, y.loc[sample.index], scoring="average_precision", n_repeats=5, random_state=42
    )
    ranked = sorted(zip(FEATURES, result.importances_mean, strict=True), key=lambda kv: -kv[1])
    return [{"feature": f, "importance": float(v)} for f, v in ranked if f in used]


def defaults(test: pd.DataFrame, numeric: list[str]) -> dict[str, Any]:
    """Typical values used to pre-fill the what-if form."""
    values: dict[str, Any] = {c: round(float(test[c].median()), 3) for c in numeric}
    values.update({c: test[c].mode().iat[0] for c in CATEGORICAL})
    return values


def _summary(frame: pd.DataFrame) -> dict[str, Any]:
    return {
        "rows": len(frame),
        "from": frame["purchase_ts"].min().date().isoformat(),
        "to": frame["purchase_ts"].max().date().isoformat(),
        "late_rate": float(frame["is_late"].astype(bool).mean()),
    }


def train(df: pd.DataFrame, cutoff: pd.Timestamp) -> tuple[Pipeline, dict[str, Any]]:
    train_df, test_df = split(df, cutoff)
    if len(train_df) < 1_000 or len(test_df) < 500:
        raise ValueError(
            f"Not enough data around cutoff {cutoff.date()}: "
            f"train={len(train_df)}, test={len(test_df)}"
        )
    y_train = train_df["is_late"].astype(bool)
    y_test = test_df["is_late"].astype(bool)
    feature_set, cv_scores = select_feature_set(train_df, cutoff)
    numeric = FEATURE_SETS[feature_set]

    n_fit = int(len(train_df) * (1 - VALIDATION_SHARE))
    x_train = as_frame(train_df)
    probe = build_pipeline(numeric).fit(x_train.iloc[:n_fit], y_train.iloc[:n_fit])
    threshold = pick_threshold(
        y_train.iloc[n_fit:], probe.predict_proba(x_train.iloc[n_fit:])[:, 1]
    )

    pipe = build_pipeline(numeric).fit(x_train, y_train)
    used = CATEGORICAL + numeric
    x_test = as_frame(test_df)
    p_test = pipe.predict_proba(x_test)[:, 1]

    card = {
        "version": datetime.now(UTC).strftime("%Y%m%d-%H%M%S"),
        "trained_at": datetime.now(UTC).isoformat(),
        "algorithm": "HistGradientBoostingClassifier",
        "cutoff": cutoff.date().isoformat(),
        "train": _summary(train_df),
        "test": _summary(test_df),
        "feature_set": feature_set,
        "cv_pr_auc": cv_scores,
        "threshold": threshold,
        "metrics": scores_at(y_test, p_test, threshold),
        "baselines": baseline_scores(test_df, y_test),
        "monthly": monthly(test_df, y_test, p_test),
        "feature_importance": importance(pipe, x_test, y_test, used),
        "features": used,
        "defaults": defaults(test_df, numeric),
    }
    return pipe, card


def write_scores(engine: Engine, df: pd.DataFrame, pipe: Pipeline) -> None:
    """Score every order that has items and store P(late) in shipments.delay_probability."""
    df = df[df["n_items"] > 0]  # orders with no items (never fulfilled) have nothing to score
    scores = pd.DataFrame({"order_id": df["order_id"], "p": pipe.predict_proba(as_frame(df))[:, 1]})
    buffer = io.StringIO()
    scores.to_csv(buffer, index=False, header=False)
    buffer.seek(0)
    with engine.begin() as conn:
        conn.execute(
            text("CREATE TEMP TABLE scores (order_id varchar(32), p float8) ON COMMIT DROP")
        )
        conn.connection.dbapi_connection.cursor().copy_expert(
            "COPY scores FROM STDIN WITH (FORMAT csv)", buffer
        )
        conn.execute(
            text(
                "UPDATE shipments s SET delay_probability = scores.p"
                " FROM scores WHERE s.order_id = scores.order_id"
            )
        )
    logger.info("scored %d orders", len(scores))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--cutoff", default=DEFAULT_CUTOFF, help="train/test split date (YYYY-MM-DD)"
    )
    parser.add_argument("--if-missing", action="store_true", help="skip if a model already exists")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

    settings = get_settings()
    engine = create_engine(settings.sync_database_url)
    # Fixed row order keeps training reproducible: the early-stopping split is positional.
    query = "SELECT * FROM shipments ORDER BY order_id"
    df = pd.read_sql(query, engine, parse_dates=["purchase_ts", "delivered_ts"])

    if args.if_missing and model_store.exists(settings.MODEL_DIR):
        if df["delay_probability"].isna().all():
            logger.info("reusing the saved model to score freshly loaded orders")
            write_scores(engine, df, model_store.load(settings.MODEL_DIR)[0])
        else:
            logger.info("model already exists in %s; skipping training", settings.MODEL_DIR)
        return

    pipe, card = train(df, pd.Timestamp(args.cutoff))
    model_store.save(settings.MODEL_DIR, pipe, card)
    write_scores(engine, df, pipe)
    m = card["metrics"]
    logger.info(
        "test ROC-AUC %.3f | PR-AUC %.3f (base rate %.3f) | precision %.2f recall %.2f at %.2f",
        m["roc_auc"],
        m["pr_auc"],
        m["base_rate"],
        m["precision"],
        m["recall"],
        card["threshold"],
    )


if __name__ == "__main__":
    main()

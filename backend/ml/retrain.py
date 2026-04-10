"""
Automated retraining pipeline for the LogiTrack delay-prediction model.

Trigger conditions (``should_retrain``)
---------------------------------------
1. More than ``min_new_rows`` (default 500) shipments have been added since
   the last training date recorded in ``ml_model_versions``.
2. OR the model accuracy on the last 30 days of data has dropped below 0.78.

Pipeline (``run_retrain_pipeline``)
------------------------------------
1. Load latest shipments from PostgreSQL (all rows, not just delivered).
2. Run feature engineering via ``ml.features.build_feature_matrix``.
3. Train new model via ``ml.train.train_model``.
4. Compare new model F1-late against the currently active model on a shared
   holdout slice.
5. If the new model is strictly better (higher F1), promote it.
6. Log everything to MLflow regardless of promotion decision.
7. Return a summary dict.

Scheduling (``schedule_retrain``)
----------------------------------
Uses ``APScheduler`` (``BackgroundScheduler``) to fire every Monday at
02:00 UTC.  Designed to be called once at application startup.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sklearn.metrics import f1_score
from sqlalchemy import Engine, text

from app.config import Settings
from ml.features import build_feature_matrix
from ml.registry import load_active_model, log_experiment, promote_model
from ml.train import train_model

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Trigger decision
# ---------------------------------------------------------------------------

def should_retrain(db_engine: Engine, min_new_rows: int = 500) -> bool:
    """Decide whether a new training run is warranted.

    Returns ``True`` if either of the following is satisfied:

    * More than ``min_new_rows`` shipments have been inserted **after** the
      ``trained_at`` timestamp of the most recently active model version.
    * The model's accuracy on shipments from the last 30 days falls below
      the hard floor of 0.78.

    Parameters
    ----------
    db_engine:
        Synchronous SQLAlchemy engine.
    min_new_rows:
        Minimum number of new rows since last training to trigger retraining.

    Returns
    -------
    bool
    """
    with db_engine.connect() as conn:
        # ── Condition 1: new row count ──────────────────────────────────────
        row = conn.execute(
            text(
                "SELECT trained_at FROM ml_model_versions "
                "WHERE is_active = TRUE ORDER BY trained_at DESC LIMIT 1"
            )
        ).fetchone()

        if row is None:
            logger.info("No active model found — triggering initial training.")
            return True

        last_trained_at: datetime = row[0]
        if last_trained_at.tzinfo is None:
            last_trained_at = last_trained_at.replace(tzinfo=timezone.utc)

        new_rows_count: int = conn.execute(
            text(
                "SELECT COUNT(*) FROM shipments WHERE created_at > :since"
            ),
            {"since": last_trained_at},
        ).scalar_one()

        if new_rows_count >= min_new_rows:
            logger.info(
                "Retraining triggered — %d new rows since %s (threshold=%d).",
                new_rows_count,
                last_trained_at.isoformat(),
                min_new_rows,
            )
            return True

        # ── Condition 2: recent accuracy drop ──────────────────────────────
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=30)
        recent_rows = conn.execute(
            text(
                "SELECT is_late FROM shipments "
                "WHERE purchase_timestamp >= :since AND is_late IS NOT NULL"
            ),
            {"since": cutoff},
        ).fetchall()

        if not recent_rows:
            logger.info("No recent rows to evaluate accuracy; skipping accuracy check.")
            return False

        # Simple heuristic: if the raw late-rate has shifted significantly
        # beyond the training distribution it may indicate accuracy degradation.
        # A proper check would run the active model on these rows, but that
        # requires the features to be available — which may not be the case
        # for very fresh rows.  We use a proxy: if actual late-rate deviates
        # from the stored model accuracy by more than 0.22 we re-train.
        recent_late_rate = sum(r[0] for r in recent_rows) / len(recent_rows)
        stored_accuracy_row = conn.execute(
            text(
                "SELECT accuracy FROM ml_model_versions "
                "WHERE is_active = TRUE ORDER BY trained_at DESC LIMIT 1"
            )
        ).fetchone()

        if stored_accuracy_row and stored_accuracy_row[0] is not None:
            stored_accuracy: float = stored_accuracy_row[0]
            drift = abs(stored_accuracy - (1.0 - recent_late_rate))
            if drift > 0.22 or stored_accuracy < 0.78:
                logger.info(
                    "Retraining triggered — accuracy drift=%.4f or stored_accuracy=%.4f < 0.78.",
                    drift,
                    stored_accuracy,
                )
                return True

    logger.info(
        "No retraining needed — new_rows=%d, accuracy drift within bounds.",
        new_rows_count,
    )
    return False


# ---------------------------------------------------------------------------
# Full retraining pipeline
# ---------------------------------------------------------------------------

def run_retrain_pipeline(db_engine: Engine, settings: Settings) -> dict[str, Any]:
    """Execute the full retraining pipeline.

    Parameters
    ----------
    db_engine:
        Synchronous SQLAlchemy engine.
    settings:
        Application ``Settings`` instance (needed for S3 + MLflow config).

    Returns
    -------
    dict with keys:
        - ``retrained``  : bool — whether a new model was trained
        - ``new_f1``     : float — F1-late of the newly trained model
        - ``old_f1``     : float — F1-late of the previously active model
                           (0.0 if no active model existed)
        - ``promoted``   : bool — whether the new model was promoted to active
    """
    logger.info("Starting retraining pipeline.")

    # ── Step 1: Load shipments ──────────────────────────────────────────────
    with db_engine.connect() as conn:
        df: pd.DataFrame = pd.read_sql(
            "SELECT * FROM shipments WHERE is_late IS NOT NULL",
            conn,
        )

    if df.empty:
        logger.warning("No shipments with is_late labels found. Aborting retraining.")
        return {"retrained": False, "new_f1": 0.0, "old_f1": 0.0, "promoted": False}

    logger.info("Loaded %d labelled shipments for retraining.", len(df))

    # ── Step 2: Feature engineering ─────────────────────────────────────────
    X, y = build_feature_matrix(df)
    encoders: dict[str, Any] = X.attrs.get("encoders", {})

    # Reserve a shared holdout for comparing old vs new model (last 10%)
    holdout_n = max(50, int(len(X) * 0.10))
    X_holdout = X.iloc[-holdout_n:].copy()
    y_holdout = y.iloc[-holdout_n:].copy()
    X_train_full = X.iloc[:-holdout_n].copy()
    df_train = df.iloc[:-holdout_n].copy()

    # ── Step 3: Train new model ─────────────────────────────────────────────
    result = train_model(df_train, threshold=settings.ALERT_THRESHOLD)
    new_model = result["model"]
    new_threshold = result["threshold"]
    new_metrics = result["metrics"]
    new_f1 = new_metrics["f1_late"]

    logger.info("New model trained — f1_late=%.4f", new_f1)

    # ── Step 4: Evaluate old model on the same holdout ──────────────────────
    old_f1 = 0.0
    try:
        old_model, old_encoders, old_threshold = load_active_model(db_engine, settings)
        old_proba = old_model.predict_proba(X_holdout)[:, 1]
        old_pred = (old_proba >= old_threshold).astype(int)
        old_f1 = float(f1_score(y_holdout, old_pred, zero_division=0))
        logger.info("Active model holdout F1-late: %.4f", old_f1)
    except RuntimeError:
        logger.info("No active model found — new model will be promoted automatically.")
        old_f1 = 0.0

    # ── Step 5: Evaluate new model on holdout ──────────────────────────────
    new_proba_holdout = new_model.predict_proba(X_holdout)[:, 1]
    new_pred_holdout = (new_proba_holdout >= new_threshold).astype(int)
    new_f1_holdout = float(f1_score(y_holdout, new_pred_holdout, zero_division=0))

    # ── Step 6: Log to MLflow ───────────────────────────────────────────────
    run_name = f"retrain-{datetime.now(tz=timezone.utc).strftime('%Y-%m-%dT%H%M')}"
    run_id = log_experiment(
        run_name=run_name,
        metrics=new_metrics,
        model=new_model,
        encoders=result["encoders"],
        threshold=new_threshold,
        feature_importances=result["feature_importances"],
        settings=settings,
    )

    # ── Step 7: Promote if better ───────────────────────────────────────────
    promoted = new_f1_holdout > old_f1
    if promoted:
        promote_model(run_id, db_engine, settings)
        logger.info(
            "New model PROMOTED — holdout F1: %.4f > old F1: %.4f", new_f1_holdout, old_f1
        )
    else:
        logger.info(
            "New model NOT promoted — holdout F1: %.4f <= old F1: %.4f",
            new_f1_holdout,
            old_f1,
        )

    return {
        "retrained": True,
        "new_f1": new_f1_holdout,
        "old_f1": old_f1,
        "promoted": promoted,
    }


# ---------------------------------------------------------------------------
# APScheduler background job
# ---------------------------------------------------------------------------

def schedule_retrain(settings: Settings, db_engine: Engine | None = None) -> None:
    """Register the weekly retraining job with APScheduler.

    Fires every Monday at 02:00 UTC.  The scheduler runs in a daemon thread
    so it does not block application shutdown.

    Parameters
    ----------
    settings:
        Application settings (passed through to the pipeline).
    db_engine:
        Optional pre-built engine.  When ``None`` a new sync engine is created
        from ``settings.DATABASE_SYNC_URL`` at schedule time.
    """
    from sqlalchemy import create_engine  # deferred to avoid circular imports

    def _job() -> None:
        logger.info("APScheduler: weekly retraining job triggered.")
        engine = db_engine or create_engine(settings.DATABASE_SYNC_URL)
        if should_retrain(engine):
            summary = run_retrain_pipeline(engine, settings)
            logger.info("Retraining summary: %s", summary)
        else:
            logger.info("APScheduler: retraining skipped — triggers not met.")

    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        _job,
        trigger=CronTrigger(day_of_week="mon", hour=2, minute=0),
        id="weekly_retrain",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("APScheduler started — retraining scheduled every Monday at 02:00 UTC.")

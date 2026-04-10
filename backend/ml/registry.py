"""
Model registry — versioning, S3/MinIO storage, and MLflow experiment tracking.

Responsibilities
----------------
1. Log every experiment to MLflow (params, metrics, artifact path).
2. Persist model + encoders as a single joblib bundle in S3/MinIO.
3. Promote the best model version by updating ``ml_model_versions`` in PostgreSQL.
4. Load the active model for live inference.

S3 layout
---------
    s3://<bucket>/models/<run_id>/model_bundle.joblib   ← model + encoders + threshold
    s3://<bucket>/models/active/model_bundle.joblib     ← always points to active version

MLflow experiment
-----------------
    Experiment name : "logitrack-delay-prediction"
    Run name        : supplied by caller (e.g. "retrain-2024-w15")
    Logged params   : threshold, n_estimators, max_depth, train_size, test_size
    Logged metrics  : accuracy, precision_late, recall_late, f1_late, roc_auc
    Logged artifacts: model_bundle.joblib, feature_importances.json
"""

from __future__ import annotations

import io
import json
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
import joblib
import mlflow
import mlflow.sklearn
import pandas as pd
from botocore.exceptions import BotoCoreError, ClientError
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sqlalchemy import Engine, text

logger = logging.getLogger(__name__)

_EXPERIMENT_NAME = "logitrack-delay-prediction"
_ACTIVE_KEY = "models/active/model_bundle.joblib"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_s3_client(settings: Any) -> Any:
    """Return a boto3 S3 client pointed at MinIO / S3."""
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
    )


def _ensure_bucket(s3: Any, bucket: str) -> None:
    """Create the bucket if it does not already exist."""
    try:
        s3.head_bucket(Bucket=bucket)
    except ClientError:
        try:
            s3.create_bucket(Bucket=bucket)
            logger.info("Created S3 bucket: %s", bucket)
        except (ClientError, BotoCoreError) as exc:
            logger.warning("Could not create bucket %s: %s", bucket, exc)


def _bundle_key(run_id: str) -> str:
    return f"models/{run_id}/model_bundle.joblib"


def _upload_bundle(
    s3: Any,
    bucket: str,
    key: str,
    bundle: dict[str, Any],
) -> None:
    """Serialise bundle to joblib in-memory and upload to S3."""
    buf = io.BytesIO()
    joblib.dump(bundle, buf)
    buf.seek(0)
    s3.put_object(Bucket=bucket, Key=key, Body=buf.getvalue())
    logger.info("Uploaded bundle to s3://%s/%s", bucket, key)


def _download_bundle(s3: Any, bucket: str, key: str) -> dict[str, Any]:
    """Download and deserialise a joblib bundle from S3."""
    response = s3.get_object(Bucket=bucket, Key=key)
    buf = io.BytesIO(response["Body"].read())
    return joblib.load(buf)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def log_experiment(
    run_name: str,
    metrics: dict[str, Any],
    model: RandomForestClassifier,
    encoders: dict[str, LabelEncoder],
    threshold: float,
    feature_importances: dict[str, float],
    settings: Any | None = None,
) -> str:
    """Log a training experiment to MLflow and persist the model bundle to S3.

    Parameters
    ----------
    run_name:
        Human-readable name for this MLflow run (e.g. ``"retrain-2024-w15"``).
    metrics:
        Dict returned by ``train_model()["metrics"]``.
    model:
        Fitted ``RandomForestClassifier``.
    encoders:
        Dict of fitted ``LabelEncoder`` instances keyed by column name.
    threshold:
        Probability classification threshold used during training.
    feature_importances:
        Dict mapping feature name → importance score.
    settings:
        Application ``Settings`` instance.  Used to compose the S3 artifact
        path.  If ``None``, the artifact path is set to a local temp file as
        a fallback (useful in tests / offline mode).

    Returns
    -------
    str
        MLflow ``run_id`` for the logged run.
    """
    mlflow.set_experiment(_EXPERIMENT_NAME)

    with mlflow.start_run(run_name=run_name) as run:
        run_id: str = run.info.run_id

        # ---- Params -------------------------------------------------------
        mlflow.log_params(
            {
                "threshold": threshold,
                "n_estimators": model.n_estimators,
                "max_depth": model.max_depth,
                "min_samples_leaf": model.min_samples_leaf,
                "max_features": model.max_features,
                "class_weight": str(model.class_weight),
                "random_state": model.random_state,
            }
        )

        # ---- Metrics -------------------------------------------------------
        loggable_metrics = {
            k: v for k, v in metrics.items() if isinstance(v, (int, float))
        }
        mlflow.log_metrics(loggable_metrics)

        # ---- Feature importances as artifact ------------------------------
        with tempfile.TemporaryDirectory() as tmp_dir:
            fi_path = Path(tmp_dir) / "feature_importances.json"
            fi_path.write_text(json.dumps(feature_importances, indent=2))
            mlflow.log_artifact(str(fi_path), artifact_path="reports")

        # ---- Persist bundle to S3 (or local fallback) --------------------
        bundle: dict[str, Any] = {
            "model": model,
            "encoders": encoders,
            "threshold": threshold,
            "run_id": run_id,
            "logged_at": datetime.now(tz=timezone.utc).isoformat(),
        }

        if settings is not None:
            try:
                s3 = _get_s3_client(settings)
                _ensure_bucket(s3, settings.S3_BUCKET_NAME)
                key = _bundle_key(run_id)
                _upload_bundle(s3, settings.S3_BUCKET_NAME, key, bundle)
                artifact_uri = f"s3://{settings.S3_BUCKET_NAME}/{key}"
            except Exception as exc:  # noqa: BLE001
                logger.warning("S3 upload failed (%s); falling back to local storage.", exc)
                artifact_uri = _local_fallback_save(bundle, run_id)
        else:
            artifact_uri = _local_fallback_save(bundle, run_id)

        mlflow.log_param("artifact_uri", artifact_uri)
        logger.info(
            "Experiment logged — run_id=%s, f1_late=%.4f, artifact=%s",
            run_id,
            metrics.get("f1_late", float("nan")),
            artifact_uri,
        )

    return run_id


def promote_model(run_id: str, db_engine: Engine, settings: Any | None = None) -> None:
    """Set the model for ``run_id`` as the active version in the database.

    Steps
    -----
    1. Deactivate all existing model versions (``is_active = FALSE``).
    2. Look up the MLflow run to retrieve stored metrics and artifact path.
    3. Insert or update the new active version in ``ml_model_versions``.
    4. Copy the model bundle to the ``active/`` slot in S3 (fast pointer swap).

    Parameters
    ----------
    run_id:
        MLflow run ID returned by ``log_experiment``.
    db_engine:
        Synchronous SQLAlchemy engine.
    settings:
        Application ``Settings`` instance; required for S3 operations.
    """
    # ---- Fetch MLflow run ------------------------------------------------
    client = mlflow.tracking.MlflowClient()
    run = client.get_run(run_id)
    params = run.data.params
    metrics = run.data.metrics
    artifact_uri = params.get("artifact_uri", "")

    with db_engine.begin() as conn:
        # Deactivate all previous versions
        conn.execute(text("UPDATE ml_model_versions SET is_active = FALSE"))

        # Insert new active version
        conn.execute(
            text(
                """
                INSERT INTO ml_model_versions
                    (version, accuracy, precision_late, recall_late, f1_late,
                     threshold, is_active, storage_path, notes)
                VALUES
                    (:version, :accuracy, :precision_late, :recall_late, :f1_late,
                     :threshold, TRUE, :storage_path, :notes)
                """
            ),
            {
                "version": run_id,
                "accuracy": metrics.get("accuracy"),
                "precision_late": metrics.get("precision_late"),
                "recall_late": metrics.get("recall_late"),
                "f1_late": metrics.get("f1_late"),
                "threshold": float(params.get("threshold", 0.65)),
                "storage_path": artifact_uri,
                "notes": f"Promoted from MLflow run {run_id}",
            },
        )

    logger.info("Promoted run_id=%s as active model in DB", run_id)

    # ---- Copy bundle to active slot in S3 --------------------------------
    if settings is not None and artifact_uri.startswith("s3://"):
        try:
            s3 = _get_s3_client(settings)
            src_key = _bundle_key(run_id)
            s3.copy_object(
                Bucket=settings.S3_BUCKET_NAME,
                CopySource={"Bucket": settings.S3_BUCKET_NAME, "Key": src_key},
                Key=_ACTIVE_KEY,
            )
            logger.info("Copied active bundle to s3://%s/%s", settings.S3_BUCKET_NAME, _ACTIVE_KEY)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not copy bundle to active slot: %s", exc)


def load_active_model(
    db_engine: Engine,
    settings: Any | None = None,
) -> tuple[Any, dict[str, LabelEncoder], float]:
    """Load the active model bundle from S3 (or local fallback).

    Parameters
    ----------
    db_engine:
        Synchronous SQLAlchemy engine.
    settings:
        Application ``Settings`` instance; required for S3 operations.

    Returns
    -------
    (model, encoders, threshold)

    Raises
    ------
    RuntimeError
        If no active model version exists in the database.
    """
    with db_engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT storage_path, threshold FROM ml_model_versions "
                "WHERE is_active = TRUE ORDER BY trained_at DESC LIMIT 1"
            )
        ).fetchone()

    if row is None:
        raise RuntimeError(
            "No active model found in ml_model_versions. "
            "Run the training pipeline first."
        )

    storage_path: str = row[0]
    threshold: float = float(row[1])

    # Try S3 first, then fall back to local path
    bundle: dict[str, Any]

    if settings is not None and storage_path.startswith("s3://"):
        try:
            s3 = _get_s3_client(settings)
            bundle = _download_bundle(s3, settings.S3_BUCKET_NAME, _ACTIVE_KEY)
            logger.info("Loaded active model from S3 active slot")
        except Exception as exc:  # noqa: BLE001
            logger.warning("S3 load failed (%s); trying local path.", exc)
            bundle = joblib.load(storage_path)
    else:
        bundle = joblib.load(storage_path)
        logger.info("Loaded active model from local path: %s", storage_path)

    return bundle["model"], bundle["encoders"], threshold


# ---------------------------------------------------------------------------
# Local fallback helpers (offline / test environments)
# ---------------------------------------------------------------------------

def _local_fallback_save(bundle: dict[str, Any], run_id: str) -> str:
    """Persist bundle to a local temp directory and return the path."""
    save_dir = Path(tempfile.gettempdir()) / "logitrack_models" / run_id
    save_dir.mkdir(parents=True, exist_ok=True)
    path = save_dir / "model_bundle.joblib"
    joblib.dump(bundle, path)
    logger.info("Saved bundle locally at %s", path)
    return str(path)

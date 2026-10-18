"""Save/load the trained pipeline and its model card (a JSON summary of how it did)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
from sklearn.pipeline import Pipeline

MODEL_FILE = "model.joblib"
CARD_FILE = "model_card.json"


def save(model_dir: Path, pipeline: Pipeline, card: dict[str, Any]) -> None:
    model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, model_dir / MODEL_FILE)
    (model_dir / CARD_FILE).write_text(json.dumps(card, indent=2, default=str))


def exists(model_dir: Path) -> bool:
    return (model_dir / MODEL_FILE).exists() and (model_dir / CARD_FILE).exists()


def load(model_dir: Path) -> tuple[Pipeline, dict[str, Any]]:
    # Only ever load model files this project wrote: joblib unpickles arbitrary code.
    pipeline = joblib.load(model_dir / MODEL_FILE)
    card = json.loads((model_dir / CARD_FILE).read_text())
    return pipeline, card

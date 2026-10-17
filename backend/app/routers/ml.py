"""Model card, what-if prediction, and the in-memory model dependency."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sklearn.pipeline import Pipeline

from app.auth.service import AnalystUser, ViewerUser
from app.schemas import PredictRequest, PredictResponse
from ml.features import FEATURES, as_frame

router = APIRouter(prefix="/api/v1/ml", tags=["ml"])


@dataclass(frozen=True)
class LoadedModel:
    pipeline: Pipeline
    card: dict[str, Any]

    @property
    def threshold(self) -> float:
        return float(self.card["threshold"])


def get_model(request: Request) -> LoadedModel:
    model = getattr(request.app.state, "model", None)
    if model is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "No trained model yet. Run `python -m ml.train`."
        )
    return model


Model = Annotated[LoadedModel, Depends(get_model)]


@router.get("/model")
async def model_card(_: ViewerUser, model: Model) -> dict[str, Any]:
    """How the model was trained and how it scored on the held-out period."""
    return model.card


@router.post("/predict", response_model=PredictResponse)
async def predict(body: PredictRequest, _: AnalystUser, model: Model) -> dict[str, Any]:
    """Score a hypothetical order. Omitted inputs use typical values from the test period."""
    defaults = model.card["defaults"]
    given = body.model_dump(exclude_none=True)
    inputs = {f: given.get(f, defaults.get(f)) for f in FEATURES}
    p = float(model.pipeline.predict_proba(as_frame(pd.DataFrame([inputs])))[0, 1])
    return {
        "delay_probability": p,
        "flagged": p >= model.threshold,
        "threshold": model.threshold,
        "base_rate": model.card["train"]["late_rate"],
        "inputs": inputs,
    }

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from etl.features import add_point_in_time_features
from etl.transform import build_orders
from ml.features import FEATURES, as_frame, build_pipeline
from ml.train import pick_threshold, split, train
from tests.factory import make_raw

CUTOFF = pd.Timestamp("2018-01-01")


@pytest.fixture(scope="module")
def orders() -> pd.DataFrame:
    return add_point_in_time_features(build_orders(make_raw()))


def test_split_trains_only_on_labels_knowable_at_the_cutoff(orders: pd.DataFrame) -> None:
    train_df, test_df = split(orders, CUTOFF)
    assert (train_df["purchase_ts"] < CUTOFF).all()
    assert (pd.to_datetime(train_df["estimated_delivery"]) < CUTOFF).all()
    assert (test_df["purchase_ts"] >= CUTOFF).all()
    assert train_df["is_late"].notna().all() and test_df["is_late"].notna().all()
    assert not set(train_df["order_id"]) & set(test_df["order_id"])


def test_pick_threshold_maximises_f1() -> None:
    y = pd.Series([False, False, True, True, False, True])
    p = np.array([0.1, 0.2, 0.7, 0.8, 0.75, 0.9])
    # At 0.7 every late order is caught with one false alarm: F1 = 6/7, the best available.
    assert pick_threshold(y, p) == pytest.approx(0.7)


def test_pipeline_scores_rows_with_unseen_categories_and_missing_values(
    orders: pd.DataFrame,
) -> None:
    labelled = orders[orders["is_late"].notna()]
    pipe = build_pipeline().fit(as_frame(labelled), labelled["is_late"].astype(bool))
    odd = pd.DataFrame(
        [
            {f: np.nan for f in FEATURES}
            | {"category": "never_seen", "price": 10, "freight_value": 5}
        ]
    )
    p = pipe.predict_proba(as_frame(odd))[0, 1]
    assert 0.0 <= p <= 1.0


def test_training_reports_out_of_time_metrics(orders: pd.DataFrame) -> None:
    _, card = train(orders, CUTOFF)
    assert card["cutoff"] == "2018-01-01"
    assert pd.Timestamp(card["test"]["from"]) >= CUTOFF
    assert card["train"]["to"] < card["cutoff"]
    assert card["feature_set"] in card["cv_pr_auc"]
    # The synthetic data makes deliveries to BA slower, which a working model must pick up.
    assert card["metrics"]["roc_auc"] > 0.6
    assert {row["feature"] for row in card["feature_importance"]} == set(card["features"])
    assert 0 < card["threshold"] < 1

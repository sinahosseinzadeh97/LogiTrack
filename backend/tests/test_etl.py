from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from etl.extract import read_olist
from etl.features import add_point_in_time_features
from etl.transform import build_orders
from tests.factory import make_raw


@pytest.fixture(scope="module")
def orders() -> pd.DataFrame:
    return add_point_in_time_features(build_orders(make_raw()))


def _raw_with(order_rows: list[dict]) -> dict[str, pd.DataFrame]:
    raw = make_raw(n_orders=len(order_rows))
    for i, overrides in enumerate(order_rows):
        for col, value in overrides.items():
            raw["olist_orders_dataset"].loc[i, col] = value
    return raw


def test_late_means_delivered_on_a_later_calendar_day() -> None:
    promise = "2018-03-10 00:00:00"
    raw = _raw_with(
        [
            {
                "order_status": "delivered",
                "order_estimated_delivery_date": promise,
                "order_delivered_customer_date": "2018-03-10 18:30:00",
            },
            {
                "order_status": "delivered",
                "order_estimated_delivery_date": promise,
                "order_delivered_customer_date": "2018-03-11 08:00:00",
            },
            {
                "order_status": "shipped",
                "order_estimated_delivery_date": promise,
                "order_delivered_customer_date": None,
            },
        ]
    )
    df = build_orders(raw).set_index("order_id")
    assert df.loc["o00000", "delay_days"] == 0 and not df.loc["o00000", "is_late"]
    assert df.loc["o00001", "delay_days"] == 1 and df.loc["o00001", "is_late"]
    assert pd.isna(df.loc["o00002", "is_late"])


def test_order_totals_cover_every_item_but_seller_comes_from_the_first() -> None:
    raw = make_raw(n_orders=2)
    items = raw["olist_order_items_dataset"]
    extra = items.iloc[[0]].assign(order_item_id=2, seller_id="s7", price=100.0, freight_value=10.0)
    raw["olist_order_items_dataset"] = pd.concat([items, extra], ignore_index=True)

    row = build_orders(raw).set_index("order_id").loc["o00000"]
    first = items.iloc[0]
    assert row["n_items"] == 2 and row["n_sellers"] == 2
    assert row["price"] == pytest.approx(first["price"] + 100.0)
    assert row["freight_value"] == pytest.approx(first["freight_value"] + 10.0)
    assert row["seller_id"] == first["seller_id"]


def test_distance_between_sao_paulo_and_rio_is_about_360_km() -> None:
    raw = make_raw(n_orders=1)
    raw["olist_customers_dataset"].loc[0, ["customer_zip_code_prefix", "customer_state"]] = [
        "20001",
        "RJ",
    ]
    raw["olist_order_items_dataset"].loc[0, "seller_id"] = "s0"  # s0 is in SP
    assert build_orders(raw)["distance_km"].iat[0] == pytest.approx(360, abs=15)


def test_seller_history_only_counts_orders_due_before_the_purchase(orders: pd.DataFrame) -> None:
    active = orders[~orders["order_status"].isin(["canceled", "unavailable"])]
    known_at = pd.to_datetime(active["estimated_delivery"]) + pd.Timedelta(days=1)
    for seller_id, group in orders.groupby("seller_id"):
        mine = known_at[active["seller_id"] == seller_id].to_numpy()
        expected = (mine[None, :] < group["purchase_ts"].to_numpy()[:, None]).sum(axis=1)
        np.testing.assert_array_equal(group["seller_prior_orders"].to_numpy(), expected)


def test_an_orders_own_outcome_never_changes_its_features() -> None:
    raw = make_raw()
    before = add_point_in_time_features(build_orders(raw)).set_index("order_id")

    target = before.index[before["is_late"].fillna(False)][0]
    i = int(target[1:])
    promise = pd.Timestamp(raw["olist_orders_dataset"].loc[i, "order_estimated_delivery_date"])
    raw["olist_orders_dataset"].loc[i, "order_delivered_customer_date"] = str(
        promise
    )  # now on time
    after = add_point_in_time_features(build_orders(raw)).set_index("order_id")

    features = ["seller_prior_orders", "seller_prior_late_rate", "network_late_rate_14d"]
    assert not after.loc[target, "is_late"]
    pd.testing.assert_series_equal(before.loc[target, features], after.loc[target, features])
    # Orders bought before that outcome became known are untouched as well.
    earlier = before.index[before["purchase_ts"] <= promise + pd.Timedelta(days=1)]
    pd.testing.assert_frame_equal(before.loc[earlier, features], after.loc[earlier, features])


def test_network_load_counts_purchases_in_the_previous_seven_days(orders: pd.DataFrame) -> None:
    t = orders["purchase_ts"].to_numpy()
    sample = orders.sample(200, random_state=1)
    for ts, count in zip(sample["purchase_ts"], sample["network_orders_7d"], strict=True):
        expected = (
            (t < ts.to_datetime64()) & (t >= (ts - pd.Timedelta(days=7)).to_datetime64())
        ).sum()
        assert count == expected


def test_reader_names_the_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="olist_orders_dataset"):
        read_olist(tmp_path)


def test_reader_names_missing_columns(tmp_path: Path) -> None:
    for stem, frame in make_raw(n_orders=5).items():
        frame = frame.drop(columns=["order_status"]) if stem == "olist_orders_dataset" else frame
        frame.to_csv(tmp_path / f"{stem}.csv", index=False)
    with pytest.raises(ValueError, match="order_status"):
        read_olist(tmp_path)

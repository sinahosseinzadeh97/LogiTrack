"""Point-in-time features: for each order, only what was knowable at its purchase.

The building block is a *due event*: the day after an order's promised date we
know whether it made it (delivered by then) or missed it (delivered later, or
not at all). ``pd.merge_asof(..., allow_exact_matches=False)`` looks up the
running totals of those events as they stood just before each purchase, so no
order ever sees its own outcome or anything from its future.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SMOOTHING_ORDERS = 5  # pull sellers with little history toward the network-wide miss rate
LATE_WINDOW = pd.Timedelta(days=14)
LOAD_WINDOW = pd.Timedelta(days=7)
NO_SELLER = "__no_seller__"
INACTIVE_STATUSES = ("canceled", "unavailable")


def _due_events(df: pd.DataFrame) -> pd.DataFrame:
    active = ~df["order_status"].isin(INACTIVE_STATUSES) & df["estimated_delivery"].notna()
    events = pd.DataFrame(
        {
            "seller_id": df.loc[active, "seller_id"].fillna(NO_SELLER),
            "known_at": pd.to_datetime(df.loc[active, "estimated_delivery"]) + pd.Timedelta(days=1),
            # Not delivered by the promised date (or never) counts as a miss.
            "missed": df.loc[active, "is_late"].fillna(True).astype(int),
        }
    )
    events = events.sort_values("known_at", kind="stable").reset_index(drop=True)
    events["seller_n"] = events.groupby("seller_id").cumcount() + 1
    events["seller_missed"] = events.groupby("seller_id")["missed"].cumsum()
    events["all_n"] = np.arange(1, len(events) + 1)
    events["all_missed"] = events["missed"].cumsum()
    return events


def _totals_before(
    left: pd.DataFrame, at: str, events: pd.DataFrame, cols: list[str], by: str | None = None
) -> pd.DataFrame:
    """Running totals in ``events`` as of strictly before ``left[at]`` (0 if none)."""
    right = events[["known_at", *cols] + ([by] if by else [])]
    out = pd.merge_asof(
        left.sort_values(at),
        right,
        left_on=at,
        right_on="known_at",
        by=by,
        direction="backward",
        allow_exact_matches=False,
    )
    return out.set_index("order_id")[cols].reindex(left["order_id"]).fillna(0)


def _recent_promise_gap(df: pd.DataFrame) -> pd.Series:
    """Promised days minus the median promise of orders bought in the previous 7 days."""
    ordered = df[["purchase_ts", "promised_days"]].sort_values("purchase_ts", kind="stable")
    recent = ordered.rolling(LOAD_WINDOW, on="purchase_ts", closed="left")["promised_days"].median()
    return df["promised_days"] - recent.reindex(df.index)


def add_point_in_time_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    events = _due_events(df)
    left = df[["order_id", "purchase_ts"]].assign(
        seller_id=df["seller_id"].fillna(NO_SELLER),
        window_start=df["purchase_ts"] - LATE_WINDOW,
    )

    seller = _totals_before(
        left, "purchase_ts", events, ["seller_n", "seller_missed"], by="seller_id"
    )
    now = _totals_before(left, "purchase_ts", events, ["all_n", "all_missed"])
    then = _totals_before(left, "window_start", events, ["all_n", "all_missed"])

    prior_rate = (now["all_missed"] / now["all_n"]).where(now["all_n"] > 0)
    window_n = now["all_n"] - then["all_n"]
    df["seller_prior_orders"] = seller["seller_n"].astype(int).to_numpy()
    df["seller_prior_late_rate"] = (
        (seller["seller_missed"] + SMOOTHING_ORDERS * prior_rate)
        / (seller["seller_n"] + SMOOTHING_ORDERS)
    ).to_numpy()
    df["network_late_rate_14d"] = (
        ((now["all_missed"] - then["all_missed"]) / window_n).where(window_n > 0).to_numpy()
    )

    purchases = np.sort(df["purchase_ts"].to_numpy())
    t = df["purchase_ts"].to_numpy()
    df["network_orders_7d"] = np.searchsorted(purchases, t, side="left") - np.searchsorted(
        purchases, t - LOAD_WINDOW.to_timedelta64(), side="left"
    )
    df["promise_gap_7d"] = _recent_promise_gap(df)
    return df

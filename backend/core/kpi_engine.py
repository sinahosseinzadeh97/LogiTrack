"""
KPI Engine — single source of truth for all LogiTrack KPI calculations.

Every function in this module is a **pure function**:
  - No I/O, no database calls, no side effects.
  - All input arrives via DataFrames / scalars.
  - All output is a scalar, DataFrame, or dict.

The engine assumes the *delivered* DataFrame (``df``) has been produced by
:mod:`etl.clean` and :mod:`etl.enrich` and contains at least the columns:

  delay_days          float   positive = late, negative = early
  is_late             bool    True when delay_days > 0
  freight_value       float   shipment cost in BRL
  category_name       str | NaN
  seller_id           str
  seller_state        str | NaN
  purchase_timestamp  datetime64[ns, UTC]

The *all-orders* DataFrame (``df_all``) additionally includes cancelled /
unavailable orders and is used only for fulfillment rate computation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    pass  # keep imports clean; pandas re-exported via type annotations only

__all__ = [
    "calculate_otif",
    "calculate_avg_delay",
    "calculate_fulfillment_rate",
    "calculate_cost_per_shipment",
    "calculate_weekly_otif_trend",
    "calculate_delay_by_category",
    "calculate_seller_scorecard",
    "calculate_kpi_summary",
]

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_REQUIRED_COLUMNS_DELIVERED: frozenset[str] = frozenset(
    {"delay_days", "is_late", "freight_value", "purchase_timestamp"}
)


def _guard_empty(df: pd.DataFrame, label: str = "DataFrame") -> None:
    """Raise :class:`ValueError` when *df* has no rows."""
    if df.empty:
        raise ValueError(f"{label} must not be empty.")


def _to_week_start(ts: pd.Series) -> pd.Series:
    """Return the Monday of the ISO week for each element of a datetime Series."""
    # Normalise to date, subtract the weekday offset so we always land on Monday
    dt = pd.to_datetime(ts, utc=True)
    return (dt - pd.to_timedelta(dt.dt.dayofweek, unit="D")).dt.normalize().dt.date


# ---------------------------------------------------------------------------
# 1. OTIF — On-Time In-Full
# ---------------------------------------------------------------------------


def calculate_otif(df: pd.DataFrame) -> float:
    """On-Time In-Full rate.

    Returns the percentage of delivered orders where ``delay_days <= 0``
    (i.e. the shipment arrived on time or early).

    Parameters
    ----------
    df:
        Delivered-orders DataFrame.  Must contain a boolean ``is_late`` column
        where ``True`` means the order arrived after the estimated delivery.

    Returns
    -------
    float
        OTIF percentage in the range [0.0, 100.0].

    Raises
    ------
    ValueError
        If *df* is empty.

    Examples
    --------
    >>> calculate_otif(df)
    83.5
    """
    _guard_empty(df, "df")
    on_time = (~df["is_late"]).sum()
    return float(on_time / len(df) * 100)


# ---------------------------------------------------------------------------
# 2. Average delay days
# ---------------------------------------------------------------------------


def calculate_avg_delay(
    df: pd.DataFrame,
    group_by: str | None = None,
    only_late: bool = True,
) -> float | pd.DataFrame:
    """Mean delay days, optionally grouped and/or restricted to late orders.

    Parameters
    ----------
    df:
        Delivered-orders DataFrame with ``delay_days`` (float) and
        ``is_late`` (bool) columns.
    group_by:
        Optional column name to group results by (e.g. ``"seller_id"``).
        When provided, returns a DataFrame instead of a scalar.
    only_late:
        When ``True`` (default), excludes on-time deliveries
        (``is_late == False``) from the average so the metric reflects
        the *severity* of lateness rather than the overall mean.

    Returns
    -------
    float
        Mean delay days when *group_by* is ``None``.
    pd.DataFrame
        Columns ``[group_by, 'avg_delay_days']`` when *group_by* is given.
        Rows with no late orders in a group receive ``NaN``.

    Raises
    ------
    ValueError
        If *df* is empty.
    """
    _guard_empty(df, "df")

    working = df.copy()
    if only_late:
        working = working[working["is_late"]]

    if group_by is not None:
        result = (
            working.groupby(group_by, as_index=False)["delay_days"]
            .mean()
            .rename(columns={"delay_days": "avg_delay_days"})
        )
        return result

    if working.empty:
        return float("nan")

    return float(working["delay_days"].mean())


# ---------------------------------------------------------------------------
# 3. Fulfillment rate
# ---------------------------------------------------------------------------


def calculate_fulfillment_rate(df_all: pd.DataFrame) -> float:
    """Percentage of all orders (any status) that reached ``'delivered'``.

    Uses the ``order_status`` column present in ``df_all``  produced by the
    ETL clean stage.

    Parameters
    ----------
    df_all:
        All-orders DataFrame (including cancelled, unavailable, etc.).  Must
        contain an ``order_status`` column.

    Returns
    -------
    float
        Fulfillment percentage in [0.0, 100.0].

    Raises
    ------
    ValueError
        If *df_all* is empty.
    """
    _guard_empty(df_all, "df_all")
    delivered = (df_all["order_status"] == "delivered").sum()
    return float(delivered / len(df_all) * 100)


# ---------------------------------------------------------------------------
# 4. Cost per shipment
# ---------------------------------------------------------------------------


def calculate_cost_per_shipment(df: pd.DataFrame) -> float:
    """Mean freight value per delivered order.

    Parameters
    ----------
    df:
        Delivered-orders DataFrame with ``freight_value`` column.

    Returns
    -------
    float
        Mean freight value in BRL.

    Raises
    ------
    ValueError
        If *df* is empty.
    """
    _guard_empty(df, "df")
    return float(df["freight_value"].mean())


# ---------------------------------------------------------------------------
# 5. Weekly OTIF trend
# ---------------------------------------------------------------------------


def calculate_weekly_otif_trend(df: pd.DataFrame, weeks: int = 8) -> pd.DataFrame:
    """OTIF rate per ISO week for the last *N* weeks.

    The function anchors to the most recent ``purchase_timestamp`` in the
    dataset (not wall-clock time) so results are reproducible against a fixed
    dataset regardless of when the function is called.

    Parameters
    ----------
    df:
        Delivered-orders DataFrame with ``purchase_timestamp`` and ``is_late``
        columns.
    weeks:
        Number of complete ISO weeks to return, counting backwards from the
        latest timestamp in *df*.  Defaults to 8.

    Returns
    -------
    pd.DataFrame
        Columns: ``['week_start', 'otif_rate']``.

        - ``week_start`` — ``datetime.date`` of the Monday that opens the week.
        - ``otif_rate``  — OTIF percentage for that week [0.0, 100.0].

        Weeks with no deliveries are included with ``otif_rate = NaN``.
        Rows are ordered chronologically (oldest first).

    Raises
    ------
    ValueError
        If *df* is empty.
    """
    _guard_empty(df, "df")

    working = df.copy()
    working["week_start"] = _to_week_start(working["purchase_timestamp"])

    # Determine the cutoff: retain only the last `weeks` complete weeks.
    latest_week = working["week_start"].max()
    # Build all week boundaries
    all_weeks = pd.date_range(
        end=pd.Timestamp(latest_week),
        periods=weeks,
        freq="W-MON",  # weekly, anchored to Monday
    ).date

    # Filter to rows whose week_start is in our range
    working = working[working["week_start"].isin(all_weeks)]

    grouped = working.groupby("week_start", as_index=False).apply(
        lambda g: pd.Series(
            {"otif_rate": float((~g["is_late"]).sum() / len(g) * 100)}
        ),
        include_groups=False,
    )

    # Reindex to ensure all weeks appear (even empty ones)
    week_frame = pd.DataFrame({"week_start": all_weeks})
    result = week_frame.merge(grouped, on="week_start", how="left")
    return result[["week_start", "otif_rate"]].sort_values("week_start").reset_index(drop=True)


# ---------------------------------------------------------------------------
# 6. Delay by category
# ---------------------------------------------------------------------------


def calculate_delay_by_category(df: pd.DataFrame) -> pd.DataFrame:
    """Average delay and order count per product category.

    Only rows where ``is_late == True`` feed the ``avg_delay_days`` aggregate
    so the metric reflects *severity* of lateness.

    Parameters
    ----------
    df:
        Delivered-orders DataFrame with ``category_name``, ``delay_days``,
        and ``is_late`` columns.

    Returns
    -------
    pd.DataFrame
        Columns: ``['category_name', 'avg_delay_days', 'order_count']``.
        Sorted by ``avg_delay_days`` descending (worst performers first).
        Rows with ``None``/``NaN`` category_name are dropped.

    Raises
    ------
    ValueError
        If *df* is empty.
    """
    _guard_empty(df, "df")

    working = df.dropna(subset=["category_name"]).copy()

    # Order count is total orders per category (including on-time)
    order_counts = (
        working.groupby("category_name", as_index=False)
        .size()
        .rename(columns={"size": "order_count"})
    )

    # avg_delay_days is only over late orders
    late = working[working["is_late"]]
    avg_delays = (
        late.groupby("category_name", as_index=False)["delay_days"]
        .mean()
        .rename(columns={"delay_days": "avg_delay_days"})
    )

    result = order_counts.merge(avg_delays, on="category_name", how="left")
    result = result.sort_values("avg_delay_days", ascending=False).reset_index(drop=True)
    return result[["category_name", "avg_delay_days", "order_count"]]


# ---------------------------------------------------------------------------
# 7. Seller scorecard
# ---------------------------------------------------------------------------


def calculate_seller_scorecard(df: pd.DataFrame) -> pd.DataFrame:
    """Per-seller performance scorecard.

    Parameters
    ----------
    df:
        Delivered-orders DataFrame with ``seller_id``, ``seller_state``,
        ``is_late``, ``delay_days``, and ``freight_value`` columns.

    Returns
    -------
    pd.DataFrame
        Columns:
        ``['seller_id', 'seller_state', 'total_orders', 'delay_rate',
        'avg_delay_days', 'avg_cost']``.

        - ``delay_rate``      — fraction of late orders [0.0, 1.0].
        - ``avg_delay_days``  — mean delay over *late* orders only.
        - ``avg_cost``        — mean freight value across all orders.

        Sorted by ``delay_rate`` descending (worst performers first).

    Raises
    ------
    ValueError
        If *df* is empty.
    """
    _guard_empty(df, "df")

    # Base aggregates (all orders per seller)
    base = df.groupby("seller_id", as_index=False).agg(
        seller_state=("seller_state", "first"),
        total_orders=("is_late", "count"),
        delay_rate=("is_late", "mean"),
        avg_cost=("freight_value", "mean"),
    )

    # avg_delay_days over late orders only
    late_avg = (
        df[df["is_late"]]
        .groupby("seller_id", as_index=False)["delay_days"]
        .mean()
        .rename(columns={"delay_days": "avg_delay_days"})
    )

    result = base.merge(late_avg, on="seller_id", how="left")
    result = result.sort_values("delay_rate", ascending=False).reset_index(drop=True)
    return result[
        ["seller_id", "seller_state", "total_orders", "delay_rate", "avg_delay_days", "avg_cost"]
    ]


# ---------------------------------------------------------------------------
# 8. KPI Summary dict
# ---------------------------------------------------------------------------


def calculate_kpi_summary(df: pd.DataFrame, df_all: pd.DataFrame) -> dict:
    """Aggregate all top-level KPIs into a single dictionary.

    Parameters
    ----------
    df:
        Delivered-orders DataFrame (status == ``'delivered'``).
    df_all:
        All-orders DataFrame (all statuses).

    Returns
    -------
    dict
        Keys:

        - ``otif_rate``               — OTIF % this week
        - ``avg_delay_days``          — mean delay, late orders only
        - ``fulfillment_rate``        — % of all orders delivered
        - ``avg_cost_per_shipment``   — mean freight value (BRL)
        - ``total_shipments``         — row count in *df*
        - ``late_shipments``          — count of late orders in *df*
        - ``week_over_week_otif_delta``— current week OTIF minus previous
          week OTIF; ``None`` when either week has no data

    Raises
    ------
    ValueError
        If *df* or *df_all* is empty.
    """
    _guard_empty(df, "df")
    _guard_empty(df_all, "df_all")

    otif = calculate_otif(df)
    avg_delay = calculate_avg_delay(df, only_late=True)
    fulfillment = calculate_fulfillment_rate(df_all)
    avg_cost = calculate_cost_per_shipment(df)
    total_shipments = int(len(df))
    late_shipments = int(df["is_late"].sum())

    # -----------------------------------------------------------------------
    # Week-over-week OTIF delta
    # -----------------------------------------------------------------------
    working = df.copy()
    working["week_start"] = _to_week_start(working["purchase_timestamp"])

    # Sort all unique weeks descending
    sorted_weeks = sorted(working["week_start"].unique(), reverse=True)

    def _week_otif(week_label: object) -> float | None:
        subset = working[working["week_start"] == week_label]
        if subset.empty:
            return None
        return float((~subset["is_late"]).sum() / len(subset) * 100)

    current_otif: float | None = _week_otif(sorted_weeks[0]) if len(sorted_weeks) >= 1 else None
    prev_otif: float | None = _week_otif(sorted_weeks[1]) if len(sorted_weeks) >= 2 else None

    if current_otif is not None and prev_otif is not None:
        wow_delta: float | None = round(current_otif - prev_otif, 4)
    else:
        wow_delta = None

    return {
        "otif_rate": round(otif, 4),
        "avg_delay_days": round(float(avg_delay), 4) if avg_delay == avg_delay else float("nan"),
        "fulfillment_rate": round(fulfillment, 4),
        "avg_cost_per_shipment": round(avg_cost, 4),
        "total_shipments": total_shipments,
        "late_shipments": late_shipments,
        "week_over_week_otif_delta": wow_delta,
    }

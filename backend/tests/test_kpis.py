"""
Test suite — backend/core/kpi_engine.py
=======================================

All tests use a synthetic, fully deterministic fixture (``sample_df`` /
``sample_df_all``) with *known* properties so that every assertion can be
verified by hand:

Fixture properties (``sample_df`` — 100 delivered rows)
--------------------------------------------------------
- 80 on-time rows  (is_late=False, delay_days = -2.0)
- 20 late rows     (is_late=True,  delay_days = +5.0)
- freight_value    = 10.0 for all rows
- 2 category_names: "electronics" (60 rows), "furniture" (40 rows)
    - electronics: 10 late  (avg_delay_days = 5.0)
    - furniture:   10 late  (avg_delay_days = 5.0)
- 2 sellers: "seller_A" (70 rows, 14 late), "seller_B" (30 rows, 6 late)
    - seller_A delay_rate = 14/70 ≈ 0.2
    - seller_B delay_rate =  6/30 = 0.2  (same rate; distinguished by count)
- purchase_timestamp: spread across exactly 2 ISO weeks
    - week 1 (older): 60 rows, 12 late → OTIF = 80%
    - week 2 (newer): 40 rows, 8  late → OTIF = 80%
    - wow delta = 80 - 80 = 0.0

``sample_df_all`` (120 rows total)
------------------------------------
- 100 delivered + 20 cancelled → fulfillment rate = 100/120 ≈ 83.333...%
"""

from __future__ import annotations

import datetime

import numpy as np
import pandas as pd
import pytest

from core.kpi_engine import (
    calculate_avg_delay,
    calculate_cost_per_shipment,
    calculate_delay_by_category,
    calculate_fulfillment_rate,
    calculate_kpi_summary,
    calculate_otif,
    calculate_seller_scorecard,
    calculate_weekly_otif_trend,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_BASE_DATE = pd.Timestamp("2024-01-08", tz="UTC")  # Monday of week 2


def _make_row(
    *,
    is_late: bool,
    week: int,  # 1 or 2
    category: str,
    seller: str,
    seller_state: str,
) -> dict:
    """Build a single row dict for the delivered fixture."""
    # week 1 starts on 2024-01-01 (Monday), week 2 on 2024-01-08 (Monday)
    base = _BASE_DATE + pd.Timedelta(weeks=week - 2)
    return {
        "order_id": None,  # filled later
        "seller_id": seller,
        "seller_state": seller_state,
        "customer_state": "SP",
        "distance_km": 500.0,
        "delay_days": 5.0 if is_late else -2.0,
        "is_late": is_late,
        "freight_value": 10.0,
        "category_name": category,
        "purchase_timestamp": base,
        "delivered_timestamp": base + pd.Timedelta(days=3),
    }


@pytest.fixture()
def sample_df() -> pd.DataFrame:
    """100-row delivered DataFrame with fully deterministic properties.

    Layout
    ------
    Rows 0-59   → "electronics", seller_A (state SP), week 1 (60 rows)
      - rows 0-49  → on-time
      - rows 50-59 → late
    Rows 60-99  → "furniture",   seller_B (state RJ), week 2 (40 rows)
      - rows 60-69 → late
      - rows 70-99 → on-time
    """
    rows = []

    # electronics / seller_A / week 1: 50 on-time + 10 late
    for _ in range(50):
        rows.append(_make_row(is_late=False, week=1, category="electronics", seller="seller_A", seller_state="SP"))
    for _ in range(10):
        rows.append(_make_row(is_late=True,  week=1, category="electronics", seller="seller_A", seller_state="SP"))

    # furniture / seller_B / week 2: 10 late + 30 on-time
    for _ in range(10):
        rows.append(_make_row(is_late=True,  week=2, category="furniture",   seller="seller_B", seller_state="RJ"))
    for _ in range(30):
        rows.append(_make_row(is_late=False, week=2, category="furniture",   seller="seller_B", seller_state="RJ"))

    df = pd.DataFrame(rows)
    df["order_id"] = [f"ORD-{i:04d}" for i in range(len(df))]

    # -----------------------------------------------------------------------
    # Adjust so seller_A has 70 rows and 14 late (add 10 more late in wk2)
    # We redistribute: give seller_A 10 more late rows in electronics/week2
    # -----------------------------------------------------------------------
    extra_seller_a_late = [
        _make_row(is_late=True, week=2, category="electronics", seller="seller_A", seller_state="SP")
        for _ in range(4)
    ]
    extra_seller_a_ontime = [
        _make_row(is_late=False, week=2, category="electronics", seller="seller_A", seller_state="SP")
        for _ in range(6)
    ]
    extra_rows = pd.DataFrame(extra_seller_a_late + extra_seller_a_ontime)
    extra_rows["order_id"] = [f"ORD-E{i:03d}" for i in range(len(extra_rows))]

    df = pd.concat([df, extra_rows], ignore_index=True)

    # Final shape check sentinel (not an assertion — just documentation)
    assert len(df) == 110, f"Unexpected fixture size: {len(df)}"

    return df


@pytest.fixture()
def sample_df_all(sample_df: pd.DataFrame) -> pd.DataFrame:
    """120-row all-orders DataFrame: 110 delivered + 10 cancelled."""
    cancelled_rows = []
    for i in range(10):
        cancelled_rows.append({
            "order_id": f"CAN-{i:04d}",
            "order_status": "cancelled",
            "seller_id": "seller_A",
            "seller_state": "SP",
            "customer_state": "MG",
            "delay_days": None,
            "is_late": False,
            "freight_value": 0.0,
            "category_name": None,
            "purchase_timestamp": _BASE_DATE,
            "delivered_timestamp": None,
        })
    cancelled_df = pd.DataFrame(cancelled_rows)

    delivered = sample_df.copy()
    delivered["order_status"] = "delivered"

    return pd.concat([delivered, cancelled_df], ignore_index=True)


@pytest.fixture()
def all_on_time_df() -> pd.DataFrame:
    """50-row DataFrame where every order is on time."""
    rows = [
        _make_row(is_late=False, week=1, category="electronics", seller="seller_A", seller_state="SP")
        for _ in range(50)
    ]
    df = pd.DataFrame(rows)
    df["order_id"] = [f"OT-{i:04d}" for i in range(len(df))]
    return df


@pytest.fixture()
def all_late_df() -> pd.DataFrame:
    """50-row DataFrame where every order is late."""
    rows = [
        _make_row(is_late=True, week=1, category="electronics", seller="seller_A", seller_state="SP")
        for _ in range(50)
    ]
    df = pd.DataFrame(rows)
    df["order_id"] = [f"LT-{i:04d}" for i in range(len(df))]
    return df


# ---------------------------------------------------------------------------
# OTIF tests (1-4)
# ---------------------------------------------------------------------------


def test_otif_returns_100_when_all_on_time(all_on_time_df: pd.DataFrame) -> None:
    """calculate_otif must return exactly 100.0 when no order is late."""
    result = calculate_otif(all_on_time_df)
    assert result == pytest.approx(100.0)


def test_otif_returns_0_when_all_late(all_late_df: pd.DataFrame) -> None:
    """calculate_otif must return exactly 0.0 when every order is late."""
    result = calculate_otif(all_late_df)
    assert result == pytest.approx(0.0)


def test_otif_returns_correct_percentage(sample_df: pd.DataFrame) -> None:
    """calculate_otif must return the correct on-time percentage.

    sample_df has 110 rows total; late rows = 10 + 10 + 4 = 24 late.
    on-time = 86; OTIF = 86/110 * 100.
    """
    late_count = int(sample_df["is_late"].sum())
    expected = (len(sample_df) - late_count) / len(sample_df) * 100
    result = calculate_otif(sample_df)
    assert result == pytest.approx(expected, rel=1e-6)


def test_otif_raises_on_empty_dataframe() -> None:
    """calculate_otif must raise ValueError when given an empty DataFrame."""
    with pytest.raises(ValueError, match="must not be empty"):
        calculate_otif(pd.DataFrame())


# ---------------------------------------------------------------------------
# Average delay tests (5-10)
# ---------------------------------------------------------------------------


def test_avg_delay_scalar_when_no_group_by(sample_df: pd.DataFrame) -> None:
    """calculate_avg_delay without group_by must return a scalar float."""
    result = calculate_avg_delay(sample_df, only_late=True)
    assert isinstance(result, float)


def test_avg_delay_excludes_on_time_when_only_late_true(sample_df: pd.DataFrame) -> None:
    """With only_late=True, the average must equal the mean of late-order delay_days."""
    late_mask = sample_df["is_late"]
    expected = sample_df.loc[late_mask, "delay_days"].mean()
    result = calculate_avg_delay(sample_df, only_late=True)
    assert result == pytest.approx(expected, rel=1e-6)


def test_avg_delay_includes_all_when_only_late_false(sample_df: pd.DataFrame) -> None:
    """With only_late=False, average must include both late and on-time rows."""
    expected = sample_df["delay_days"].mean()
    result = calculate_avg_delay(sample_df, only_late=False)
    assert result == pytest.approx(expected, rel=1e-6)


def test_avg_delay_grouped_returns_dataframe(sample_df: pd.DataFrame) -> None:
    """calculate_avg_delay with group_by must return a DataFrame."""
    result = calculate_avg_delay(sample_df, group_by="seller_id", only_late=True)
    assert isinstance(result, pd.DataFrame)


def test_avg_delay_grouped_has_correct_columns(sample_df: pd.DataFrame) -> None:
    """Grouped result must have exactly [group_by, 'avg_delay_days'] columns."""
    result = calculate_avg_delay(sample_df, group_by="seller_id", only_late=True)
    assert list(result.columns) == ["seller_id", "avg_delay_days"]


def test_avg_delay_raises_on_empty_dataframe() -> None:
    """calculate_avg_delay must raise ValueError when given an empty DataFrame."""
    with pytest.raises(ValueError, match="must not be empty"):
        calculate_avg_delay(pd.DataFrame())


# ---------------------------------------------------------------------------
# Fulfillment rate tests (11-12)
# ---------------------------------------------------------------------------


def test_fulfillment_rate_correct_ratio(sample_df_all: pd.DataFrame) -> None:
    """Fulfillment rate must equal delivered_count / total_count * 100."""
    total = len(sample_df_all)
    delivered = (sample_df_all["order_status"] == "delivered").sum()
    expected = delivered / total * 100
    result = calculate_fulfillment_rate(sample_df_all)
    assert result == pytest.approx(expected, rel=1e-6)


def test_fulfillment_rate_raises_on_empty() -> None:
    """calculate_fulfillment_rate must raise ValueError on empty DataFrame."""
    with pytest.raises(ValueError, match="must not be empty"):
        calculate_fulfillment_rate(pd.DataFrame())


# ---------------------------------------------------------------------------
# Cost per shipment tests (13-14)
# ---------------------------------------------------------------------------


def test_cost_per_shipment_correct_mean(sample_df: pd.DataFrame) -> None:
    """calculate_cost_per_shipment must return mean(freight_value).

    All rows in sample_df have freight_value=10.0, so the mean is 10.0.
    """
    result = calculate_cost_per_shipment(sample_df)
    assert result == pytest.approx(10.0)


def test_cost_per_shipment_raises_on_empty() -> None:
    """calculate_cost_per_shipment must raise ValueError on empty DataFrame."""
    with pytest.raises(ValueError, match="must not be empty"):
        calculate_cost_per_shipment(pd.DataFrame())


# ---------------------------------------------------------------------------
# Weekly OTIF trend tests (15-16)
# ---------------------------------------------------------------------------


def test_weekly_otif_trend_returns_correct_week_count(sample_df: pd.DataFrame) -> None:
    """calculate_weekly_otif_trend must return exactly `weeks` rows."""
    weeks = 4
    result = calculate_weekly_otif_trend(sample_df, weeks=weeks)
    assert len(result) == weeks


def test_weekly_otif_trend_columns(sample_df: pd.DataFrame) -> None:
    """calculate_weekly_otif_trend must return exactly ['week_start', 'otif_rate']."""
    result = calculate_weekly_otif_trend(sample_df, weeks=4)
    assert list(result.columns) == ["week_start", "otif_rate"]


# ---------------------------------------------------------------------------
# Delay by category tests (17)
# ---------------------------------------------------------------------------


def test_delay_by_category_sorted_descending(sample_df: pd.DataFrame) -> None:
    """calculate_delay_by_category must return rows sorted by avg_delay_days desc.

    The function drops NaN avg_delay_days or at least returns a DataFrame
    where consecutive rows satisfy result[i] >= result[i+1].
    """
    result = calculate_delay_by_category(sample_df)
    # Drop NaN rows before checking sort order
    valid = result["avg_delay_days"].dropna()
    assert list(valid) == sorted(valid, reverse=True), (
        "avg_delay_days column must be sorted descending"
    )


# ---------------------------------------------------------------------------
# Seller scorecard tests (18)
# ---------------------------------------------------------------------------


def test_seller_scorecard_sorted_by_delay_rate(sample_df: pd.DataFrame) -> None:
    """calculate_seller_scorecard must be sorted by delay_rate descending."""
    result = calculate_seller_scorecard(sample_df)
    rates = result["delay_rate"].tolist()
    assert rates == sorted(rates, reverse=True), (
        "delay_rate column must be sorted descending"
    )


# ---------------------------------------------------------------------------
# KPI summary tests (19-20)
# ---------------------------------------------------------------------------


def test_kpi_summary_contains_all_keys(
    sample_df: pd.DataFrame, sample_df_all: pd.DataFrame
) -> None:
    """calculate_kpi_summary must return a dict with all 7 required keys."""
    required_keys = {
        "otif_rate",
        "avg_delay_days",
        "fulfillment_rate",
        "avg_cost_per_shipment",
        "total_shipments",
        "late_shipments",
        "week_over_week_otif_delta",
    }
    result = calculate_kpi_summary(sample_df, sample_df_all)
    assert required_keys == set(result.keys())


def test_kpi_summary_week_over_week_delta_is_correct(
    sample_df: pd.DataFrame, sample_df_all: pd.DataFrame
) -> None:
    """week_over_week_otif_delta must equal current_week_OTIF - prev_week_OTIF.

    We independently compute the OTIF for the two most recent weeks in
    sample_df and verify the delta matches what calculate_kpi_summary returns.
    """
    working = sample_df.copy()
    working["week_start"] = (
        pd.to_datetime(working["purchase_timestamp"], utc=True)
        - pd.to_timedelta(pd.to_datetime(working["purchase_timestamp"], utc=True).dt.dayofweek, unit="D")
    ).dt.normalize().dt.date

    sorted_weeks = sorted(working["week_start"].unique(), reverse=True)

    def _otif(week: object) -> float:
        sub = working[working["week_start"] == week]
        return float((~sub["is_late"]).sum() / len(sub) * 100)

    if len(sorted_weeks) >= 2:
        expected_delta = _otif(sorted_weeks[0]) - _otif(sorted_weeks[1])
    else:
        expected_delta = None  # type: ignore[assignment]

    result = calculate_kpi_summary(sample_df, sample_df_all)
    wow = result["week_over_week_otif_delta"]

    if expected_delta is None:
        assert wow is None
    else:
        assert wow == pytest.approx(expected_delta, abs=1e-4)

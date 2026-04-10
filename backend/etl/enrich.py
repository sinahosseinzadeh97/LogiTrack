"""
ETL Step 2 — Feature enrichment.

Adds geo-spatial, temporal, historical seller, and cost-efficiency features
to the cleaned DataFrame produced by :mod:`etl.clean`.

All functions operate on DataFrames and return new DataFrames (no in-place
mutation) to keep transformations composable and testable in isolation.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
from geopy.distance import geodesic

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Geo features
# ---------------------------------------------------------------------------


def add_geo_features(df: pd.DataFrame, geo_df: pd.DataFrame) -> pd.DataFrame:
    """Join geolocation coordinates to seller and customer zip-code prefixes.

    The Olist geolocation table contains multiple coordinate pairs per zip
    prefix (one per city district).  To keep the join deterministic we take
    the **first** coordinate pair per prefix after sorting by zip.

    Geodesic distance between seller and customer coordinates is computed
    using :func:`geopy.distance.geodesic` (WGS-84 ellipsoid).  Rows where
    either endpoint is missing are set to ``NaN`` and logged.

    Parameters
    ----------
    df:
        Cleaned delivered-orders DataFrame from :func:`etl.clean.clean_orders`.
    geo_df:
        Raw geolocation DataFrame (``olist_geolocation_dataset``).

    Returns
    -------
    pd.DataFrame
        *df* augmented with columns:
        ``seller_lat``, ``seller_lng``, ``customer_lat``, ``customer_lng``,
        ``distance_km``.
    """
    df = df.copy()

    # Deduplicate: first coordinate per zip prefix
    geo_deduped = (
        geo_df
        .sort_values("geolocation_zip_code_prefix")
        .drop_duplicates(subset=["geolocation_zip_code_prefix"], keep="first")
        [["geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng"]]
    )

    # ------------------------------------------------------------------
    # Seller coordinates
    # ------------------------------------------------------------------
    df = df.merge(
        geo_deduped.rename(
            columns={
                "geolocation_zip_code_prefix": "seller_zip_code_prefix",
                "geolocation_lat": "seller_lat",
                "geolocation_lng": "seller_lng",
            }
        ),
        on="seller_zip_code_prefix",
        how="left",
    )

    # ------------------------------------------------------------------
    # Customer coordinates
    # ------------------------------------------------------------------
    df = df.merge(
        geo_deduped.rename(
            columns={
                "geolocation_zip_code_prefix": "customer_zip_code_prefix",
                "geolocation_lat": "customer_lat",
                "geolocation_lng": "customer_lng",
            }
        ),
        on="customer_zip_code_prefix",
        how="left",
    )

    # ------------------------------------------------------------------
    # Geodesic distance
    # ------------------------------------------------------------------
    missing_mask = (
        df["seller_lat"].isna()
        | df["seller_lng"].isna()
        | df["customer_lat"].isna()
        | df["customer_lng"].isna()
    )
    missing_count = int(missing_mask.sum())
    if missing_count:
        logger.warning(
            "%d row(s) have missing coordinates — distance_km will be NaN.",
            missing_count,
        )

    def _geodesic_km(row: pd.Series) -> float | None:
        """Return geodesic distance in km, or ``None`` on missing inputs."""
        try:
            return geodesic(
                (row["seller_lat"], row["seller_lng"]),
                (row["customer_lat"], row["customer_lng"]),
            ).km
        except Exception:  # noqa: BLE001 — geopy raises ValueError on bad coords
            return None

    # Compute only for rows with complete coordinates to avoid slow iteration
    # over the full DataFrame.
    distances = np.full(len(df), np.nan, dtype=float)
    valid_idx = df.index[~missing_mask]

    if len(valid_idx):
        distances[df.index.get_indexer(valid_idx)] = (
            df.loc[valid_idx]
            .apply(_geodesic_km, axis=1)
            .values
        )

    df["distance_km"] = distances
    logger.info(
        "add_geo_features: distance_km computed for %d/%d rows.",
        len(valid_idx),
        len(df),
    )
    return df


# ---------------------------------------------------------------------------
# Temporal features
# ---------------------------------------------------------------------------


def add_temporal_features(df: pd.DataFrame) -> pd.DataFrame:
    """Extract ``day_of_week`` and ``month`` from ``purchase_timestamp``.

    Parameters
    ----------
    df:
        DataFrame with a ``purchase_timestamp`` column (datetime64, UTC-aware).

    Returns
    -------
    pd.DataFrame
        *df* augmented with:
        - ``day_of_week`` — int8 [0=Monday … 6=Sunday]
        - ``month``       — int8 [1–12]
    """
    df = df.copy()

    if "purchase_timestamp" not in df.columns:
        logger.warning(
            "Column 'purchase_timestamp' not found — temporal features skipped."
        )
        return df

    ts = pd.to_datetime(df["purchase_timestamp"], utc=True)
    df["day_of_week"] = ts.dt.dayofweek.astype("Int8")
    df["month"] = ts.dt.month.astype("Int8")

    logger.debug(
        "add_temporal_features: day_of_week and month added (%d rows).", len(df)
    )
    return df


# ---------------------------------------------------------------------------
# Seller historical delay rate
# ---------------------------------------------------------------------------


def add_seller_delay_rate(df: pd.DataFrame) -> pd.DataFrame:
    """Compute and join the historical late-delivery rate per seller.

    The rate is calculated as ``mean(is_late)`` across **all orders in df**
    for each ``seller_id``.

    .. warning::
        This feature is computed from the same data used for training, making
        it a *look-ahead* feature that must **not** be used during real-time
        inference.  At inference time, the rate should be read from the
        ``seller_stats.delay_rate`` column which is set at ETL time.

    Parameters
    ----------
    df:
        DataFrame with ``seller_id`` and ``is_late`` columns.

    Returns
    -------
    pd.DataFrame
        *df* augmented with ``seller_historical_delay_rate`` (float).
    """
    df = df.copy()

    if "seller_id" not in df.columns or "is_late" not in df.columns:
        logger.warning(
            "Columns 'seller_id' or 'is_late' not found — "
            "seller_historical_delay_rate skipped."
        )
        return df

    seller_rates = (
        df.groupby("seller_id", as_index=False)["is_late"]
        .mean()
        .rename(columns={"is_late": "seller_historical_delay_rate"})
    )

    df = df.merge(seller_rates, on="seller_id", how="left")

    logger.info(
        "add_seller_delay_rate: computed for %d unique sellers.",
        seller_rates["seller_id"].nunique(),
    )
    return df


# ---------------------------------------------------------------------------
# Cost per km
# ---------------------------------------------------------------------------


def compute_cost_per_km(df: pd.DataFrame) -> pd.DataFrame:
    """Compute ``cost_per_km = freight_value / distance_km``.

    Rows where ``distance_km`` is zero or NaN receive a ``NaN`` result to
    avoid division-by-zero errors producing ``inf`` values.

    Parameters
    ----------
    df:
        DataFrame with ``freight_value`` (float) and ``distance_km`` (float).

    Returns
    -------
    pd.DataFrame
        *df* augmented with ``cost_per_km`` (float, NaN where not computable).
    """
    df = df.copy()

    distance = pd.to_numeric(df.get("distance_km"), errors="coerce")
    freight = pd.to_numeric(df.get("freight_value"), errors="coerce")

    df["cost_per_km"] = np.where(
        (distance.isna()) | (distance == 0),
        np.nan,
        freight / distance,
    )

    valid_count = int(df["cost_per_km"].notna().sum())
    logger.debug(
        "compute_cost_per_km: valid values for %d/%d rows.", valid_count, len(df)
    )
    return df


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def run_enrich(df: pd.DataFrame, geo_df: pd.DataFrame) -> pd.DataFrame:
    """Run the full feature-enrichment pipeline in sequence.

    Applies, in order:
    1. :func:`add_geo_features`      — lat/lng + distance_km
    2. :func:`add_temporal_features` — day_of_week, month
    3. :func:`add_seller_delay_rate` — seller_historical_delay_rate
    4. :func:`compute_cost_per_km`   — cost_per_km

    Parameters
    ----------
    df:
        Cleaned delivered-orders DataFrame from :func:`etl.clean.run_clean`.
    geo_df:
        Raw geolocation DataFrame.

    Returns
    -------
    pd.DataFrame
        Fully enriched DataFrame ready for :mod:`etl.load`.
    """
    import time  # local import avoids polluting module-level namespace

    t0 = time.perf_counter()
    logger.info("Starting enrichment pipeline: %d input rows.", len(df))

    df = add_geo_features(df, geo_df)
    df = add_temporal_features(df)
    df = add_seller_delay_rate(df)
    df = compute_cost_per_km(df)

    elapsed = time.perf_counter() - t0
    logger.info("Enrichment pipeline complete in %.2fs.", elapsed)
    return df

"""
ETL Step 1 — Raw CSV ingestion and row-level cleaning.

Responsibilities:
  - Load all 9 Olist CSVs with explicit dtypes to prevent silent type coercion.
  - Parse timestamp columns to UTC-aware datetime64.
  - Merge source tables into a single denormalised DataFrame of *delivered* orders.
  - Compute ``delay_days`` and ``is_late`` flags.

This module is intentionally free of database I/O; it is a pure transformation
layer operating on DataFrames so that it can be unit-tested without a live DB.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Expected CSV filenames (Olist dataset canonical names)
# ---------------------------------------------------------------------------
_EXPECTED_FILES: dict[str, dict[str, Any]] = {
    "olist_orders_dataset.csv": {
        "dtype": {
            "order_id": "string",
            "customer_id": "string",
            "order_status": "string",
        }
    },
    "olist_order_items_dataset.csv": {
        "dtype": {
            "order_id": "string",
            "order_item_id": "Int64",
            "product_id": "string",
            "seller_id": "string",
            "price": "float64",
            "freight_value": "float64",
        }
    },
    "olist_products_dataset.csv": {
        "dtype": {
            "product_id": "string",
            "product_category_name": "string",
        }
    },
    "olist_sellers_dataset.csv": {
        "dtype": {
            "seller_id": "string",
            "seller_zip_code_prefix": "string",
            "seller_city": "string",
            "seller_state": "string",
        }
    },
    "olist_customers_dataset.csv": {
        "dtype": {
            "customer_id": "string",
            "customer_zip_code_prefix": "string",
            "customer_city": "string",
            "customer_state": "string",
        }
    },
    "olist_geolocation_dataset.csv": {
        "dtype": {
            "geolocation_zip_code_prefix": "string",
            "geolocation_lat": "float64",
            "geolocation_lng": "float64",
            "geolocation_city": "string",
            "geolocation_state": "string",
        }
    },
    "olist_order_payments_dataset.csv": {
        "dtype": {
            "order_id": "string",
            "payment_sequential": "Int64",
            "payment_type": "string",
            "payment_installments": "Int64",
            "payment_value": "float64",
        }
    },
    "olist_order_reviews_dataset.csv": {
        "dtype": {
            "review_id": "string",
            "order_id": "string",
            "review_score": "Int64",
        }
    },
    "product_category_name_translation.csv": {
        "dtype": {
            "product_category_name": "string",
            "product_category_name_english": "string",
        }
    },
}

# Timestamp columns found in the orders CSV
_ORDER_TIMESTAMP_COLS: list[str] = [
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_raw_csvs(raw_path: str) -> dict[str, pd.DataFrame]:
    """Load all 9 Olist CSV files from *raw_path* into a keyed dictionary.

    Each CSV is read with its canonical ``dtype`` mapping to avoid silent
    coercion (e.g. numeric order IDs becoming floats) that would break joins.

    Parameters
    ----------
    raw_path:
        Filesystem path to the directory containing the 9 CSV files.

    Returns
    -------
    dict[str, pd.DataFrame]
        Keys are the canonical file stems (without ``.csv``), values are the
        loaded DataFrames.

    Raises
    ------
    FileNotFoundError
        If *raw_path* does not exist or any of the 9 expected files is absent.
    """
    data_dir = Path(raw_path)

    if not data_dir.is_dir():
        raise FileNotFoundError(
            f"Raw data directory not found: '{data_dir.resolve()}'. "
            "Download the Olist dataset and place the 9 CSVs there."
        )

    dfs: dict[str, pd.DataFrame] = {}

    for filename, read_opts in _EXPECTED_FILES.items():
        file_path = data_dir / filename
        if not file_path.exists():
            raise FileNotFoundError(
                f"Required CSV file is missing: '{file_path.resolve()}'. "
                f"Ensure the Olist dataset is fully extracted into '{data_dir}'."
            )

        stem = file_path.stem
        df = pd.read_csv(
            file_path,
            dtype=read_opts.get("dtype"),
            low_memory=False,
        )
        dfs[stem] = df
        logger.info(
            "Loaded CSV file",
            extra={"file": filename, "rows": len(df), "columns": len(df.columns)},
        )

    logger.info(
        "All %d CSV files loaded successfully from '%s'.",
        len(dfs),
        data_dir,
    )
    return dfs


def parse_timestamps(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Parse string timestamp columns to UTC-aware ``datetime64[ns, UTC]``.

    Uses ``errors='coerce'`` so malformed values become ``NaT`` rather than
    raising, preserving all rows.  The count of nullified values is logged per
    column for audit purposes.

    Parameters
    ----------
    df:
        DataFrame containing the columns to parse (mutated in-place via copy).
    cols:
        List of column names to convert. Columns absent from *df* are skipped
        with a warning.

    Returns
    -------
    pd.DataFrame
        A *copy* of *df* with the specified columns converted.
    """
    df = df.copy()

    for col in cols:
        if col not in df.columns:
            logger.warning(
                "Timestamp column '%s' not found in DataFrame — skipping.", col
            )
            continue

        before_nulls = df[col].isna().sum()
        df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)
        after_nulls = df[col].isna().sum()
        nullified = int(after_nulls - before_nulls)

        if nullified > 0:
            logger.warning(
                "Column '%s': %d value(s) could not be parsed and were set to NaT.",
                col,
                nullified,
            )
        else:
            logger.debug("Column '%s': all values parsed successfully.", col)

    return df


def clean_orders(dfs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Merge and clean the Olist source tables into a single denormalised DataFrame.

    The function performs the following steps in order:

    1. Drop rows where ``order_id`` is null in the orders table.
    2. Deduplicate orders on ``order_id`` (keep first occurrence).
    3. Parse all timestamp columns to UTC-aware datetime64.
    4. Keep *all* statuses in a copy (orders_all) — returned by the caller.
    5. Filter to ``order_status == 'delivered'`` for the main pipeline.
    6. Merge: orders → order_items (first item per order) → products →
       product_category_name_translation → sellers → customers → payments
       (summed payment_value per order) → reviews (max score per order).
    7. Cast financials, fill nulls, rename columns.
    8. Compute ``delay_days`` and ``is_late``.

    Parameters
    ----------
    dfs:
        Dictionary produced by :func:`load_raw_csvs`.

    Returns
    -------
    pd.DataFrame
        Denormalised DataFrame containing only *delivered* orders, enriched
        with all available features.

    Notes
    -----
    The caller is responsible for also passing the *all-statuses* DataFrame out
    of the pipeline.  This function returns only the delivered slice; the
    orchestrator :func:`run_clean` returns both.
    """
    orders = dfs["olist_orders_dataset"].copy()
    items = dfs["olist_order_items_dataset"].copy()
    products = dfs["olist_products_dataset"].copy()
    translations = dfs["product_category_name_translation"].copy()
    sellers = dfs["olist_sellers_dataset"].copy()
    customers = dfs["olist_customers_dataset"].copy()
    payments = dfs["olist_order_payments_dataset"].copy()
    reviews = dfs["olist_order_reviews_dataset"].copy()

    # ------------------------------------------------------------------
    # 1. Drop null order_ids
    # ------------------------------------------------------------------
    null_order_ids = orders["order_id"].isna().sum()
    if null_order_ids:
        logger.warning("Dropping %d rows with null order_id.", null_order_ids)
        orders = orders.dropna(subset=["order_id"])

    # ------------------------------------------------------------------
    # 2. Deduplicate
    # ------------------------------------------------------------------
    before_dedup = len(orders)
    orders = orders.drop_duplicates(subset=["order_id"], keep="first")
    removed = before_dedup - len(orders)
    if removed:
        logger.warning(
            "Deduplicated orders on order_id: removed %d duplicate row(s).", removed
        )

    # ------------------------------------------------------------------
    # 3. Parse timestamps
    # ------------------------------------------------------------------
    orders = parse_timestamps(orders, _ORDER_TIMESTAMP_COLS)

    # ------------------------------------------------------------------
    # 4. Preserve all-statuses snapshot before filtering
    # ------------------------------------------------------------------
    # The caller (run_clean) uses this to compute seller_delay_rate across
    # all delivered orders without touching the main DataFrame.
    # We signal it via a module-level variable written by run_clean.

    # ------------------------------------------------------------------
    # 5. Filter to delivered orders
    # ------------------------------------------------------------------
    before_filter = len(orders)
    orders = orders[orders["order_status"] == "delivered"].copy()
    logger.info(
        "Filtered to delivered orders: %d → %d rows (%.1f%% retained).",
        before_filter,
        len(orders),
        100 * len(orders) / max(before_filter, 1),
    )

    # ------------------------------------------------------------------
    # 6. Build first-item-per-order from order_items
    # ------------------------------------------------------------------
    # Keep item 1 to get seller / product / price for single-product heuristic.
    items_first = (
        items.sort_values("order_item_id")
        .groupby("order_id", as_index=False)
        .first()
    )

    # Aggregate payment_value per order (sum across payment types)
    payments_agg = (
        payments.groupby("order_id", as_index=False)["payment_value"]
        .sum()
        .rename(columns={"payment_value": "payment_value"})
    )

    # Keep highest review score per order (idempotent for single reviews)
    reviews_agg = (
        reviews.groupby("order_id", as_index=False)["review_score"]
        .max()
    )

    # English category names
    products = products.merge(
        translations,
        on="product_category_name",
        how="left",
    )

    # ------------------------------------------------------------------
    # 7. Merge pipeline
    # ------------------------------------------------------------------
    df = (
        orders
        .merge(items_first[["order_id", "product_id", "seller_id", "price", "freight_value"]], on="order_id", how="left")
        .merge(products[["product_id", "product_category_name_english"]], on="product_id", how="left")
        .merge(sellers[["seller_id", "seller_zip_code_prefix", "seller_state"]], on="seller_id", how="left")
        .merge(customers[["customer_id", "customer_zip_code_prefix", "customer_state"]], on="customer_id", how="left")
        .merge(payments_agg, on="order_id", how="left")
        .merge(reviews_agg, on="order_id", how="left")
    )

    # ------------------------------------------------------------------
    # 8. Clean and cast
    # ------------------------------------------------------------------
    df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0.0)
    df["freight_value"] = pd.to_numeric(df["freight_value"], errors="coerce").fillna(0.0)

    # Rename for ORM alignment
    df = df.rename(
        columns={
            "order_purchase_timestamp": "purchase_timestamp",
            "order_delivered_customer_date": "delivered_timestamp",
            "order_estimated_delivery_date": "estimated_delivery",
            "product_category_name_english": "category_name",
        }
    )

    # ------------------------------------------------------------------
    # 9. Delay metrics
    # ------------------------------------------------------------------
    df["delay_days"] = (
        (df["delivered_timestamp"] - df["estimated_delivery"])
        .dt.total_seconds()
        .div(86_400)
    )
    df["is_late"] = df["delay_days"] > 0

    logger.info(
        "clean_orders complete: %d delivered rows, %.1f%% late.",
        len(df),
        100 * df["is_late"].mean(),
    )
    return df


def run_clean(raw_path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Orchestrate CSV loading, parsing, and cleaning.

    Parameters
    ----------
    raw_path:
        Path to the directory containing the 9 raw Olist CSVs.

    Returns
    -------
    tuple[pd.DataFrame, pd.DataFrame]
        ``(df_delivered, df_all)`` where:
        - ``df_delivered`` — cleaned DataFrame of delivered orders (enrichment input)
        - ``df_all``       — full orders DataFrame (all statuses, for seller stats)
    """
    t0 = time.perf_counter()
    logger.info("Starting clean pipeline from raw_path='%s'.", raw_path)

    dfs = load_raw_csvs(raw_path)

    # Build the all-statuses DataFrame before clean_orders filters it
    orders_raw = dfs["olist_orders_dataset"].copy()
    null_ids = orders_raw["order_id"].isna().sum()
    if null_ids:
        orders_raw = orders_raw.dropna(subset=["order_id"])
    orders_raw = orders_raw.drop_duplicates(subset=["order_id"], keep="first")
    orders_raw = parse_timestamps(orders_raw, _ORDER_TIMESTAMP_COLS)

    # Items joined to orders_all for seller_delay_rate computation
    items = dfs["olist_order_items_dataset"].copy()
    items_first = (
        items.sort_values("order_item_id")
        .groupby("order_id", as_index=False)
        .first()
    )
    df_all = orders_raw.merge(
        items_first[["order_id", "seller_id"]], on="order_id", how="left"
    )
    df_all = df_all.rename(
        columns={
            "order_delivered_customer_date": "delivered_timestamp",
            "order_estimated_delivery_date": "estimated_delivery",
        }
    )
    df_all["delay_days"] = (
        (df_all["delivered_timestamp"] - df_all["estimated_delivery"])
        .dt.total_seconds()
        .div(86_400)
    )
    df_all["is_late"] = df_all["delay_days"] > 0

    df_delivered = clean_orders(dfs)

    elapsed = time.perf_counter() - t0
    logger.info(
        "Clean pipeline finished in %.2fs — delivered=%d, all=%d.",
        elapsed,
        len(df_delivered),
        len(df_all),
    )
    return df_delivered, df_all

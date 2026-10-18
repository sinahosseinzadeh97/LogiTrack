"""Read the Olist CSVs (plain or gzipped) and check they have the columns we need."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# file stem -> columns the pipeline reads
TABLES: dict[str, list[str]] = {
    "olist_orders_dataset": [
        "order_id",
        "customer_id",
        "order_status",
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ],
    "olist_order_items_dataset": [
        "order_id",
        "order_item_id",
        "product_id",
        "seller_id",
        "price",
        "freight_value",
    ],
    "olist_products_dataset": ["product_id", "product_category_name", "product_weight_g"],
    "product_category_name_translation": [
        "product_category_name",
        "product_category_name_english",
    ],
    "olist_customers_dataset": ["customer_id", "customer_zip_code_prefix", "customer_state"],
    "olist_sellers_dataset": ["seller_id", "seller_zip_code_prefix", "seller_state"],
    "olist_geolocation_dataset": [
        "geolocation_zip_code_prefix",
        "geolocation_lat",
        "geolocation_lng",
    ],
    "olist_order_reviews_dataset": ["order_id", "review_score"],
}

# Zip prefixes are 5-digit strings with leading zeros; never parse them as numbers.
_STRING_COLS = {
    "customer_zip_code_prefix",
    "seller_zip_code_prefix",
    "geolocation_zip_code_prefix",
}


def _find(data_dir: Path, stem: str) -> Path:
    for suffix in (".csv", ".csv.gz"):
        path = data_dir / f"{stem}{suffix}"
        if path.exists():
            return path
    raise FileNotFoundError(f"Missing {stem}.csv(.gz) in {data_dir.resolve()}")


def read_olist(data_dir: Path) -> dict[str, pd.DataFrame]:
    tables: dict[str, pd.DataFrame] = {}
    for stem, columns in TABLES.items():
        path = _find(data_dir, stem)
        header = pd.read_csv(path, nrows=0).columns
        missing = set(columns) - set(header)
        if missing:
            raise ValueError(f"{path.name} is missing columns: {sorted(missing)}")
        dtype = {c: "string" for c in columns if c in _STRING_COLS}
        tables[stem] = pd.read_csv(path, usecols=columns, dtype=dtype)
        logger.info("read %s: %d rows", path.name, len(tables[stem]))
    return tables

"""Join the raw Olist tables into one row per order, with outcomes and geo distance."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

EARTH_RADIUS_KM = 6371.0
# Olist's geolocation table has a few points far outside Brazil; ignore them.
BRAZIL_LAT = (-34.0, 6.0)
BRAZIL_LNG = (-74.0, -34.0)


def haversine_km(lat1: pd.Series, lng1: pd.Series, lat2: pd.Series, lng2: pd.Series) -> pd.Series:
    lat1, lng1, lat2, lng2 = (np.radians(s.astype(float)) for s in (lat1, lng1, lat2, lng2))
    a = (
        np.sin((lat2 - lat1) / 2) ** 2
        + np.cos(lat1) * np.cos(lat2) * np.sin((lng2 - lng1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


def _zip_coordinates(geo: pd.DataFrame) -> pd.DataFrame:
    """One (lat, lng) per zip prefix: the median of the in-Brazil points."""
    inside = geo["geolocation_lat"].between(*BRAZIL_LAT) & geo["geolocation_lng"].between(
        *BRAZIL_LNG
    )
    return (
        geo[inside]
        .groupby("geolocation_zip_code_prefix")[["geolocation_lat", "geolocation_lng"]]
        .median()
    )


def _items_per_order(items: pd.DataFrame, products: pd.DataFrame) -> pd.DataFrame:
    """Totals across all items; seller and category come from the first item."""
    items = items.merge(
        products[["product_id", "category", "product_weight_g"]], on="product_id", how="left"
    )
    totals = items.groupby("order_id").agg(
        n_items=("order_item_id", "size"),
        n_sellers=("seller_id", "nunique"),
        price=("price", "sum"),
        freight_value=("freight_value", "sum"),
        weight_g=("product_weight_g", lambda w: w.sum(min_count=1)),
    )
    first = items.sort_values("order_item_id").drop_duplicates("order_id").set_index("order_id")
    return totals.join(first[["seller_id", "category"]])


def build_orders(raw: dict[str, pd.DataFrame]) -> pd.DataFrame:
    orders = raw["olist_orders_dataset"].drop_duplicates("order_id")
    orders = orders.rename(
        columns={
            "order_purchase_timestamp": "purchase_ts",
            "order_approved_at": "approved_ts",
            "order_delivered_carrier_date": "carrier_ts",
            "order_delivered_customer_date": "delivered_ts",
            "order_estimated_delivery_date": "estimated_delivery",
        }
    )
    for col in ("purchase_ts", "approved_ts", "carrier_ts", "delivered_ts", "estimated_delivery"):
        orders[col] = pd.to_datetime(orders[col], errors="coerce")
    no_purchase = orders["purchase_ts"].isna()
    if no_purchase.any():
        logger.warning("dropping %d orders without a purchase timestamp", no_purchase.sum())
        orders = orders[~no_purchase]

    products = raw["olist_products_dataset"].merge(
        raw["product_category_name_translation"], on="product_category_name", how="left"
    )
    products["category"] = (
        products["product_category_name_english"]
        .fillna(products["product_category_name"])
        .fillna("unknown")
    )

    df = (
        orders.set_index("order_id")
        .join(_items_per_order(raw["olist_order_items_dataset"], products))
        .reset_index()
        .merge(raw["olist_customers_dataset"], on="customer_id", how="left")
        .merge(raw["olist_sellers_dataset"], on="seller_id", how="left")
        .merge(
            raw["olist_order_reviews_dataset"]
            .groupby("order_id", as_index=False)["review_score"]
            .mean(),
            on="order_id",
            how="left",
        )
    )

    coords = _zip_coordinates(raw["olist_geolocation_dataset"])
    seller_xy = coords.reindex(df["seller_zip_code_prefix"]).to_numpy()
    customer_xy = coords.reindex(df["customer_zip_code_prefix"]).to_numpy()
    df["distance_km"] = haversine_km(
        pd.Series(seller_xy[:, 0]),
        pd.Series(seller_xy[:, 1]),
        pd.Series(customer_xy[:, 0]),
        pd.Series(customer_xy[:, 1]),
    ).to_numpy()

    df["n_items"] = df["n_items"].fillna(0).astype(int)
    df["n_sellers"] = df["n_sellers"].fillna(0).astype(int)
    df["price"] = df["price"].fillna(0.0).round(2)
    df["freight_value"] = df["freight_value"].fillna(0.0).round(2)
    df["review_score"] = df["review_score"].round().astype("Int64")

    # Outcome. The promise is a calendar date, so "late" means delivered on a later day.
    delivered = (df["order_status"] == "delivered") & df["delivered_ts"].notna()
    delay = (df["delivered_ts"].dt.normalize() - df["estimated_delivery"].dt.normalize()).dt.days
    df["delay_days"] = delay.where(delivered).astype("Int64")
    df["is_late"] = (delay > 0).where(delivered).astype("boolean")

    df["promised_days"] = (df["estimated_delivery"] - df["purchase_ts"]).dt.total_seconds() / 86_400
    df["purchase_dow"] = df["purchase_ts"].dt.dayofweek
    df["estimated_delivery"] = df["estimated_delivery"].dt.date

    logger.info(
        "built %d orders (%d delivered, %.1f%% of them late)",
        len(df),
        delivered.sum(),
        100 * df["is_late"].mean(),
    )
    return df

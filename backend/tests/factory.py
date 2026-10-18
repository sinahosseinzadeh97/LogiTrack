"""Synthetic Olist-shaped tables, so tests never depend on the real dataset."""

from __future__ import annotations

import numpy as np
import pandas as pd

STATES = ["SP", "RJ", "MG", "BA"]
CATEGORIES = ["bed_bath_table", "health_beauty", "toys"]
ZIPS = {"SP": "01001", "RJ": "20001", "MG": "30001", "BA": "40001"}
COORDS = {
    "01001": (-23.55, -46.63),
    "20001": (-22.90, -43.20),
    "30001": (-19.92, -43.94),
    "40001": (-12.97, -38.50),
}


def make_raw(n_orders: int = 3_000, seed: int = 7) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    order_ids = [f"o{i:05d}" for i in range(n_orders)]
    customer_ids = [f"c{i:05d}" for i in range(n_orders)]
    seller_ids = [f"s{i}" for i in range(8)]
    seller_state = {s: STATES[i % len(STATES)] for i, s in enumerate(seller_ids)}

    purchase = pd.Timestamp("2017-01-01") + pd.to_timedelta(rng.uniform(0, 540, n_orders), unit="D")
    promised = rng.integers(10, 30, n_orders)
    customer_state = rng.choice(STATES, n_orders)
    # Lateness depends on the destination, so a model has something real to learn.
    extra = np.where(customer_state == "BA", 8, 0)
    transit = rng.integers(3, 25, n_orders) + extra
    status = rng.choice(["delivered", "shipped", "canceled"], n_orders, p=[0.94, 0.03, 0.03])
    delivered = pd.Series(purchase + pd.to_timedelta(transit, unit="D")).where(
        status == "delivered"
    )
    estimated = (purchase + pd.to_timedelta(promised, unit="D")).normalize()

    orders = pd.DataFrame(
        {
            "order_id": order_ids,
            "customer_id": customer_ids,
            "order_status": status,
            "order_purchase_timestamp": purchase.strftime("%Y-%m-%d %H:%M:%S"),
            "order_approved_at": purchase.strftime("%Y-%m-%d %H:%M:%S"),
            "order_delivered_carrier_date": None,
            "order_delivered_customer_date": delivered.dt.strftime("%Y-%m-%d %H:%M:%S"),
            "order_estimated_delivery_date": estimated.strftime("%Y-%m-%d %H:%M:%S"),
        }
    )
    sellers_of_order = rng.choice(seller_ids, n_orders)
    items = pd.DataFrame(
        {
            "order_id": order_ids,
            "order_item_id": 1,
            "product_id": rng.choice([f"p{i}" for i in range(len(CATEGORIES))], n_orders),
            "seller_id": sellers_of_order,
            "price": rng.uniform(10, 300, n_orders).round(2),
            "freight_value": rng.uniform(5, 40, n_orders).round(2),
        }
    )
    return {
        "olist_orders_dataset": orders,
        "olist_order_items_dataset": items,
        "olist_products_dataset": pd.DataFrame(
            {
                "product_id": [f"p{i}" for i in range(len(CATEGORIES))],
                "product_category_name": [f"pt_{c}" for c in CATEGORIES],
                "product_weight_g": [500.0, 250.0, 1200.0],
            }
        ),
        "product_category_name_translation": pd.DataFrame(
            {
                "product_category_name": [f"pt_{c}" for c in CATEGORIES],
                "product_category_name_english": CATEGORIES,
            }
        ),
        "olist_customers_dataset": pd.DataFrame(
            {
                "customer_id": customer_ids,
                "customer_zip_code_prefix": [ZIPS[s] for s in customer_state],
                "customer_state": customer_state,
            }
        ),
        "olist_sellers_dataset": pd.DataFrame(
            {
                "seller_id": seller_ids,
                "seller_zip_code_prefix": [ZIPS[seller_state[s]] for s in seller_ids],
                "seller_state": [seller_state[s] for s in seller_ids],
            }
        ),
        "olist_geolocation_dataset": pd.DataFrame(
            {
                "geolocation_zip_code_prefix": list(COORDS),
                "geolocation_lat": [c[0] for c in COORDS.values()],
                "geolocation_lng": [c[1] for c in COORDS.values()],
            }
        ),
        "olist_order_reviews_dataset": pd.DataFrame(
            {
                "order_id": order_ids,
                "review_score": rng.integers(1, 6, n_orders),
            }
        ),
    }

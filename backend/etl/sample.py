"""Write the small committed demo dataset: ``python -m etl.sample [--fraction 0.25]``.

Samples whole *sellers* (with every order they sold) rather than random orders,
so each sampled seller keeps its full history and the point-in-time seller
features stay meaningful. Writes gzipped CSVs to data/sample.
"""

from __future__ import annotations

import argparse
import logging

import numpy as np

from app.config import get_settings
from etl.extract import read_olist
from etl.run import SAMPLE_DIR

logger = logging.getLogger("etl.sample")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fraction", type=float, default=0.25)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

    raw = read_olist(get_settings().DATA_DIR)
    items = raw["olist_order_items_dataset"]
    sellers = items["seller_id"].drop_duplicates()
    rng = np.random.default_rng(args.seed)
    chosen = set(sellers[rng.random(len(sellers)) < args.fraction])

    order_ids = set(items.loc[items["seller_id"].isin(chosen), "order_id"])
    orders = raw["olist_orders_dataset"]
    orders = orders[orders["order_id"].isin(order_ids)]
    items = items[items["order_id"].isin(order_ids)]
    customers = raw["olist_customers_dataset"]
    customers = customers[customers["customer_id"].isin(orders["customer_id"])]
    sellers_df = raw["olist_sellers_dataset"]
    sellers_df = sellers_df[sellers_df["seller_id"].isin(items["seller_id"])]
    zips = set(customers["customer_zip_code_prefix"]) | set(sellers_df["seller_zip_code_prefix"])
    geo = raw["olist_geolocation_dataset"]
    geo = (
        geo[geo["geolocation_zip_code_prefix"].isin(zips)]
        .groupby("geolocation_zip_code_prefix", as_index=False)
        .median()  # one point per prefix keeps the file small; the ETL uses the median anyway
    )
    products = raw["olist_products_dataset"]

    tables = {
        "olist_orders_dataset": orders,
        "olist_order_items_dataset": items,
        "olist_products_dataset": products[products["product_id"].isin(items["product_id"])],
        "product_category_name_translation": raw["product_category_name_translation"],
        "olist_customers_dataset": customers,
        "olist_sellers_dataset": sellers_df,
        "olist_geolocation_dataset": geo,
        "olist_order_reviews_dataset": raw["olist_order_reviews_dataset"].pipe(
            lambda r: r[r["order_id"].isin(order_ids)]
        ),
    }
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    for stem, frame in tables.items():
        frame.to_csv(SAMPLE_DIR / f"{stem}.csv.gz", index=False)
    logger.info("wrote %d orders from %d sellers to %s", len(orders), len(chosen), SAMPLE_DIR)


if __name__ == "__main__":
    main()

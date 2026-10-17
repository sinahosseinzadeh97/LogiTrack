"""ETL entry point: ``python -m etl.run [--data-dir DIR] [--if-empty]``.

Without --data-dir it uses the full dataset in data/raw when present, otherwise
the committed sample in data/sample.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from sqlalchemy import create_engine, text

from app.config import BACKEND_ROOT, get_settings
from etl.extract import read_olist
from etl.features import add_point_in_time_features
from etl.load import load_shipments
from etl.transform import build_orders

logger = logging.getLogger("etl")
SAMPLE_DIR = BACKEND_ROOT.parent / "data" / "sample"


def default_data_dir() -> Path:
    raw = get_settings().DATA_DIR
    has_raw = any(raw.glob("olist_orders_dataset.csv*")) if raw.is_dir() else False
    return raw if has_raw else SAMPLE_DIR


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--if-empty", action="store_true", help="skip if shipments has rows")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

    engine = create_engine(get_settings().sync_database_url)
    if args.if_empty:
        with engine.connect() as conn:
            if conn.execute(text("SELECT EXISTS (SELECT 1 FROM shipments)")).scalar():
                logger.info("shipments already loaded; skipping ETL")
                return

    data_dir = args.data_dir or default_data_dir()
    started = time.perf_counter()
    logger.info("reading %s", data_dir)
    df = add_point_in_time_features(build_orders(read_olist(data_dir)))
    load_shipments(engine, df)
    logger.info("ETL finished in %.1fs", time.perf_counter() - started)


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError) as exc:
        logger.error("ETL failed: %s", exc)
        sys.exit(1)

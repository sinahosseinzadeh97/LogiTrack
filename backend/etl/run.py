"""
ETL pipeline entry-point.

Run as a module from the project root::

    python -m etl.run

The script reads configuration from the environment (via :mod:`app.config`),
executes the three-stage pipeline (clean → enrich → load), and exits with
code 0 on success or 1 on failure.

Environment variables required
-------------------------------
DATABASE_SYNC_URL : str
    Synchronous PostgreSQL DSN for the load step.
DATA_RAW_PATH : str
    Path to the directory containing the 9 Olist CSV files.

All other settings are loaded via :class:`app.config.Settings` and may be
supplied via a `.env` file in the working directory.
"""

from __future__ import annotations

import logging
import sys
import time

from app.config import get_settings
from etl.clean import run_clean
from etl.enrich import run_enrich
from etl.load import run_load

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)

logger = logging.getLogger(__name__)


def main() -> None:
    """Execute the full ETL pipeline: clean → enrich → load."""
    t_global = time.perf_counter()
    settings = get_settings()

    logger.info(
        "LogiTrack ETL starting — env=%s, raw_path=%s",
        settings.ENVIRONMENT,
        settings.DATA_RAW_PATH,
    )

    # ------------------------------------------------------------------
    # Stage 1: Clean
    # ------------------------------------------------------------------
    try:
        df_delivered, df_all = run_clean(settings.DATA_RAW_PATH)
    except FileNotFoundError as exc:
        logger.critical("Clean stage failed — %s", exc)
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        logger.critical("Unexpected error in clean stage: %s", exc, exc_info=True)
        sys.exit(1)

    # ------------------------------------------------------------------
    # Stage 2: Enrich
    # ------------------------------------------------------------------
    try:
        # geo_df is loaded separately since it is not part of the delivered slice
        from etl.clean import load_raw_csvs  # local import to avoid circular dep

        dfs = load_raw_csvs(settings.DATA_RAW_PATH)
        geo_df = dfs["olist_geolocation_dataset"]
        df_enriched = run_enrich(df_delivered, geo_df)
    except Exception as exc:  # noqa: BLE001
        logger.critical("Unexpected error in enrich stage: %s", exc, exc_info=True)
        sys.exit(1)

    # ------------------------------------------------------------------
    # Stage 3: Load
    # ------------------------------------------------------------------
    try:
        summary = run_load(df_enriched, df_all, settings.DATABASE_SYNC_URL)
    except Exception as exc:  # noqa: BLE001
        logger.critical("Unexpected error in load stage: %s", exc, exc_info=True)
        sys.exit(1)

    elapsed = time.perf_counter() - t_global
    logger.info(
        "ETL pipeline complete in %.1fs — shipments=%d, kpi_days=%d, sellers=%d.",
        elapsed,
        summary["shipments"],
        summary["kpi_days"],
        summary["sellers"],
    )


if __name__ == "__main__":
    main()

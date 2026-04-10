"""
ETL Step 3 — Database load layer.

Responsibilities:
  - Upsert enriched shipment rows into ``shipments`` using PostgreSQL
    ``INSERT … ON CONFLICT DO UPDATE`` to make all runs idempotent.
  - Compute and upsert daily KPI aggregates into ``kpi_daily``.
  - Compute and upsert per-seller statistics into ``seller_stats``.

All operations use the **synchronous** SQLAlchemy engine because bulk ETL
workloads do not benefit from async I/O and the synchronous driver (psycopg2)
handles large batch inserts more efficiently in this context.

IntegrityErrors are caught and logged at the batch level; a single bad batch
does not abort the entire load.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.models.shipment import KpiDaily, SellerStats, Shipment

logger = logging.getLogger(__name__)

_BATCH_SIZE = 1_000

# Columns in the enriched DataFrame that map directly to ``shipments`` columns.
_SHIPMENT_COLS: list[str] = [
    "order_id",
    "customer_id",
    "seller_id",
    "product_id",
    "category_name",
    "seller_state",
    "customer_state",
    "purchase_timestamp",
    "delivered_timestamp",
    "estimated_delivery",
    "price",
    "freight_value",
    "payment_value",
    "delay_days",
    "is_late",
    "distance_km",
    "cost_per_km",
    "day_of_week",
    "month",
    "seller_lat",
    "seller_lng",
    "customer_lat",
    "customer_lng",
    "seller_historical_delay_rate",
    "review_score",
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_engine(db_url: str) -> Engine:
    """Create a synchronous SQLAlchemy engine from *db_url*.

    Parameters
    ----------
    db_url:
        PostgreSQL connection string in ``postgresql+psycopg2://…`` format.

    Returns
    -------
    Engine
        Configured engine with pool pre-ping enabled.
    """
    return create_engine(db_url, pool_pre_ping=True, pool_size=5, max_overflow=10)


def _df_to_records(df: pd.DataFrame, cols: list[str]) -> list[dict[str, Any]]:
    """Extract *cols* from *df* into a list of plain dicts for SQLAlchemy Core.

    Pandas NA values are converted to ``None`` so psycopg2 maps them to SQL
    NULL instead of raising a type error.

    Parameters
    ----------
    df:
        Source DataFrame.
    cols:
        Ordered list of column names to extract.  Missing columns are silently
        filled with ``None`` to avoid KeyErrors when optional columns are absent.

    Returns
    -------
    list[dict[str, Any]]
        One dict per row, keys matching the column names.
    """
    available = [c for c in cols if c in df.columns]
    missing = set(cols) - set(available)
    if missing:
        logger.warning(
            "Columns absent from DataFrame and defaulting to None: %s", sorted(missing)
        )

    records: list[dict[str, Any]] = []
    for row in df[available].itertuples(index=False):
        record: dict[str, Any] = {}
        for col, val in zip(available, row, strict=True):
            # Convert pandas NA / NaN scalars to Python None
            if pd.isna(val):
                record[col] = None
            elif hasattr(val, 'item'):
                # Convert numpy scalar (int8, int64, float32, bool_, …) to Python native
                record[col] = val.item()
            else:
                record[col] = val
        for col in missing:
            record[col] = None
        records.append(record)
    return records


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def upsert_shipments(engine: Engine, df: pd.DataFrame) -> int:
    """Upsert enriched shipment rows into the ``shipments`` table.

    Uses PostgreSQL ``INSERT … ON CONFLICT (order_id) DO UPDATE`` so the
    operation is safe to re-run.  Rows are inserted in batches of
    ``_BATCH_SIZE`` to bound per-transaction memory usage.

    Parameters
    ----------
    engine:
        Synchronous SQLAlchemy engine pointing at the target PostgreSQL DB.
    df:
        Enriched DataFrame produced by :func:`etl.enrich.run_enrich`.

    Returns
    -------
    int
        Total number of rows upserted (inserted + updated).

    Raises
    ------
    SQLAlchemyError
        Re-raised after logging if a non-integrity database error occurs that
        prevents the overall load from completing.
    """
    if df.empty:
        logger.warning("upsert_shipments called with empty DataFrame — nothing to do.")
        return 0

    records = _df_to_records(df, _SHIPMENT_COLS)
    total_upserted = 0
    table = Shipment.__table__

    # Columns that may be updated on conflict (all except the conflict target)
    update_cols = {c: text(f"EXCLUDED.{c}") for c in _SHIPMENT_COLS if c != "order_id"}

    with engine.begin() as conn:
        for batch_start in range(0, len(records), _BATCH_SIZE):
            batch = records[batch_start : batch_start + _BATCH_SIZE]
            try:
                stmt = (
                    insert(table)
                    .values(batch)
                    .on_conflict_do_update(
                        index_elements=["order_id"],
                        set_=update_cols,
                    )
                )
                conn.execute(stmt)
                total_upserted += len(batch)
                logger.debug(
                    "Upserted batch %d–%d (%d rows).",
                    batch_start,
                    batch_start + len(batch) - 1,
                    len(batch),
                )
            except IntegrityError as exc:
                logger.error(
                    "IntegrityError on batch %d–%d — batch skipped: %s",
                    batch_start,
                    batch_start + len(batch) - 1,
                    exc.orig,
                )
                # Roll back only the current batch statement; the connection
                # remains open for subsequent batches.
                conn.rollback()

    logger.info("upsert_shipments complete: %d rows upserted.", total_upserted)
    return total_upserted


def compute_and_load_kpi_daily(engine: Engine, df: pd.DataFrame) -> None:
    """Aggregate delivered orders by date and upsert into ``kpi_daily``.

    KPIs computed per calendar date:
    - ``otif_rate``             — fraction of orders delivered on time (``~is_late``)
    - ``avg_delay_days``        — mean delay (positive = late, negative = early)
    - ``fulfillment_rate``      — fraction of all orders with ``delivered_timestamp``
                                  not null (approximated from delivered slice as 1.0)
    - ``avg_cost_per_shipment`` — mean ``freight_value``
    - ``total_shipments``       — row count per date

    Parameters
    ----------
    engine:
        Synchronous SQLAlchemy engine.
    df:
        Enriched delivered-orders DataFrame; must contain ``purchase_timestamp``,
        ``is_late``, ``delay_days``, and ``freight_value``.
    """
    if df.empty:
        logger.warning("compute_and_load_kpi_daily: empty DataFrame — skipping.")
        return

    work = df.copy()
    work["_date"] = pd.to_datetime(work["purchase_timestamp"], utc=True).dt.date

    daily = (
        work.groupby("_date", as_index=False)
        .agg(
            total_shipments=("order_id", "count"),
            otif_rate=("is_late", lambda x: float((~x.astype(bool)).mean())),
            avg_delay_days=("delay_days", "mean"),
            avg_cost_per_shipment=("freight_value", "mean"),
        )
        .rename(columns={"_date": "date"})
    )
    # fulfillment_rate: all rows in the delivered slice are fulfilled
    daily["fulfillment_rate"] = 1.0
    daily["flagged_count"] = 0

    table = KpiDaily.__table__
    update_cols = {
        "otif_rate": text("EXCLUDED.otif_rate"),
        "avg_delay_days": text("EXCLUDED.avg_delay_days"),
        "fulfillment_rate": text("EXCLUDED.fulfillment_rate"),
        "avg_cost_per_shipment": text("EXCLUDED.avg_cost_per_shipment"),
        "total_shipments": text("EXCLUDED.total_shipments"),
        "flagged_count": text("EXCLUDED.flagged_count"),
        "updated_at": text("NOW()"),
    }

    records = daily.to_dict(orient="records")

    with engine.begin() as conn:
        try:
            stmt = (
                insert(table)
                .values(records)
                .on_conflict_do_update(index_elements=["date"], set_=update_cols)
            )
            conn.execute(stmt)
            logger.info(
                "compute_and_load_kpi_daily: upserted %d date rows.", len(records)
            )
        except SQLAlchemyError as exc:
            logger.error("Failed to upsert kpi_daily: %s", exc)
            raise


def compute_and_load_seller_stats(engine: Engine, df: pd.DataFrame) -> None:
    """Aggregate per-seller statistics and upsert into ``seller_stats``.

    Statistics computed per ``seller_id``:
    - ``total_orders``  — count of all orders by that seller
    - ``delay_rate``    — fraction of orders where ``is_late`` is True
    - ``avg_delay_days`` — mean ``delay_days``
    - ``avg_cost``      — mean ``freight_value``

    Parameters
    ----------
    engine:
        Synchronous SQLAlchemy engine.
    df:
        Enriched delivered-orders DataFrame.
    """
    if df.empty:
        logger.warning("compute_and_load_seller_stats: empty DataFrame — skipping.")
        return

    stats = (
        df.groupby("seller_id", as_index=False)
        .agg(
            seller_state=("seller_state", "first"),
            total_orders=("order_id", "count"),
            delay_rate=("is_late", "mean"),
            avg_delay_days=("delay_days", "mean"),
            avg_cost=("freight_value", "mean"),
        )
    )

    # Replace pandas NA with None
    stats = stats.where(pd.notna(stats), other=None)
    records = stats.to_dict(orient="records")

    table = SellerStats.__table__
    update_cols = {
        "seller_state": text("EXCLUDED.seller_state"),
        "total_orders": text("EXCLUDED.total_orders"),
        "delay_rate": text("EXCLUDED.delay_rate"),
        "avg_delay_days": text("EXCLUDED.avg_delay_days"),
        "avg_cost": text("EXCLUDED.avg_cost"),
        "updated_at": text("NOW()"),
    }

    with engine.begin() as conn:
        for batch_start in range(0, len(records), _BATCH_SIZE):
            batch = records[batch_start : batch_start + _BATCH_SIZE]
            try:
                stmt = (
                    insert(table)
                    .values(batch)
                    .on_conflict_do_update(
                        index_elements=["seller_id"], set_=update_cols
                    )
                )
                conn.execute(stmt)
            except IntegrityError as exc:
                logger.error(
                    "IntegrityError upserting seller_stats batch: %s", exc.orig
                )

    logger.info(
        "compute_and_load_seller_stats: upserted %d seller rows.", len(records)
    )


def run_load(
    df_delivered: pd.DataFrame,
    df_all: pd.DataFrame,
    db_url: str,
) -> dict[str, int]:
    """Orchestrate all three load steps and return a summary.

    Parameters
    ----------
    df_delivered:
        Enriched delivered-orders DataFrame from :func:`etl.enrich.run_enrich`.
    df_all:
        All-statuses orders DataFrame from :func:`etl.clean.run_clean`
        (used for seller stats when delivered slice may be smaller).
    db_url:
        Synchronous PostgreSQL DSN (``postgresql+psycopg2://…``).

    Returns
    -------
    dict[str, int]
        Summary counts: ``{"shipments": n, "kpi_days": n, "sellers": n}``.
    """
    t0 = time.perf_counter()
    logger.info("Starting load pipeline — db_url='%s'.", db_url)

    engine = _get_engine(db_url)

    shipments_count = upsert_shipments(engine, df_delivered)

    compute_and_load_kpi_daily(engine, df_delivered)
    kpi_days_count = int(
        pd.to_datetime(df_delivered["purchase_timestamp"], utc=True).dt.date.nunique()
    )

    # Use df_delivered for seller stats (enriched columns required)
    compute_and_load_seller_stats(engine, df_delivered)
    sellers_count = int(df_delivered["seller_id"].nunique()) if not df_delivered.empty else 0

    engine.dispose()

    elapsed = time.perf_counter() - t0
    summary = {
        "shipments": shipments_count,
        "kpi_days": kpi_days_count,
        "sellers": sellers_count,
    }
    logger.info(
        "Load pipeline finished in %.2fs — %s.",
        elapsed,
        ", ".join(f"{k}={v}" for k, v in summary.items()),
    )
    return summary

"""Replace the shipments table in one transaction (TRUNCATE + COPY).

A full refresh is simpler than upserts for a batch dataset and is idempotent:
readers keep seeing the old rows until the transaction commits.
"""

from __future__ import annotations

import io
import logging

import pandas as pd
from sqlalchemy import Engine, text

from app.models import Shipment

logger = logging.getLogger(__name__)

# Everything except the model score, which ml.train writes afterwards.
COLUMNS = [c.name for c in Shipment.__table__.columns if c.name != "delay_probability"]


def load_shipments(engine: Engine, df: pd.DataFrame) -> int:
    missing = set(COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame is missing columns: {sorted(missing)}")

    buffer = io.StringIO()
    df[COLUMNS].to_csv(buffer, index=False, header=False, na_rep="")
    buffer.seek(0)

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE shipments"))
        cursor = conn.connection.dbapi_connection.cursor()
        cursor.copy_expert(
            f"COPY shipments ({', '.join(COLUMNS)}) FROM STDIN WITH (FORMAT csv, NULL '')",
            buffer,
        )
    logger.info("loaded %d shipments", len(df))
    return len(df)

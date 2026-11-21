"""Transform raw Bronze JSON records into validated Silver OHLCV rows."""
from __future__ import annotations

import logging

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

try:
    from scripts.config import DatabaseConfig
except ModuleNotFoundError:
    from config import DatabaseConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def transform() -> int:
    config = DatabaseConfig.from_env()
    with psycopg2.connect(**config.psycopg2_kwargs) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT ticker, market_date, data, ingestion_timestamp
                FROM bronze.stock_raw
                ORDER BY market_date, ticker
            """)
            source = cur.fetchall()

    if not source:
        logger.warning("Bronze contains no records; Silver was not changed.")
        return 0

    rows = []
    for ticker, market_date, payload, ingestion_ts in source:
        payload = payload if isinstance(payload, dict) else {}
        try:
            values = [
                float(payload[name]) for name in ("Open", "High", "Low", "Close")
            ]
            volume = int(float(payload["Volume"]))
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
        open_price, high, low, close = values
        if (min(values) <= 0 or volume < 0 or high < max(open_price, close, low)
                or low > min(open_price, close, high)):
            continue
        rows.append((
            market_date, ticker, open_price, high, low, close,
            volume, ingestion_ts,
        ))

    if not rows:
        raise RuntimeError("No valid Bronze records found; refusing to replace Silver.")

    upsert = """
        INSERT INTO silver.stock_clean
            (date, ticker, open, high, low, close, volume, ingestion_timestamp)
        VALUES %s
        ON CONFLICT (date, ticker) DO UPDATE SET
            open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low,
            close = EXCLUDED.close, volume = EXCLUDED.volume,
            ingestion_timestamp = EXCLUDED.ingestion_timestamp
    """
    with psycopg2.connect(**config.psycopg2_kwargs) as conn:
        with conn.cursor() as cur:
            execute_values(cur, upsert, rows, page_size=1000)
    logger.info("Upserted %d valid Silver rows", len(rows))
    return len(rows)


if __name__ == "__main__":
    transform()

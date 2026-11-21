"""Build analytical Gold metrics from Silver using PostgreSQL window functions."""
from __future__ import annotations

import logging

import psycopg2

try:
    from scripts.config import DatabaseConfig
except ModuleNotFoundError:
    from config import DatabaseConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

GOLD_SQL = """
    INSERT INTO gold.stock_metrics
        (date, ticker, close, daily_return_pct, sma_7, sma_30, volume)
    SELECT
        date, ticker, close,
        ROUND((close / NULLIF(LAG(close) OVER w, 0) - 1)::numeric * 100, 2),
        ROUND(AVG(close) OVER (
            PARTITION BY ticker ORDER BY date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        )::numeric, 2),
        ROUND(AVG(close) OVER (
            PARTITION BY ticker ORDER BY date
            ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
        )::numeric, 2),
        volume
    FROM silver.stock_clean
    WINDOW w AS (PARTITION BY ticker ORDER BY date)
    ON CONFLICT (date, ticker) DO UPDATE SET
        close = EXCLUDED.close,
        daily_return_pct = EXCLUDED.daily_return_pct,
        sma_7 = EXCLUDED.sma_7,
        sma_30 = EXCLUDED.sma_30,
        volume = EXCLUDED.volume
"""


def build_gold() -> int:
    config = DatabaseConfig.from_env()
    with psycopg2.connect(**config.psycopg2_kwargs) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM silver.stock_clean")
            source_count = cur.fetchone()[0]
            if source_count == 0:
                raise RuntimeError("Silver is empty; refusing to build Gold.")
            cur.execute(GOLD_SQL)
            cur.execute("SELECT COUNT(*) FROM gold.stock_metrics")
            gold_count = cur.fetchone()[0]
    logger.info("Gold contains %d rows after processing %d Silver rows",
                gold_count, source_count)
    return gold_count


if __name__ == "__main__":
    build_gold()

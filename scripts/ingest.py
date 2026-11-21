"""Fetch daily OHLCV data and append raw ticker/date records to Bronze."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import pandas as pd
import psycopg2
import yfinance as yf
from psycopg2.extras import execute_values

try:
    from scripts.config import DatabaseConfig
    from scripts.validation import validate_market_frame
except ModuleNotFoundError:  # supports: python scripts/ingest.py
    from config import DatabaseConfig
    from validation import validate_market_frame

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

TICKERS = [
    "RELIANCE.NS", "HDFCBANK.NS", "BHARTIARTL.NS", "SBIN.NS",
    "ICICIBANK.NS", "TCS.NS", "BAJFINANCE.NS", "LT.NS",
    "HINDUNILVR.NS", "INFY.NS", "SUNPHARMA.NS", "MARUTI.NS",
    "AXISBANK.NS", "NTPC.NS", "TITAN.NS", "ITC.NS", "ONGC.NS",
]


def download_ticker(ticker: str, period: str = "5y") -> pd.DataFrame:
    """Download one ticker so each source record has an explicit identity."""
    frame = yf.download(
        ticker, period=period, interval="1d",
        auto_adjust=False, progress=False, threads=False,
    )
    if frame.empty:
        logger.warning("No rows returned for %s", ticker)
        return pd.DataFrame()
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)
    frame = frame.reset_index()
    frame["ticker"] = ticker
    return validate_market_frame(frame)


def ingest(period: str = "5y") -> int:
    config = DatabaseConfig.from_env()
    ingestion_ts = datetime.now(timezone.utc)
    rows = []
    for ticker in TICKERS:
        frame = download_ticker(ticker, period)
        for record in frame.to_dict(orient="records"):
            date_value = pd.Timestamp(record.pop("Date")).date().isoformat()
            payload = {
                key: (value.isoformat() if hasattr(value, "isoformat") else
                      (None if pd.isna(value) else value))
                for key, value in record.items()
            }
            rows.append((ticker, date_value, ingestion_ts, json.dumps(payload)))

    if not rows:
        raise RuntimeError("Ingestion produced no valid market records.")

    sql = """
        INSERT INTO bronze.stock_raw
            (ticker, market_date, ingestion_timestamp, data)
        VALUES %s
        ON CONFLICT (ticker, market_date) DO UPDATE SET
            ingestion_timestamp = EXCLUDED.ingestion_timestamp,
            data = EXCLUDED.data
    """
    with psycopg2.connect(**config.psycopg2_kwargs) as conn:
        with conn.cursor() as cur:
            execute_values(cur, sql, rows, page_size=1000)
    logger.info("Ingested %d ticker-date records", len(rows))
    return len(rows)


if __name__ == "__main__":
    ingest()

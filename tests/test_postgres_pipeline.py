"""PostgreSQL integration coverage for the Bronze -> Silver -> Gold path."""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from pathlib import Path

import psycopg2
import pytest

from scripts.cleaning import transform
from scripts.config import DatabaseConfig
from scripts.gol_metrics import build_gold

pytestmark = pytest.mark.skipif(
    os.getenv("STOCKFLOW_TEST_POSTGRES") != "1",
    reason="Set STOCKFLOW_TEST_POSTGRES=1 to run destructive tests in a disposable DB",
)


def test_bronze_silver_gold_pipeline_is_repeatable():
    """Run against a disposable PostgreSQL database; schemas are reset first."""
    config = DatabaseConfig.from_env()
    root = Path(__file__).resolve().parents[1]

    with psycopg2.connect(**config.psycopg2_kwargs) as conn:
        with conn.cursor() as cur:
            cur.execute("DROP SCHEMA IF EXISTS bronze CASCADE")
            cur.execute("DROP SCHEMA IF EXISTS silver CASCADE")
            cur.execute("DROP SCHEMA IF EXISTS gold CASCADE")
            for schema_file in (
                "Bronze_schema.sql",
                "Silver_Schema.sql",
                "Gold_schema.sql",
            ):
                cur.execute((root / "sql" / schema_file).read_text(encoding="utf-8"))

            payloads = [
                (date(2024, 1, 2), {
                    "Open": 100, "High": 105, "Low": 95,
                    "Close": 100, "Volume": 1000,
                }),
                (date(2024, 1, 3), {
                    "Open": 101, "High": 112, "Low": 99,
                    "Close": 110, "Volume": 1200,
                }),
            ]
            cur.executemany(
                """
                INSERT INTO bronze.stock_raw_daily
                    (ticker, market_date, ingestion_timestamp, data)
                VALUES (%s, %s, %s, %s::jsonb)
                """,
                [
                    ("TEST.NS", market_date, datetime.now(timezone.utc),
                     json.dumps(payload))
                    for market_date, payload in payloads
                ],
            )

    assert transform() == 2
    assert transform() == 2  # Same ticker/date keys are updated, not duplicated.
    assert build_gold() == 2
    assert build_gold() == 2

    with psycopg2.connect(**config.psycopg2_kwargs) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM silver.stock_clean")
            assert cur.fetchone()[0] == 2
            cur.execute("SELECT COUNT(*) FROM gold.stock_metrics")
            assert cur.fetchone()[0] == 2
            cur.execute(
                """
                SELECT daily_return_pct, sma_7
                FROM gold.stock_metrics
                WHERE ticker = %s AND date = %s
                """,
                ("TEST.NS", date(2024, 1, 3)),
            )
            daily_return, sma_7 = cur.fetchone()

    assert float(daily_return) == 10.0
    assert float(sma_7) == 105.0

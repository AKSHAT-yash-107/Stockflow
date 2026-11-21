# Stockflow — Stock Market Data Warehouse & Analytics Platform

Stockflow is a batch data-engineering project that ingests historical NSE equity data, preserves source records in a Bronze layer, validates and normalizes OHLCV records into Silver, and builds analytical Gold metrics in PostgreSQL.

## Architecture

```text
Yahoo Finance
     |
     v
Python ingestion (one ticker at a time)
     |
     v
Bronze: raw JSONB records (ticker/date grain)
     |
     v
OHLCV validation + normalization
     |
     v
Silver: one validated row per ticker/date
     |
     v
PostgreSQL window-function transformations
     |
     v
Gold: daily returns + rolling averages
     |
     v
Power BI
```

## Implemented engineering capabilities

- Python ingestion using yfinance.
- PostgreSQL Bronze/Silver/Gold layers.
- JSONB raw-record preservation.
- OHLCV validation (positive finite prices, consistent high/low, non-negative integer volume).
- Idempotent upserts keyed by ticker and market date.
- Gold daily returns and 7-/30-observation simple moving averages using PostgreSQL window functions.
- Environment-based database configuration; credentials are not stored in source code.
- Unit tests for validation and transformation invariants.

## Dataset scope

The ingestion script currently defines 17 NSE tickers and requests a five-year daily history. The actual row count and date coverage depend on the source response at run time.

## Technology

Python, PostgreSQL, pandas, NumPy, yfinance, psycopg2, python-dotenv, pytest, Power BI.

## Repository layout

```text
scripts/
  config.py          # environment-backed database config
  ingest.py          # source ingestion -> Bronze
  validation.py      # reusable OHLCV checks
  cleaning.py        # Bronze -> Silver
  gol_metrics.py     # Silver -> Gold
sql/
  Bronze_schema.sql
  Silver_Schema.sql
  Gold_schema.sql
  gold_analytical_deductions.sql
tests/
  test_validation.py
  test_metrics_sql.py
docs/
  architecture.png
.env.example
requirements.txt
```

## Setup

1. Install PostgreSQL and create a database named `stockflow`.
2. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   # Windows PowerShell: .venv\\Scripts\\Activate.ps1
   # macOS/Linux: source .venv/bin/activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Copy `.env.example` to `.env` and set your local PostgreSQL credentials. Do not commit `.env`.

5. Create the schemas and tables in order:

   ```bash
   psql -d stockflow -f sql/Bronze_schema.sql
   psql -d stockflow -f sql/Silver_Schema.sql
   psql -d stockflow -f sql/Gold_schema.sql
   ```

   The new per-ticker Bronze table is `bronze.stock_raw_daily`. An existing legacy `bronze.stock_raw` table is left intact. Silver and Gold use unique ticker/date indexes so upserts also work with the original table definitions. If an older Silver or Gold table contains duplicate ticker/date pairs, inspect and reconcile those duplicates before creating the unique indexes; the schema scripts intentionally do not delete user data.

6. Run each stage from the repository root:

   ```bash
   python -m scripts.ingest
   python -m scripts.cleaning
   python -m scripts.gol_metrics
   ```

7. Run unit tests:

   ```bash
   python -m pytest -q
   ```

## Data quality and reruns

- Empty downloads do not silently replace existing datasets.
- Invalid or non-finite OHLCV values are rejected.
- The ticker/date unique indexes prevent duplicate business records.
- Upserts make repeated stage execution safe for the same business key.
- Bronze retains the latest raw payload per ticker/date; it is not an immutable ingestion-event archive.
- Gold currently recomputes and upserts all records from Silver on each run.

## Analytical outputs

Gold includes daily percentage return and 7-/30-observation simple moving averages. The SQL analytics file contains additional total-return, volatility and market-correlation analyses. Moving averages use trading observations, not calendar-day windows.

## Scope and limitations

This is a batch historical-data pipeline, not a real-time streaming or distributed processing system. Airflow, dbt, Kafka, Spark and AWS integrations are not claimed as implemented in the current repository. Validate source availability and licensing before production use.

## Dashboard

The Power BI report is maintained separately and is not currently included in this GitHub repository. Add a dashboard screenshot under `docs/` when publishing a shareable preview.

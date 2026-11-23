# Lesson 01 — Ticker Universe and Daily Data Contract

**Status:** Design approved; config loader implemented; production Nifty 50 membership CSV not yet populated.  
**Date:** 2026-11-23

## Objective

Before the first daily ingestion, define exactly which instruments Stockflow tracks and the shape/meaning of one daily market observation.

This prevents ticker lists from being hard-coded in Python, makes index membership changes traceable, and gives Bronze, Silver, Gold, DynamoDB, PostgreSQL and Athena a shared business key.

## 1. Ticker universe is configuration, not code

Source file: **config/tickers.csv**

Required columns:

| Column | Meaning |
|---|---|
| ticker | yfinance symbol, e.g. RELIANCE.NS |
| company_name | Human-readable company name |
| sector | Sector label used in sector-level analytics |
| exchange | NSE |
| effective_from | First date this ticker belongs to the configured universe |
| effective_to | Last date in the membership period; blank means open-ended |
| is_active | Operational enable/disable flag |
| source_as_of_date | Date on which the universe/sector mapping was verified |
| source_url | Provenance for the membership and sector mapping |

### Why effective dates?

Nifty 50 membership changes. Overwriting a departed ticker with a new ticker destroys the history of the configured universe. Effective-dated rows preserve the previous member and allow point-in-time membership logic.

For this first version, daily collection begins with the approved current universe. A five-year download of today's constituents is **not** a historical reconstruction of the Nifty 50 index: it has survivorship bias. Historical index membership would require point-in-time constituent history.

### Why source provenance?

Sector names and index membership are reference data. Each config snapshot should record when it was verified and where it came from. Do not silently invent or infer sector values.

## 2. Canonical market observation

Business key: **(ticker, trade_date)**

| Field | Contract |
|---|---|
| ticker | Canonical NSE yfinance symbol |
| trade_date | Exchange trading date, ISO YYYY-MM-DD; not ingestion time |
| open | Finite positive numeric value |
| high | Finite positive numeric value |
| low | Finite positive numeric value |
| close | Finite positive numeric value |
| adj_close | Optional adjusted close if supplied and validated |
| volume | Non-negative integer |
| sector | Sector from the effective-dated ticker config |
| exchange | NSE |
| source | yfinance |
| ingested_at_utc | UTC capture timestamp |
| run_id | Airflow logical run identifier |
| schema_version | Version of the record contract |

The yfinance DataFrame is a library-normalized source snapshot, not the literal original Yahoo Finance HTTP response. Bronze stores the untransformed returned rows plus capture metadata. This distinction must remain accurate in documentation and interviews.

## 3. OHLCV invariants

- All required prices are numeric, finite and greater than zero.
- high >= max(open, close, low).
- low <= min(open, close, high).
- volume >= 0 and must be integral.
- (ticker, trade_date) is unique in a curated layer after deterministic deduplication.
- Missing exchange sessions create no synthetic rows.

Returns should use adjusted close where it exists and passes validation; preserve unadjusted close for the reported traded close. The exact corporate-action policy must be tested against the chosen yfinance options and documented.

## 4. Daily incremental extraction

For each ticker:

1. Read its last fully completed market-date checkpoint.
2. If no checkpoint exists, use the configured initial backfill start date.
3. Otherwise fetch from last_successful_trade_date minus overlap_days.
4. Use an explicit end date (exclusive) to make the requested source interval deterministic.
5. Keep the overlap configurable (initial candidate: 3–5 calendar days).
6. Do not treat weekends, exchange holidays or no-data responses as fabricated trading records.
7. Store each run's source snapshot under a unique S3 run prefix with a manifest.
8. Advance downstream completion state only after every required publication succeeds.

The overlap catches some late source publication/corrections; it cannot detect arbitrary historical corrections. Older corrections require a backfill procedure.

## 5. S3 Bronze immutability and retry behavior

Bronze keys include both ingestion date and run ID. A retry must be traceable to the same Airflow run and attempt. Keep each accepted raw batch and its manifest; do not overwrite an older Bronze object just because a newer run has corrected values.

Curated Silver/Gold outputs are rebuildable from S3 Bronze. Parquet output is not automatically an upsert table: reruns must replace affected partitions safely or use a transactional table format. Blindly appending Parquet on retry creates duplicate business keys.

## 6. Code implementation

- Loader: scripts/ticker_universe.py
- Config template: config/tickers.csv
- Unit tests: tests/test_ticker_universe.py

Run:

    python -m pytest -q

The repository CSV is intentionally a header-only template until the current 50-member/sector list is reconciled with the latest maintained ticker configuration. Do not run production ingestion against an empty universe.

## 7. Open decisions for later ADRs

- Exact official source and update cadence for constituents/sector mapping.
- Whether returns use adjusted close exclusively and how missing adjusted-close values are treated.
- Exact overlap policy and historical backfill range.
- Whether Silver/Gold use dynamic partition overwrite or Apache Iceberg for correction-aware updates.
- Whether a source snapshot with zero rows is a valid NO_NEW_DATA outcome or a source outage, based on context and per-ticker results.

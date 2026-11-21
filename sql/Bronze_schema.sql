CREATE SCHEMA IF NOT EXISTS bronze;

-- Keep the legacy bronze.stock_raw table (wide daily API snapshots) intact.
-- The normalized table below stores one source record per ticker/date.
CREATE TABLE IF NOT EXISTS bronze.stock_raw_daily (
    ticker TEXT NOT NULL,
    market_date DATE NOT NULL,
    ingestion_timestamp TIMESTAMPTZ NOT NULL,
    data JSONB NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_stock_raw_daily_ticker_date
    ON bronze.stock_raw_daily (ticker, market_date);

CREATE INDEX IF NOT EXISTS idx_stock_raw_daily_market_date
    ON bronze.stock_raw_daily (market_date);

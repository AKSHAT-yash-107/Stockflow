CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.stock_raw (
    ticker TEXT NOT NULL,
    market_date DATE NOT NULL,
    ingestion_timestamp TIMESTAMPTZ NOT NULL,
    data JSONB NOT NULL,
    CONSTRAINT stock_raw_ticker_date_pk PRIMARY KEY (ticker, market_date)
);

CREATE INDEX IF NOT EXISTS idx_stock_raw_market_date
    ON bronze.stock_raw (market_date);

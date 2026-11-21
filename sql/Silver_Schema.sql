CREATE SCHEMA IF NOT EXISTS silver;

CREATE TABLE IF NOT EXISTS silver.stock_clean (
    date DATE NOT NULL,
    ticker TEXT NOT NULL,
    open DOUBLE PRECISION NOT NULL CHECK (open > 0),
    high DOUBLE PRECISION NOT NULL CHECK (high > 0),
    low DOUBLE PRECISION NOT NULL CHECK (low > 0),
    close DOUBLE PRECISION NOT NULL CHECK (close > 0),
    volume BIGINT NOT NULL CHECK (volume >= 0),
    ingestion_timestamp TIMESTAMPTZ NOT NULL,
    CONSTRAINT stock_clean_date_ticker_pk PRIMARY KEY (date, ticker),
    CONSTRAINT stock_clean_ohlc_valid CHECK (
        high >= GREATEST(open, close, low)
        AND low <= LEAST(open, close, high)
    )
);

CREATE INDEX IF NOT EXISTS idx_stock_clean_ticker_date
    ON silver.stock_clean (ticker, date);

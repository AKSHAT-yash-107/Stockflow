CREATE SCHEMA IF NOT EXISTS gold;

CREATE TABLE IF NOT EXISTS gold.stock_metrics (
    date DATE NOT NULL,
    ticker TEXT NOT NULL,
    close DOUBLE PRECISION NOT NULL CHECK (close > 0),
    daily_return_pct DOUBLE PRECISION,
    sma_7 DOUBLE PRECISION,
    sma_30 DOUBLE PRECISION,
    volume BIGINT NOT NULL CHECK (volume >= 0)
);

-- Compatible with an existing Gold table created by the original schema.
CREATE UNIQUE INDEX IF NOT EXISTS uq_stock_metrics_date_ticker
    ON gold.stock_metrics (date, ticker);

CREATE INDEX IF NOT EXISTS idx_stock_metrics_ticker_date
    ON gold.stock_metrics (ticker, date);

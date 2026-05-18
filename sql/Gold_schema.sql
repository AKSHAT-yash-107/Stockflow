
DROP TABLE IF EXISTS gold.stock_metrics;

CREATE TABLE gold.stock_metrics (
    date DATE,
    ticker TEXT,
    close DOUBLE PRECISION,
    daily_return_pct DOUBLE PRECISION,
    sma_7 DOUBLE PRECISION,
    sma_30 DOUBLE PRECISION,
    volume BIGINT
);
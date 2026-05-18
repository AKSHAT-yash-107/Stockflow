CREATE SCHEMA IF NOT EXISTS silver;

DROP TABLE IF EXISTS silver.stock_clean;

CREATE TABLE silver.stock_clean (
    date DATE,
    ticker TEXT,
    open DOUBLE PRECISION,
    high DOUBLE PRECISION,
    low DOUBLE PRECISION,
    close DOUBLE PRECISION,
    volume BIGINT,
    ingestion_timestamp TIMESTAMP
);
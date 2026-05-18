CREATE SCHEMA IF NOT EXISTS bronze;

DROP TABLE IF EXISTS bronze.stock_raw;

CREATE TABLE bronze.stock_raw (
    ingestion_timestamp TIMESTAMP,
    data JSONB
);
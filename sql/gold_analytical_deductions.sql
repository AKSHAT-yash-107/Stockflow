

-- ==========================================
-- 1. Highest Performing Stocks
-- ==========================================

WITH price_points AS (

    SELECT DISTINCT
        ticker,

        FIRST_VALUE(close) OVER (
            PARTITION BY ticker
            ORDER BY date
        ) AS first_close,

        FIRST_VALUE(close) OVER (
            PARTITION BY ticker
            ORDER BY date DESC
        ) AS last_close

    FROM gold.stock_metrics
)

SELECT
    ticker,

    ROUND(
        (
            (
                (
                    last_close - first_close
                )
                /
                first_close
            ) * 100
        )::numeric,
        2
    ) AS total_return_pct

FROM price_points

ORDER BY total_return_pct DESC;


-- ==========================================
-- 2. Most Stable Stocks
-- ==========================================

SELECT
    ticker,

    ROUND(
        STDDEV(daily_return_pct)::numeric,
        2
    ) AS volatility

FROM gold.stock_metrics

GROUP BY ticker

ORDER BY volatility ASC;


-- ==========================================
-- 3. Most Aggressive Stocks
-- ==========================================

SELECT
    ticker,

    ROUND(
        STDDEV(daily_return_pct)::numeric,
        2
    ) AS volatility

FROM gold.stock_metrics

GROUP BY ticker

ORDER BY volatility DESC;


-- ==========================================
-- 4. Market Correlation Analysis
-- ==========================================

WITH market_returns AS (

    SELECT
        date,
        AVG(daily_return_pct) AS market_return

    FROM gold.stock_metrics

    GROUP BY date
)

SELECT
    g.ticker,

    ROUND(
        CORR(
            g.daily_return_pct,
            m.market_return
        )::numeric,
        2
    ) AS market_correlation

FROM gold.stock_metrics g

JOIN market_returns m
ON g.date = m.date

GROUP BY g.ticker

ORDER BY market_correlation ASC;


-- ==========================================
-- 5. Combined Portfolio Analytics
-- ==========================================

WITH price_points AS (

    SELECT DISTINCT
        ticker,

        FIRST_VALUE(close) OVER (
            PARTITION BY ticker
            ORDER BY date
        ) AS first_close,

        FIRST_VALUE(close) OVER (
            PARTITION BY ticker
            ORDER BY date DESC
        ) AS last_close

    FROM gold.stock_metrics
),

returns AS (

    SELECT
        ticker,

        ROUND(
            (
                (
                    (
                        last_close - first_close
                    )
                    /
                    first_close
                ) * 100
            )::numeric,
            2
        ) AS total_return_pct

    FROM price_points
),

volatility AS (

    SELECT
        ticker,

        ROUND(
            STDDEV(daily_return_pct)::numeric,
            2
        ) AS volatility

    FROM gold.stock_metrics

    GROUP BY ticker
),

market_returns AS (

    SELECT
        date,
        AVG(daily_return_pct) AS market_return

    FROM gold.stock_metrics

    GROUP BY date
),

correlation AS (

    SELECT
        g.ticker,

        ROUND(
            CORR(
                g.daily_return_pct,
                m.market_return
            )::numeric,
            2
        ) AS market_correlation

    FROM gold.stock_metrics g

    JOIN market_returns m
    ON g.date = m.date

    GROUP BY g.ticker
)

SELECT
    r.ticker,
    r.total_return_pct,
    v.volatility,
    c.market_correlation

FROM returns r

JOIN volatility v
ON r.ticker = v.ticker

JOIN correlation c
ON r.ticker = c.ticker

ORDER BY
    r.total_return_pct DESC,
    v.volatility ASC;
```

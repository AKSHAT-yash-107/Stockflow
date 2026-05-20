# Stockflow — Stock Market Data Warehouse & Analytics Platform

## Why I Built This

Most stock datasets available online are either raw CSVs or isolated 
dashboards. I wanted to design a layered analytical pipeline that could 
ingest raw market data, clean and normalize it, generate business-ready 
metrics like returns, volatility, and market correlation, and finally 
expose those insights through a BI dashboard.

The project simulates how financial analytics systems process and transform 
market data into decision-support systems for analysts and investors.

---

## Architecture

![Architecture](docs/architecture.png)

---

## Tech Stack

| Category         | Technology              |
|------------------|-------------------------|
| Language         | Python                  |
| Database         | PostgreSQL              |
| Data Processing  | Pandas                  |
| SQL Analytics    | PostgreSQL SQL          |
| Visualization    | Power BI                |
| API Source       | Yahoo Finance (yfinance)|

---

## Pipeline
Yahoo Finance API
→ ingest.py        (Bronze layer)
→ cleaning.py      (Silver layer)
→ gold.py          (Gold layer)
→ SQL Analytics
→ Power BI Dashboard

---

## Medallion Architecture

### Bronze Layer — Raw Preservation
Stores raw JSON market data from Yahoo Finance exactly as received.

**Why JSONB and not a normal table?**
The Yahoo Finance API returns semi-structured data that may evolve over 
time. By storing raw payloads in JSONB, I preserved the original source 
data exactly as received, which improves traceability, auditability, and 
schema flexibility. This separation reduces ingestion fragility because 
schema changes from the API are less likely to break the Bronze layer.

### Silver Layer — Cleaning and Normalization
Cleans and normalizes OHLCV stock data into one row per stock per date.

**The hardest problem in this project:**
The Yahoo Finance data arrived in wide format where each stock had 
separate columns for Open, High, Low, Close, and Volume. I had to flatten 
multi-index columns, melt the dataset into a row-based structure, and 
handle null values and type conversions — all before the data was 
analytics-ready.

### Gold Layer — Business Metrics
Generates analytical metrics using SQL window functions.

**Metrics computed:**
- Daily return %
- 7-day and 30-day simple moving averages
- Volatility (standard deviation of returns)
- Market correlation
- Anomaly detection via Z-score

---

## Anomaly Detection

Anomalies represent unusual deviations from normal market behavior — 
sudden spikes or drops in returns that may indicate earnings announcements, 
macroeconomic news, panic selling, or momentum breakouts.

**Method:** Z-score on daily returns per ticker. Any day where 
zscore > 3 or zscore < -3 is flagged as anomalous.

**Finding:** 258 anomaly days detected across 17 stocks over 5 years.
Highest: ICICIBANK.NS moved 10.85% in a single day (zscore: 8.34).

---

## Key Numbers

| Metric | Value |
|--------|-------|
| Stocks tracked | 17 NSE stocks |
| Time period | 5 years |
| Silver rows |  21029 |
| Anomaly days detected | 258 |
| Gold metrics computed | Daily return, SMA7, SMA30, Volatility, Correlation |

---

## Dashboard

### Risk vs Return Analysis
![Dashboard](dashboard/powerbi_screenshots/scatter_plot.png)

---

## How To Run

```bash
# 1. Install dependencies
pip install yfinance pandas psycopg2 sqlalchemy

# 2. Set up PostgreSQL and create schemas
psql -f sql/schema.sql

# 3. Run the pipeline
python scripts/ingest.py
python scripts/cleaning.py
python scripts/gold.py
```

---

## Future Improvements

**Apache Airflow** — currently the pipeline runs manually script by 
script. Airflow would automate scheduling, manage task dependencies 
(Gold only runs after Silver completes), and provide monitoring and 
retry handling through DAGs.

**dbt** — replace raw SQL transformations with tested, documented, 
version-controlled dbt models.

**Kafka** — replace batch ingestion with real-time streaming for 
live market data.

**Docker** — containerize the full pipeline for reproducible deployment.

**Cloud (AWS/GCP)** — migrate warehouse to Redshift or BigQuery 
for scalability.

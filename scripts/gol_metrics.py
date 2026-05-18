import pandas as pd
import psycopg2 as pg
from sqlalchemy import create_engine

# -----------------------------
# CONNECT TO POSTGRESQL
# -----------------------------

conn = pg.connect(
    dbname="stockflow",
    host="localhost",
    user="postgres",
    password="123",
    port="5432"
)

# -----------------------------
# READ SILVER LAYER
# -----------------------------

df = pd.read_sql(
    "SELECT * FROM silver.stock_clean",
    conn
)
df.columns = df.columns.str.lower()
# -----------------------------
# SORT DATA
# VERY IMPORTANT
# -----------------------------
df=df.sort_values(['ticker', 'date'])

# -----------------------------
# DAILY RETURN %
# -----------------------------

df['daily_return_pct'] = (
    df.groupby('ticker')['close']
      .pct_change() * 100
)

# -----------------------------
# 7-DAY SIMPLE MOVING AVERAGE
# -----------------------------

df['sma_7'] = (
    df.groupby('ticker')['close']
      .transform(lambda x: x.rolling(7).mean())
)

# -----------------------------
# 30-DAY SIMPLE MOVING AVERAGE
# -----------------------------

df['sma_30'] = (
    df.groupby('ticker')['close']
      .transform(lambda x: x.rolling(30).mean())
)

# -----------------------------
# ROUND VALUES
# -----------------------------

df['daily_return_pct'] = df['daily_return_pct'].round(2)
df['sma_7'] = df['sma_7'].round(2)
df['sma_30'] = df['sma_30'].round(2)

# -----------------------------
# CHECK OUTPUT
# -----------------------------

print(df.head(20))

# -----------------------------
# CREATE SQLALCHEMY ENGINE
# -----------------------------

engine = create_engine(
    "postgresql://postgres:123@localhost:5432/stockflow"
)

# -----------------------------
# LOAD INTO GOLD LAYER
# -----------------------------

df.to_sql(
    name='stock_metrics',
    con=engine,
    schema='gold',
    if_exists='replace',
    index=False
)

# -----------------------------
# CLOSE CONNECTION
# -----------------------------

conn.close()

print("Gold layer created successfully.")
import pandas as pd
import psycopg2 as pg
import json
from sqlalchemy import create_engine
from datetime import datetime

conn=pg.connect(
    host="localhost",
    user="postgres",
    password="123",
    database="stockflow",
    port="5432"

)

cursor=conn.cursor()

df = pd.read_sql("SELECT data FROM bronze.stock_raw", conn)

df=pd.json_normalize(df['data'])

print(df.count().tolist())

melted = pd.melt(
    df,
id_vars = ['Date', 'ingestion_timestamp'],
    var_name='metric_ticker',
    value_name='value'
)
melted[['metric', 'ticker']] = (
    melted['metric_ticker'].str.split('_', expand=True)
)


pivot = melted.pivot_table(
    index=['Date', 'ticker'],      # what uniquely identifies each row? hint: Date + ticker
    columns='metric',         # what becomes the new columns? hint: metric
    values='value',          # what are the values? hint: value
    aggfunc='first'    # if duplicates exist, take first value
)
pivot.reset_index(inplace=True)
pivot.columns.name = None
pivot.dropna(subset=['Close', 'Open', 'High', 'Low'], inplace=True)
pivot['Date'] = pd.to_datetime(pivot['Date']).dt.date
pivot = pivot[pivot['Close'] >0 ]
pivot.drop(columns=['ingestion_timestamp'], errors='ignore', inplace=True)

pivot['ingestion_timestamp'] = datetime.now()
engine = create_engine('postgresql://postgres:123@localhost:5432/stockflow')

pivot.to_sql(
    name='stock_clean',
    con=engine,
    schema='silver',
    if_exists='replace',
    index=False
)
print("Silver saved! Rows:", len(pivot))
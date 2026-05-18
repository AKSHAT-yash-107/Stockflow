import yfinance as yf
import pandas as pd
from datetime import datetime
import psycopg2 as pg
import json


ticker = [
    "RELIANCE.NS",
    "HDFCBANK.NS",
    "BHARTIARTL.NS",
    "SBIN.NS",
    "ICICIBANK.NS",
    "TCS.NS",
    "BAJFINANCE.NS",
    "LT.NS",
    "HINDUNILVR.NS",
    "INFY.NS",
    "SUNPHARMA.NS",
    "MARUTI.NS",
    "AXISBANK.NS",
    "NTPC.NS",
    "TITAN.NS",
    "ITC.NS",
    "ONGC.NS"
]
data = yf.download(ticker, period='5y')
data.reset_index(inplace=True)

data.columns = [
    f"{col[0]}_{col[1]}" if isinstance(col, tuple) and col[1] != '' else col[0]
    for col in data.columns
]
data['ingestion_timestamp'] = datetime.now()
records = data.to_dict(orient='records')


conn=pg.connect(
    dbname="stockflow",
    host="localhost",
    password="123",
    user="postgres",
    port="5432",
)
cursor=conn.cursor()
query ="""INSERT INTO  BRONZE.stock_raw (ingestion_timestamp,data) VALUES (%s,%s)"""

batch=[]
for record in records:(
    batch.append((record['ingestion_timestamp'],json.dumps(record,default=str)))
)
cursor.executemany(query, batch)

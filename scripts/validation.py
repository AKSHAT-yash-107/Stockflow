"""Validation helpers shared by Stockflow pipeline stages."""
from __future__ import annotations

import pandas as pd

PRICE_COLUMNS = ("Open", "High", "Low", "Close")


def validate_market_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a validated copy; raise with actionable messages on bad input."""
    if frame.empty:
        raise ValueError("Market data frame is empty.")
    missing = [column for column in PRICE_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing required OHLC columns: {missing}")

    result = frame.copy()
    for column in PRICE_COLUMNS + ("Volume",):
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")

    result = result.dropna(subset=list(PRICE_COLUMNS))
    result = result[(result["Open"] > 0) & (result["High"] > 0) &
                    (result["Low"] > 0) & (result["Close"] > 0)]
    invalid_ohlc = (
        (result["High"] < result[["Open", "Close"]].max(axis=1)) |
        (result["Low"] > result[["Open", "Close"]].min(axis=1)) |
        (result["High"] < result["Low"])
    )
    result = result.loc[~invalid_ohlc]
    if "Volume" in result.columns:
        result = result.dropna(subset=["Volume"])
        result = result[result["Volume"] >= 0]
        result = result[result["Volume"] % 1 == 0]
        result["Volume"] = result["Volume"].astype("int64")
    return result


def quality_summary(frame: pd.DataFrame) -> dict:
    """Small deterministic quality report suitable for logs and audits."""
    return {
        "rows": int(len(frame)),
        "columns": int(len(frame.columns)),
        "null_cells": int(frame.isna().sum().sum()),
        "duplicate_rows": int(frame.duplicated().sum()),
    }

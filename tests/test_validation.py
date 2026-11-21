import pandas as pd
import pytest

from scripts.validation import validate_market_frame, quality_summary


def test_valid_market_rows_are_retained():
    frame = pd.DataFrame({
        "Open": [100.0], "High": [112.0], "Low": [98.0],
        "Close": [110.0], "Volume": [1000],
    })
    result = validate_market_frame(frame)
    assert len(result) == 1
    assert result.iloc[0]["Volume"] == 1000


@pytest.mark.parametrize(
    "row",
    [
        {"Open": 100, "High": 105, "Low": 98, "Close": 110, "Volume": 1000},
        {"Open": 100, "High": 112, "Low": 105, "Close": 110, "Volume": 1000},
        {"Open": 100, "High": 90, "Low": 95, "Close": 85, "Volume": 1000},
        {"Open": 100, "High": 112, "Low": 98, "Close": 110, "Volume": -1},
        {"Open": 100, "High": 112, "Low": 98, "Close": 110, "Volume": 1.5},
    ],
)
def test_invalid_market_rows_are_removed(row):
    assert validate_market_frame(pd.DataFrame([row])).empty


def test_missing_required_column_fails():
    with pytest.raises(ValueError, match="Missing required"):
        validate_market_frame(pd.DataFrame({"Open": [1]}))


def test_empty_frame_fails():
    with pytest.raises(ValueError, match="empty"):
        validate_market_frame(pd.DataFrame())


def test_quality_summary_counts_duplicates():
    frame = pd.DataFrame({"x": [1, 1], "y": [2, 2]})
    assert quality_summary(frame)["duplicate_rows"] == 1

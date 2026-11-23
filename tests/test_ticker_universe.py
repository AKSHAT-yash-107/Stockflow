import csv
from datetime import date

import pytest

from scripts.ticker_universe import load_ticker_universe


FIELDS = [
    "ticker", "company_name", "sector", "exchange",
    "effective_from", "effective_to", "is_active",
    "source_as_of_date", "source_url",
]


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def row(**overrides):
    result = {
        "ticker": "RELIANCE.NS",
        "company_name": "Reliance Industries",
        "sector": "Oil, Gas & Consumable Fuels",
        "exchange": "NSE",
        "effective_from": "2026-01-01",
        "effective_to": "",
        "is_active": "true",
        "source_as_of_date": "2026-11-23",
        "source_url": "https://www.niftyindices.com/",
    }
    result.update(overrides)
    return result


def test_loads_active_universe_for_date(tmp_path):
    path = tmp_path / "tickers.csv"
    write_csv(path, [row()])
    result = load_ticker_universe(path, date(2026, 11, 23))
    assert len(result) == 1
    assert result[0].ticker == "RELIANCE.NS"


def test_excludes_membership_outside_effective_window(tmp_path):
    path = tmp_path / "tickers.csv"
    write_csv(path, [row(effective_to="2026-06-30")])
    with pytest.raises(ValueError, match="No active tickers"):
        load_ticker_universe(path, date(2026, 11, 23))


def test_rejects_missing_sector(tmp_path):
    path = tmp_path / "tickers.csv"
    write_csv(path, [row(sector="")])
    with pytest.raises(ValueError, match="sector is required"):
        load_ticker_universe(path, date(2026, 11, 23))


def test_rejects_overlapping_membership_periods(tmp_path):
    path = tmp_path / "tickers.csv"
    write_csv(
        path,
        [
            row(effective_from="2026-01-01", effective_to="2026-06-30"),
            row(effective_from="2026-06-15", effective_to=""),
        ],
    )
    with pytest.raises(ValueError, match="Overlapping membership"):
        load_ticker_universe(path, date(2026, 11, 23))


def test_rejects_invalid_boolean(tmp_path):
    path = tmp_path / "tickers.csv"
    write_csv(path, [row(is_active="sometimes")])
    with pytest.raises(ValueError, match="is_active"):
        load_ticker_universe(path, date(2026, 11, 23))


def test_rejects_missing_provenance(tmp_path):
    path = tmp_path / "tickers.csv"
    write_csv(path, [row(source_url="")])
    with pytest.raises(ValueError, match="source_url"):
        load_ticker_universe(path, date(2026, 11, 23))

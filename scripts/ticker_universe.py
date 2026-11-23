"""Load and validate Stockflow's versioned ticker/sector universe.

The CSV is the operational source of membership metadata. Keep historical
membership rows rather than silently replacing a ticker when the index changes.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

REQUIRED_COLUMNS = {
    "ticker", "company_name", "sector", "exchange", "effective_from",
    "effective_to", "is_active", "source_as_of_date", "source_url",
}
TICKER_PATTERN = re.compile(r"^[A-Z0-9&.-]+$")


@dataclass(frozen=True)
class Ticker:
    ticker: str
    company_name: str
    sector: str
    exchange: str
    effective_from: date
    effective_to: date | None
    is_active: bool
    source_as_of_date: date
    source_url: str

    def is_member_on(self, as_of: date) -> bool:
        return (
            self.is_active
            and self.effective_from <= as_of
            and (self.effective_to is None or as_of <= self.effective_to)
        )


def _parse_date(value: str, field: str, row_number: int) -> date | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"Row {row_number}: {field} must use YYYY-MM-DD, got {value!r}"
        ) from exc


def _parse_bool(value: str, row_number: int) -> bool:
    normalized = (value or "").strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise ValueError(
        f"Row {row_number}: is_active must be true/false, got {value!r}"
    )


def load_ticker_universe(csv_path: str | Path, as_of: date) -> list[Ticker]:
    """Return active index constituents for as_of after strict validation."""
    path = Path(csv_path)
    if not path.is_file():
        raise FileNotFoundError(f"Ticker universe file does not exist: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        missing = sorted(REQUIRED_COLUMNS - columns)
        if missing:
            raise ValueError(f"Ticker CSV missing required columns: {missing}")

        records: list[Ticker] = []
        for row_number, row in enumerate(reader, start=2):
            ticker = (row.get("ticker") or "").strip().upper()
            company_name = (row.get("company_name") or "").strip()
            sector = (row.get("sector") or "").strip()
            exchange = (row.get("exchange") or "").strip().upper()
            source_url = (row.get("source_url") or "").strip()

            if not ticker or not TICKER_PATTERN.fullmatch(ticker):
                raise ValueError(f"Row {row_number}: invalid ticker symbol {ticker!r}")
            if not company_name:
                raise ValueError(f"Row {row_number}: company_name is required")
            if not sector:
                raise ValueError(f"Row {row_number}: sector is required")
            if exchange != "NSE":
                raise ValueError(
                    f"Row {row_number}: exchange must be NSE, got {exchange!r}"
                )
            if not source_url:
                raise ValueError(f"Row {row_number}: source_url is required")

            effective_from = _parse_date(
                row.get("effective_from", ""), "effective_from", row_number
            )
            effective_to = _parse_date(
                row.get("effective_to", ""), "effective_to", row_number
            )
            source_as_of = _parse_date(
                row.get("source_as_of_date", ""), "source_as_of_date", row_number
            )
            if effective_from is None:
                raise ValueError(f"Row {row_number}: effective_from is required")
            if source_as_of is None:
                raise ValueError(f"Row {row_number}: source_as_of_date is required")
            if effective_to is not None and effective_to < effective_from:
                raise ValueError(
                    f"Row {row_number}: effective_to precedes effective_from"
                )

            records.append(
                Ticker(
                    ticker=ticker,
                    company_name=company_name,
                    sector=sector,
                    exchange=exchange,
                    effective_from=effective_from,
                    effective_to=effective_to,
                    is_active=_parse_bool(row.get("is_active", ""), row_number),
                    source_as_of_date=source_as_of,
                    source_url=source_url,
                )
            )

    # Overlapping membership windows make sector/membership selection
    # dependent on CSV row order, so reject them.
    grouped: dict[str, list[Ticker]] = {}
    for record in records:
        grouped.setdefault(record.ticker, []).append(record)

    for ticker, versions in grouped.items():
        versions.sort(key=lambda item: item.effective_from)
        for previous, current in zip(versions, versions[1:]):
            previous_end = previous.effective_to or date.max
            if current.effective_from <= previous_end:
                raise ValueError(
                    f"Overlapping membership periods for {ticker}: "
                    f"{previous.effective_from}..{previous.effective_to} and "
                    f"{current.effective_from}..{current.effective_to}"
                )

    active = [record for record in records if record.is_member_on(as_of)]
    if not active:
        raise ValueError(
            f"No active tickers found for {as_of.isoformat()} in {path}"
        )
    return sorted(active, key=lambda item: item.ticker)

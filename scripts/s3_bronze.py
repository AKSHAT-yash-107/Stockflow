"""Write yfinance source snapshots to append-only S3 Bronze objects.

AWS credentials are resolved by Boto3's standard credential provider chain.
No access keys are read from this module or embedded in source code.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Iterable, Mapping
from uuid import UUID

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from dotenv import load_dotenv


TICKER_PATTERN = re.compile(r"^[A-Z0-9&.-]+$")
RUN_ID_PATTERN = re.compile(r"[^A-Za-z0-9_.=-]+")


class BronzeObjectConflict(RuntimeError):
    """Raised when a key exists but its stored content hash is different."""


@dataclass(frozen=True)
class BronzeBatch:
    """Deterministic serialized representation of one ticker's raw batch."""

    ticker: str
    run_id: str
    ingest_date: date
    key: str
    body: bytes
    sha256: str
    record_count: int
    schema_version: int


@dataclass(frozen=True)
class BronzeUploadResult:
    """Result of a conditional S3 write."""

    bucket: str
    key: str
    sha256: str
    record_count: int
    already_present: bool


def _safe_json_value(value: Any) -> Any:
    """Convert common pandas/NumPy/date values into strict JSON values."""
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Decimal):
        return float(value) if value.is_finite() else None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _safe_json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_json_value(item) for item in value]

    # pandas.Timestamp and NumPy scalar objects expose these conversion hooks.
    if hasattr(value, "to_pydatetime"):
        return _safe_json_value(value.to_pydatetime())
    if hasattr(value, "item"):
        return _safe_json_value(value.item())

    raise TypeError(
        f"Unsupported value for Bronze JSON serialization: {type(value).__name__}"
    )


def _normalize_trade_date(value: Any) -> str:
    if value is None:
        raise ValueError("Each source record must include Date or trade_date.")
    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        try:
            # yfinance may provide an ISO date or a timestamp-like ISO string.
            return date.fromisoformat(value[:10]).isoformat()
        except ValueError as exc:
            raise ValueError(f"Invalid trade date: {value!r}") from exc
    raise ValueError(f"Unsupported trade date type: {type(value).__name__}")


def _utc_timestamp(value: datetime) -> str:
    if value is None:
        raise ValueError("captured_at is required for retry-stable serialization.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("captured_at must be timezone-aware.")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def build_bronze_batch(
    *,
    ticker: str,
    records: Iterable[Mapping[str, Any]],
    run_id: str,
    ingest_date: date,
    captured_at: datetime,
    schema_version: int = 1,
) -> BronzeBatch:
    """Serialize a ticker batch as deterministic JSON Lines and content-address it.

    Key includes ingestion date, ticker, Airflow run ID and the SHA-256 of the
    complete object. An identical retry produces the same key and bytes.
    """
    ticker = ticker.strip().upper()
    if not TICKER_PATTERN.fullmatch(ticker) or not any(char.isalnum() for char in ticker):
        raise ValueError(f"Invalid ticker for S3 key: {ticker!r}")
    if not run_id or not run_id.strip():
        raise ValueError("run_id is required.")
    if schema_version < 1:
        raise ValueError("schema_version must be a positive integer.")

    safe_run_id = RUN_ID_PATTERN.sub("_", run_id.strip()).strip("._=")
    if not safe_run_id:
        raise ValueError("run_id contains no usable S3 key characters.")

    captured_at_utc = _utc_timestamp(captured_at)
    lines: list[str] = []
    for row_number, record in enumerate(records, start=1):
        if not isinstance(record, Mapping):
            raise TypeError(f"Record {row_number} must be a mapping.")
        source_date = record.get("trade_date", record.get("Date"))
        trade_date = _normalize_trade_date(source_date)
        envelope = {
            "schema_version": schema_version,
            "source": "yfinance",
            "ticker": ticker,
            "trade_date": trade_date,
            "ingested_at_utc": captured_at_utc,
            "run_id": run_id,
            "source_record": _safe_json_value(record),
        }
        lines.append(
            json.dumps(
                envelope,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        )

    if not lines:
        raise ValueError("Refusing to write an empty Bronze batch.")

    body = ("\n".join(lines) + "\n").encode("utf-8")
    digest = hashlib.sha256(body).hexdigest()
    key = (
        f"bronze/source=yfinance/ingest_date={ingest_date.isoformat()}/"
        f"ticker={ticker}/run_id={safe_run_id}/sha256={digest}.jsonl"
    )
    return BronzeBatch(
        ticker=ticker,
        run_id=run_id,
        ingest_date=ingest_date,
        key=key,
        body=body,
        sha256=digest,
        record_count=len(lines),
        schema_version=schema_version,
    )


def create_s3_client(region_name: str | None = None):
    """Create an S3 client using Boto3's default credential provider chain."""
    load_dotenv()
    region = region_name or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
    if not region:
        raise RuntimeError(
            "Set AWS_REGION (or AWS_DEFAULT_REGION) before creating the S3 client."
        )
    return boto3.client(
        "s3",
        region_name=region,
        config=Config(
            retries={"max_attempts": 5, "mode": "standard"},
            connect_timeout=5,
            read_timeout=30,
        ),
    )


def upload_bronze_batch(
    *,
    s3_client,
    bucket: str,
    batch: BronzeBatch,
) -> BronzeUploadResult:
    """Create the S3 object only if the key does not already exist.

    A 412 on an identical content-addressed key is treated as a successful
    retry. A 412 with mismatched/missing SHA metadata is raised as a conflict.
    A 409 is allowed to bubble up so Airflow can retry the task.
    """
    if not bucket or not bucket.strip():
        raise ValueError("S3 bucket name is required.")

    try:
        response = s3_client.put_object(
            Bucket=bucket,
            Key=batch.key,
            Body=batch.body,
            ContentType="application/x-ndjson",
            ServerSideEncryption="AES256",
            IfNoneMatch="*",
            Metadata={
                "sha256": batch.sha256,
                "ticker": batch.ticker,
                "run-id": RUN_ID_PATTERN.sub("_", batch.run_id)[:200],
                "record-count": str(batch.record_count),
                "schema-version": str(batch.schema_version),
            },
        )
        return BronzeUploadResult(
            bucket=bucket,
            key=batch.key,
            sha256=batch.sha256,
            record_count=batch.record_count,
            already_present=False,
        )
    except ClientError as exc:
        error = exc.response.get("Error", {})
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        code = error.get("Code")
        if status == 412 or code in {"PreconditionFailed", "412"}:
            existing = s3_client.head_object(Bucket=bucket, Key=batch.key)
            existing_hash = existing.get("Metadata", {}).get("sha256")
            if existing_hash != batch.sha256:
                raise BronzeObjectConflict(
                    f"s3://{bucket}/{batch.key} already exists with a different "
                    "or missing SHA-256 metadata value."
                ) from exc
            return BronzeUploadResult(
                bucket=bucket,
                key=batch.key,
                sha256=batch.sha256,
                record_count=batch.record_count,
                already_present=True,
            )
        # 409 ConditionalRequestConflict and transient failures should be
        # handled by the SDK retry policy and/or Airflow task retries.
        raise


def upload_bronze_records(
    *,
    ticker: str,
    records: Iterable[Mapping[str, Any]],
    run_id: str,
    ingest_date: date,
    bucket: str | None = None,
    region_name: str | None = None,
    captured_at: datetime,
    s3_client=None,
) -> BronzeUploadResult:
    """Build and upload one ticker batch using environment-backed settings.

    Pass a reusable s3_client when uploading many tickers in one task to
    avoid creating a new client for each ticker.
    """
    load_dotenv()
    target_bucket = bucket or os.getenv("STOCKFLOW_S3_BUCKET")
    if not target_bucket:
        raise RuntimeError("Set STOCKFLOW_S3_BUCKET before uploading Bronze data.")
    client = s3_client or create_s3_client(region_name=region_name)
    batch = build_bronze_batch(
        ticker=ticker,
        records=records,
        run_id=run_id,
        ingest_date=ingest_date,
        captured_at=captured_at,
    )
    return upload_bronze_batch(
        s3_client=client,
        bucket=target_bucket,
        batch=batch,
    )

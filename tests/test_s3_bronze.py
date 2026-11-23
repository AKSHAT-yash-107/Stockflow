import json
from datetime import date, datetime, timezone
from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError

from scripts.s3_bronze import (
    BronzeObjectConflict,
    build_bronze_batch,
    upload_bronze_batch,
)


CAPTURED_AT = datetime(2026, 11, 23, 13, 30, tzinfo=timezone.utc)


def sample_records():
    return [
        {
            "Date": date(2026, 11, 20),
            "Open": 100.0,
            "High": 112.0,
            "Low": 98.0,
            "Close": 110.0,
            "Volume": 1200,
        }
    ]


def make_batch(records=None, run_id="scheduled__2026-11-23T13:30:00+00:00"):
    return build_bronze_batch(
        ticker="RELIANCE.NS",
        records=records if records is not None else sample_records(),
        run_id=run_id,
        ingest_date=date(2026, 11, 23),
        captured_at=CAPTURED_AT,
    )


def client_error(status, code):
    return ClientError(
        {
            "Error": {"Code": code, "Message": "simulated"},
            "ResponseMetadata": {"HTTPStatusCode": status},
        },
        "PutObject",
    )


def test_batch_is_jsonl_and_contains_lineage():
    batch = make_batch()
    rows = [json.loads(line) for line in batch.body.decode().splitlines()]
    assert len(rows) == 1
    assert rows[0]["ticker"] == "RELIANCE.NS"
    assert rows[0]["trade_date"] == "2026-11-20"
    assert rows[0]["run_id"].startswith("scheduled__")
    assert rows[0]["source"] == "yfinance"
    assert rows[0]["source_record"]["Close"] == 110.0


def test_identical_retry_has_same_key_and_hash():
    first = make_batch()
    second = make_batch()
    assert first.key == second.key
    assert first.sha256 == second.sha256
    assert first.body == second.body


def test_different_payload_has_different_content_addressed_key():
    first = make_batch()
    changed = sample_records()
    changed[0]["Close"] = 111.0
    second = make_batch(changed)
    assert first.key != second.key
    assert first.sha256 != second.sha256


def test_empty_batch_is_rejected():
    with pytest.raises(ValueError, match="empty Bronze batch"):
        make_batch(records=[])


def test_missing_trade_date_is_rejected():
    with pytest.raises(ValueError, match="trade_date"):
        make_batch(records=[{"Close": 100}])


def test_unsafe_ticker_is_rejected():
    with pytest.raises(ValueError, match="Invalid ticker"):
        build_bronze_batch(
            ticker="../../bucket",
            records=sample_records(),
            run_id="run-1",
            ingest_date=date(2026, 11, 23),
            captured_at=CAPTURED_AT,
        )


def test_naive_timestamp_is_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        build_bronze_batch(
            ticker="RELIANCE.NS",
            records=sample_records(),
            run_id="run-1",
            ingest_date=date(2026, 11, 23),
            captured_at=datetime(2026, 11, 23, 13, 30),
        )


def test_upload_uses_conditional_write_and_metadata():
    s3 = Mock()
    s3.put_object.return_value = {"ETag": '"etag"'}
    batch = make_batch()

    result = upload_bronze_batch(s3_client=s3, bucket="stockflow-lake", batch=batch)

    kwargs = s3.put_object.call_args.kwargs
    assert kwargs["IfNoneMatch"] == "*"
    assert kwargs["ContentType"] == "application/x-ndjson"
    assert kwargs["Metadata"]["sha256"] == batch.sha256
    assert result.already_present is False


def test_identical_existing_object_is_successful_retry():
    s3 = Mock()
    s3.put_object.side_effect = client_error(412, "PreconditionFailed")
    batch = make_batch()
    s3.head_object.return_value = {"Metadata": {"sha256": batch.sha256}}

    result = upload_bronze_batch(s3_client=s3, bucket="stockflow-lake", batch=batch)

    assert result.already_present is True
    s3.head_object.assert_called_once_with(Bucket="stockflow-lake", Key=batch.key)


def test_existing_key_with_different_hash_is_a_conflict():
    s3 = Mock()
    s3.put_object.side_effect = client_error(412, "PreconditionFailed")
    s3.head_object.return_value = {"Metadata": {"sha256": "wrong-hash"}}

    with pytest.raises(BronzeObjectConflict):
        upload_bronze_batch(
            s3_client=s3,
            bucket="stockflow-lake",
            batch=make_batch(),
        )


def test_transient_conflict_is_left_for_airflow_retry():
    s3 = Mock()
    s3.put_object.side_effect = client_error(409, "ConditionalRequestConflict")

    with pytest.raises(ClientError):
        upload_bronze_batch(
            s3_client=s3,
            bucket="stockflow-lake",
            batch=make_batch(),
        )


def test_schema_version_is_consistent_in_body_and_object_metadata():
    batch = build_bronze_batch(
        ticker="RELIANCE.NS",
        records=sample_records(),
        run_id="run-schema-v2",
        ingest_date=date(2026, 11, 23),
        captured_at=CAPTURED_AT,
        schema_version=2,
    )
    envelope = json.loads(batch.body.decode().splitlines()[0])
    assert envelope["schema_version"] == 2
    s3 = Mock()
    upload_bronze_batch(s3_client=s3, bucket="stockflow-lake", batch=batch)
    assert s3.put_object.call_args.kwargs["Metadata"]["schema-version"] == "2"

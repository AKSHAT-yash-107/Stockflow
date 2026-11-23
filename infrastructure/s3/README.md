# Stockflow S3 Bronze Bucket Controls

This document describes the bucket configuration expected by the S3 Bronze writer. It does not create or modify AWS resources.

## Required configuration

- Use a dedicated bucket for Stockflow data.
- Keep S3 Block Public Access enabled.
- Enable bucket versioning.
- Enable default server-side encryption (SSE-S3 for the initial implementation; use SSE-KMS if the project requires customer-managed keys).
- Grant the ingestion role only the required `s3:PutObject` and `s3:GetObject` permissions for the Bronze prefix; add object-read access so the writer can check metadata after a conditional-write collision.
- Do not grant the ingestion role `s3:DeleteObject`.
- Keep bucket and object ownership bucket-owner-enforced; do not set ACLs in application code.
- Configure lifecycle/retention deliberately after deciding how long raw market data and old versions should be retained.

## Application-level immutability

The writer:
- builds a JSON Lines object for one ticker and Airflow run;
- hashes the exact serialized bytes with SHA-256;
- embeds the digest in the S3 key;
- writes with `IfNoneMatch="*"`, which prevents replacing an existing current object key;
- checks object metadata after a 412 to treat an identical retry as already complete;
- raises a conflict if the existing key has a different digest.

An identical retry has the same payload hash and key. A corrected payload has a different digest/key and is stored as a new object. A 409 conditional-write conflict is allowed to fail the task so Airflow can retry it.

**The capture timestamp must be deterministic across retries.** Pass Airflow's stable `logical_date` (or another run-stable timestamp) as `captured_at`. Do not use `datetime.now()` inside a retried task to build the Bronze envelope, because that changes the serialized bytes and SHA-256 on every retry.

This is application-level append-only behavior, not regulatory WORM retention. For stronger deletion/retention protection, evaluate S3 Object Lock. Object Lock requires versioning and its retention settings are difficult to reverse; do not enable it casually on a production bucket.

## Example environment

```dotenv
AWS_REGION=ap-south-1
STOCKFLOW_S3_BUCKET=replace-with-your-bucket-name
```

Credentials must come from an IAM role, an AWS IAM Identity Center/CLI profile, or another supported Boto3 credential provider. Never put AWS access keys in Git or in `.env.example`.

## First manual verification

1. Create/configure the bucket using the AWS Console or infrastructure-as-code.
2. Configure local credentials with an AWS profile.
3. Set `AWS_PROFILE`, `AWS_REGION`, and `STOCKFLOW_S3_BUCKET`.
4. Confirm the identity with `aws sts get-caller-identity`.
5. Upload a small test batch and inspect its key, metadata and content.
6. Run the same upload again and verify it returns `already_present=True`.
7. Change one source value and verify a new hash/key is created without replacing the previous object.

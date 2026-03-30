"""Lambda that extracts archive files (ZIP, TAR, etc.) from S3 back into S3."""

import json
import logging
import os
import io
import zipfile
import tarfile
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

DOCS_BUCKET = os.environ.get("DOCS_BUCKET", "")
s3_client = boto3.client("s3")
MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024  # 500 MB for archives


def handler(event, context):
    logger.info("Received event: %s", json.dumps(event, default=str))
    tool_input = event

    s3_key = tool_input.get("s3_key")
    if not s3_key:
        return _response({"error": "s3_key is required"})

    if s3_key.startswith("s3://"):
        parts = s3_key[5:].split("/", 1)
        s3_key = parts[1] if len(parts) > 1 else ""
        if not s3_key:
            return _response({"error": "Could not extract object key from S3 URI"})

    # Destination prefix defaults to archive name without extension
    dest_prefix = tool_input.get("destination_prefix", "")
    if not dest_prefix:
        base = s3_key.rsplit("/", 1)[-1]
        dest_prefix = base.rsplit(".", 1)[0] + "_extracted/"

    try:
        head = s3_client.head_object(Bucket=DOCS_BUCKET, Key=s3_key)
        if head.get("ContentLength", 0) > MAX_FILE_SIZE_BYTES:
            return _response(
                {
                    "error": f"Archive exceeds {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB limit"
                }
            )
        obj = s3_client.get_object(Bucket=DOCS_BUCKET, Key=s3_key)
        archive_bytes = obj["Body"].read()
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ("NoSuchKey", "NoSuchBucket"):
            return _response({"error": f"Not found: s3://{DOCS_BUCKET}/{s3_key}"})
        return _response({"error": "Failed to retrieve archive from S3"})

    extracted_files = []
    try:
        if zipfile.is_zipfile(io.BytesIO(archive_bytes)):
            extracted_files = _extract_zip(archive_bytes, dest_prefix)
        elif _is_tarfile(archive_bytes):
            extracted_files = _extract_tar(archive_bytes, dest_prefix)
        else:
            return _response(
                {"error": "Unsupported archive format. Supported: ZIP, TAR, TAR.GZ"}
            )
    except Exception:
        logger.exception("Archive extraction failed")
        return _response({"error": "Archive extraction failed"})

    return _response(
        {
            "s3_key": s3_key,
            "destination_prefix": dest_prefix,
            "extracted_count": len(extracted_files),
            "extracted_files": extracted_files[:50],  # cap listing
        }
    )


def _extract_zip(archive_bytes, dest_prefix):
    extracted = []
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            dest_key = dest_prefix + info.filename
            s3_client.put_object(
                Bucket=DOCS_BUCKET, Key=dest_key, Body=zf.read(info.filename)
            )
            extracted.append(dest_key)
    return extracted


def _extract_tar(archive_bytes, dest_prefix):
    extracted = []
    with tarfile.open(fileobj=io.BytesIO(archive_bytes)) as tf:
        for member in tf.getmembers():
            if not member.isfile():
                continue
            f = tf.extractfile(member)
            if f is None:
                continue
            dest_key = dest_prefix + member.name
            s3_client.put_object(Bucket=DOCS_BUCKET, Key=dest_key, Body=f.read())
            extracted.append(dest_key)
    return extracted


def _is_tarfile(data):
    try:
        with tarfile.open(fileobj=io.BytesIO(data)) as _:
            return True
    except (tarfile.TarError, Exception):
        return False


def _response(body):
    return {"output": json.dumps(body)}

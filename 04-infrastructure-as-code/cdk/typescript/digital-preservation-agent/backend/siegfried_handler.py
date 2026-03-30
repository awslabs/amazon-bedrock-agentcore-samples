"""Lambda bridging AgentCore Gateway MCP tool calls to Siegfried on Fargate.

Siegfried server accepts POST /identify with file as form-data.
Returns PRONOM format identification results (JSON).
"""

import json
import logging
import os
import urllib.request
import urllib.error
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ALB_URL = os.environ["ALB_URL"]
DOCS_BUCKET = os.environ.get("DOCS_BUCKET", "")
s3 = boto3.client("s3")
MAX_FILE_SIZE = 100 * 1024 * 1024


def handler(event, context):
    logger.info("Event: %s", json.dumps(event, default=str))

    s3_key = event.get("s3_key", "")
    if not s3_key:
        return _resp({"error": "s3_key is required"})

    if s3_key.startswith("s3://"):
        s3_key = s3_key[5:].split("/", 1)[-1]

    try:
        head = s3.head_object(Bucket=DOCS_BUCKET, Key=s3_key)
        if head.get("ContentLength", 0) > MAX_FILE_SIZE:
            return _resp(
                {"error": f"File exceeds {MAX_FILE_SIZE // (1024 * 1024)} MB limit"}
            )
        obj = s3.get_object(Bucket=DOCS_BUCKET, Key=s3_key)
        file_bytes = obj["Body"].read()
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ("NoSuchKey", "NoSuchBucket"):
            return _resp({"error": f"Not found: s3://{DOCS_BUCKET}/{s3_key}"})
        return _resp({"error": "Failed to retrieve file from S3"})

    filename = s3_key.split("/")[-1]
    try:
        # Siegfried server expects POST /identify with multipart form-data
        boundary = "----SiegfriedBoundary"
        body = (
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
                f"Content-Type: application/octet-stream\r\n\r\n"
            ).encode()
            + file_bytes
            + f"\r\n--{boundary}--\r\n".encode()
        )

        req = urllib.request.Request(
            f"{ALB_URL}/identify?format=json",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        return _resp({"s3_key": s3_key, "identification": result})
    except Exception:
        logger.exception("Siegfried call failed")
        return _resp({"error": "Siegfried identification failed"})


def _resp(body):
    return {"output": json.dumps(body)}

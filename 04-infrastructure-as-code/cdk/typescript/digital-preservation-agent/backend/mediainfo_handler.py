"""Lambda bridging AgentCore Gateway MCP tool calls to MediaInfo on Fargate."""

import json
import logging
import os
import urllib.request
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
        req = urllib.request.Request(
            f"{ALB_URL}/mediainfo/{filename}",
            data=file_bytes,
            headers={"Content-Type": "application/octet-stream"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        return _resp({"s3_key": s3_key, "media_info": result})
    except Exception:
        logger.exception("MediaInfo call failed")
        return _resp({"error": "MediaInfo analysis failed"})


def _resp(body):
    return {"output": json.dumps(body)}

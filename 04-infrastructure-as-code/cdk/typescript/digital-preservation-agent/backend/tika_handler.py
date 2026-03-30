"""Lambda bridging AgentCore Gateway MCP tool calls to Apache Tika on Fargate.

Single tool (tika_process): fetches a file from S3 and runs text extraction,
metadata extraction, or MIME type detection. Tika handles archives natively.
"""

import json
import logging
import os
import time
import urllib.request
import urllib.error
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ALB_URL = os.environ["ALB_URL"]
DOCS_BUCKET = os.environ.get("DOCS_BUCKET", "")
s3 = boto3.client("s3")
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB

ACTIONS = {
    "extract_text": ("/tika", "text/plain"),
    "extract_metadata": ("/meta", "application/json"),
    "detect_type": ("/detect/stream", "text/plain"),
}


def handler(event, context):
    logger.info("Event: %s", json.dumps(event, default=str))

    s3_key = event.get("s3_key", "")
    if not s3_key:
        return _resp({"error": "s3_key is required"})

    # Strip s3:// prefix if present
    if s3_key.startswith("s3://"):
        s3_key = s3_key[5:].split("/", 1)[-1]

    action = event.get("action", "extract_text")
    if action not in ACTIONS:
        return _resp({"error": f"Invalid action '{action}'. Use: {', '.join(ACTIONS)}"})

    # Fetch from S3
    try:
        head = s3.head_object(Bucket=DOCS_BUCKET, Key=s3_key)
        if head.get("ContentLength", 0) > MAX_FILE_SIZE:
            return _resp(
                {"error": f"File exceeds {MAX_FILE_SIZE // (1024 * 1024)} MB limit"}
            )
        obj = s3.get_object(Bucket=DOCS_BUCKET, Key=s3_key)
        file_bytes = obj["Body"].read()
        content_type = obj.get("ContentType", "application/octet-stream")
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ("NoSuchKey", "NoSuchBucket"):
            return _resp({"error": f"Not found: s3://{DOCS_BUCKET}/{s3_key}"})
        return _resp({"error": "Failed to retrieve file from S3"})

    # Call Tika
    tika_path, accept = ACTIONS[action]
    try:
        result = _call_tika(tika_path, file_bytes, content_type, accept)
    except Exception:
        logger.exception("Tika call failed")
        return _resp({"error": "Tika processing failed"})

    if action == "extract_metadata":
        return _resp({"s3_key": s3_key, "metadata": json.loads(result)})
    if action == "detect_type":
        return _resp({"s3_key": s3_key, "mime_type": result.strip()})
    return _resp({"s3_key": s3_key, "extracted_text": result})


def _call_tika(path, data, content_type, accept, timeout=90, retries=3):
    last_err = None
    for i in range(retries):
        try:
            req = urllib.request.Request(
                f"{ALB_URL}{path}",
                data=data,
                headers={"Content-Type": content_type, "Accept": accept},
                method="PUT",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8")
        except (urllib.error.URLError, ConnectionError) as e:
            last_err = e
            if i < retries - 1:
                time.sleep(2**i)
                logger.warning("Tika retry %d/%d: %s", i + 1, retries, e)
    raise last_err


def _resp(body):
    return {"output": json.dumps(body)}

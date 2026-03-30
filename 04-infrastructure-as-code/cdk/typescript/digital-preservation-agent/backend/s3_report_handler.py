"""Lambda that saves analysis reports as JSON to S3."""

import json
import logging
import os
import datetime
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

DOCS_BUCKET = os.environ.get("DOCS_BUCKET", "")
s3_client = boto3.client("s3")


def handler(event, context):
    logger.info("Received event: %s", json.dumps(event, default=str))
    tool_input = event

    report_data = tool_input.get("report_data")
    if not report_data:
        return _response({"error": "report_data is required"})

    report_name = tool_input.get("report_name", "")
    if not report_name:
        ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        report_name = f"analysis_report_{ts}"

    s3_key = f"reports/{report_name}.json"

    # report_data can be a string or dict
    if isinstance(report_data, str):
        body = report_data
    else:
        body = json.dumps(report_data, indent=2, default=str)

    try:
        s3_client.put_object(
            Bucket=DOCS_BUCKET,
            Key=s3_key,
            Body=body.encode("utf-8"),
            ContentType="application/json",
        )
        return _response(
            {
                "s3_key": s3_key,
                "s3_uri": f"s3://{DOCS_BUCKET}/{s3_key}",
                "status": "saved",
            }
        )
    except Exception:
        logger.exception("Failed to save report to S3")
        return _response({"error": "Failed to save report to S3"})


def _response(body):
    return {"output": json.dumps(body)}

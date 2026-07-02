"""Trigger Lambda: S3 email → EventBridge → Invoke Agent Runtime with SigV4 auth.

The Runtime uses IAM (SigV4) authentication. This Lambda's execution role has
bedrock-agentcore:InvokeAgentRuntime permission granted by CDK.
"""

import json
import os
import re
import urllib.parse
import urllib.request

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.session import Session as BotocoreSession

s3 = boto3.client("s3")

# Environment variables (set by CDK)
RUNTIME_ARN = os.environ.get("AGENTCORE_RUNTIME_ARN", "")
REGION = os.environ.get("AWS_REGION", "us-west-2")


def invoke_runtime(payload_dict):
    """Invoke the AgentCore Runtime via HTTPS with SigV4 auth."""
    escaped_arn = urllib.parse.quote(RUNTIME_ARN, safe="")
    url = f"https://bedrock-agentcore.{REGION}.amazonaws.com/runtimes/{escaped_arn}/invocations"

    payload = json.dumps(payload_dict).encode()

    # Sign the request with SigV4 using the Lambda's execution role credentials
    session = BotocoreSession()
    credentials = session.get_credentials().get_frozen_credentials()

    aws_request = AWSRequest(
        method="POST",
        url=url,
        data=payload,
        headers={
            "Content-Type": "application/json",
        },
    )
    SigV4Auth(credentials, "bedrock-agentcore", REGION).add_auth(aws_request)

    req = urllib.request.Request(
        url,
        data=payload,
        headers=dict(aws_request.headers),
    )

    # Buffer streaming SSE response into clean text
    if not url.startswith("https://"):
        raise ValueError(f"Only HTTPS URLs are permitted: {url}")
    content_parts = []
    with urllib.request.urlopen(req, timeout=120) as resp:  # nosec B310
        for line in resp:
            decoded = line.decode("utf-8").strip()
            if not decoded:
                continue
            if decoded.startswith("data: "):
                chunk = decoded[6:]
                # Remove surrounding quotes from JSON-encoded strings
                if chunk.startswith('"') and chunk.endswith('"'):
                    chunk = json.loads(chunk)  # proper JSON unescape
                content_parts.append(chunk)
            elif decoded.startswith("{") and "error" in decoded:
                # Error response
                content_parts.append(f"\n[ERROR] {decoded}\n")

    return "".join(content_parts)


def parse_email(content):
    """Parse email-format text into structured fields."""
    headers = {}
    lines = content.split("\n")
    body_start = 0
    for i, line in enumerate(lines):
        if line.strip() == "":
            body_start = i + 1
            break
        match = re.match(r"^(From|Subject|Date|To):\s*(.+)$", line, re.IGNORECASE)
        if match:
            headers[match.group(1).lower()] = match.group(2).strip()
    body = "\n".join(lines[body_start:]).strip()
    return headers, body


def is_email_format(content):
    """Check if content looks like an email (has From: or Subject: headers)."""
    return bool(re.match(r"^(From|Subject):", content, re.IGNORECASE | re.MULTILINE))


def handler(event, context):
    detail = event.get("detail", {})
    bucket = detail.get("bucket", {}).get("name", "")
    key = detail.get("object", {}).get("key", "")

    if not bucket or not key:
        return {"statusCode": 400, "body": "Missing S3 event details"}

    obj = s3.get_object(Bucket=bucket, Key=key)
    content = obj["Body"].read().decode("utf-8")

    # Determine format and extract claim info
    if is_email_format(content):
        headers, body = parse_email(content)
        prompt = f"Process this insurance claim from email:\n\n{body}"
        claimant_email = headers.get("from", "")
        source = f"email:{headers.get('subject', 'No Subject')}"
    else:
        try:
            claim_data = json.loads(content)
            prompt = f"Process this claim: {content}"
            claimant_email = claim_data.get("claimant_email", "")
            source = f"s3://{bucket}/{key}"
        except json.JSONDecodeError:
            prompt = content
            claimant_email = ""
            source = f"s3://{bucket}/{key}"

    payload = {"prompt": prompt, "source": source}
    if claimant_email:
        payload["claimant_email"] = claimant_email

    # Invoke runtime with SigV4 (using Lambda execution role credentials)
    result = invoke_runtime(payload)

    print(f"Agent response for {key}: {result[:1000]}")
    return {"statusCode": 200, "body": result}

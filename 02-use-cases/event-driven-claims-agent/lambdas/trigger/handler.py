"""Trigger Lambda: S3 email → EventBridge → Invoke Agent Runtime with JWT auth.

Since the Runtime uses CUSTOM_JWT auth, we can't use boto3 SDK (SigV4).
Instead, we get a Cognito M2M token and invoke via HTTPS with [REDACTED_TOKEN]
"""

import base64
import json
import os
import re
import urllib.parse
import urllib.request

import boto3

s3 = boto3.client("s3")

# Environment variables (set by CDK)
RUNTIME_ARN = os.environ.get("AGENTCORE_RUNTIME_ARN", "")
COGNITO_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID", "")
COGNITO_CLIENT_ID = os.environ.get("COGNITO_CLIENT_ID", "")
COGNITO_CLIENT_SECRET = os.environ.get("COGNITO_CLIENT_SECRET", "")
COGNITO_TOKEN_ENDPOINT = os.environ.get("COGNITO_TOKEN_ENDPOINT", "")
REGION = os.environ.get("AWS_REGION", "us-west-2")


def get_cognito_token():
    """Get M2M JWT from Cognito using client_credentials flow."""
    token_endpoint = COGNITO_TOKEN_ENDPOINT

    creds = base64.b64encode(f"{COGNITO_CLIENT_ID}:{COGNITO_CLIENT_SECRET}".encode()).decode()
    data = urllib.parse.urlencode(
        {
            "grant_type": "client_credentials",
            "scope": "agentcore/invoke",
        }
    ).encode()

    req = urllib.request.Request(
        token_endpoint,
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {creds}",
        },
    )

    if not token_endpoint.startswith("https://"):
        raise ValueError(f"Only HTTPS URLs are permitted: {token_endpoint}")
    with urllib.request.urlopen(req) as resp:  # nosec B310
        token_data = json.loads(resp.read())

    return token_data["access_token"]


def invoke_runtime_with_jwt(token, payload_dict):
    """Invoke the AgentCore Runtime via HTTPS with JWT bearer token."""
    escaped_arn = urllib.parse.quote(RUNTIME_ARN, safe="")
    url = f"https://bedrock-agentcore.{REGION}.amazonaws.com/runtimes/{escaped_arn}/invocations"

    payload = json.dumps(payload_dict).encode()

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
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

    # Get JWT and invoke runtime via HTTPS
    token = get_cognito_token()
    result = invoke_runtime_with_jwt(token, payload)

    print(f"Agent response for {key}: {result[:1000]}")
    return {"statusCode": 200, "body": result}

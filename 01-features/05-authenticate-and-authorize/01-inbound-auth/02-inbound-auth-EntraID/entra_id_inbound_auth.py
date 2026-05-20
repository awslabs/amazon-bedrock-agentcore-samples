"""
Entra ID Inbound Authentication for AgentCore Runtime.

Demonstrates how to configure an Amazon Bedrock AgentCore Runtime agent with
Microsoft Entra ID (Azure Active Directory) as the inbound identity provider,
using OAuth 2.0 Authorization Code / client credentials flow.

The agent rejects unauthenticated requests. Only callers presenting a valid
Entra ID JWT bearer token can invoke the agent.

Architecture:
    Client → MSAL (acquire_token_for_client) → Entra ID → Bearer JWT
    Client + Bearer JWT → AgentCore Runtime → validate JWT → Agent responds

Usage:
    python entra_id_inbound_auth.py
    python entra_id_inbound_auth.py --cleanup

Prerequisites:
    - AWS CLI configured
    - Microsoft Entra ID tenant with an App Registration
    - pip install -r requirements.txt
    - Set environment variables:
        ENTRA_TENANT_ID    - Directory (tenant) ID from App Registration > Overview
        ENTRA_CLIENT_ID    - Application (client) ID from App Registration > Overview
        ENTRA_CLIENT_SECRET - Client secret from App Registration > Certificates & Secrets
        ENTRA_AUDIENCE     - Application ID URI from App Registration > Expose an API
        ENTRA_SCOPES       - Scope string ending in /.default, e.g. api://<app-id>/.default

Entra ID Setup (one-time):
    1. Go to https://portal.azure.com > Microsoft Entra ID > App registrations
    2. Click New Registration, select multi-tenant option
    3. Create a client secret (Certificates & Secrets > New client secret)
    4. Expose an API: set Application ID URI, add scope
    5. Collect Tenant ID, Client ID, Client Secret, Audience
"""

import argparse
import json
import os
import time
import urllib.parse
import uuid
import zipfile
from io import BytesIO

import boto3
import msal
import requests
from boto3.session import Session

# ── Configuration ─────────────────────────────────────────────────────────────

AGENT_NAME = f"entra_inbound_auth_{int(time.time()) % 100000}"
AGENT_FILE = "simple_streaming_agent.py"
RUNTIME_CONFIG_FILE = "runtime_config_entra_inbound.json"

# ── AWS Setup ──────────────────────────────────────────────────────────────────

session = Session()
REGION = session.region_name or "us-west-2"
ACCOUNT_ID = session.client("sts").get_caller_identity()["Account"]

print(f"Region:  {REGION}")
print(f"Account: {ACCOUNT_ID}")


# ── Agent Code ─────────────────────────────────────────────────────────────────

AGENT_CODE = """import asyncio
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent

app = BedrockAgentCoreApp()
agent = Agent()

class StreamingQueue:
    def __init__(self):
        self.finished = False
        self.queue = asyncio.Queue()

    async def put(self, item):
        await self.queue.put(item)

    async def finish(self):
        self.finished = True
        await self.queue.put(None)

    async def stream(self):
        while True:
            item = await self.queue.get()
            if item is None and self.finished:
                break
            yield item

queue = StreamingQueue()

async def agent_task(user_message: str):
    try:
        await queue.put("Agent execution begins....")
        response = agent(user_message)
        await queue.put(response.message)
    except Exception as e:
        await queue.put(f"Failed with error: {repr(e)}")
    finally:
        await queue.put("Agent execution finished")
        await queue.finish()

@app.entrypoint
async def strands_agent_entraid(payload, context):
    print("Context:", context)
    prompt = payload.get("prompt", "hello")
    task = asyncio.create_task(agent_task(prompt))
    async def stream_with_task():
        async for item in queue.stream():
            yield item
        await task
    return stream_with_task()

if __name__ == "__main__":
    app.run()
"""


# ── Step 1: Create IAM Execution Role ─────────────────────────────────────────


def create_execution_role(role_name: str) -> str:
    """Create IAM execution role for AgentCore Runtime."""
    iam = boto3.client("iam", region_name=REGION)

    trust_policy = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                }
            ],
        }
    )

    try:
        role = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=trust_policy,
            Description="AgentCore Runtime execution role for Entra inbound auth demo",
        )
        role_arn = role["Role"]["Arn"]
        print(f"  Created IAM role: {role_name}")
    except iam.exceptions.EntityAlreadyExistsException:
        role_arn = iam.get_role(RoleName=role_name)["Role"]["Arn"]
        print(f"  Reusing existing IAM role: {role_name}")

    policy = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "bedrock:InvokeModel",
                        "bedrock:InvokeModelWithResponseStream",
                    ],
                    "Resource": f"arn:aws:bedrock:{REGION}::foundation-model/*",
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                    ],
                    "Resource": "arn:aws:logs:*:*:*",
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "ecr:GetAuthorizationToken",
                        "ecr:BatchGetImage",
                        "ecr:GetDownloadUrlForLayer",
                    ],
                    "Resource": "*",
                },
            ],
        }
    )

    try:
        iam.put_role_policy(
            RoleName=role_name,
            PolicyName="agentcore-execution-policy",
            PolicyDocument=policy,
        )
    except Exception:
        pass  # Policy may already exist

    time.sleep(5)  # Allow role propagation
    return role_arn


# ── Step 2: Upload Agent Code to S3 ───────────────────────────────────────────


def upload_agent_to_s3() -> dict:
    """Create agent zip and upload to S3."""
    s3 = boto3.client("s3", region_name=REGION)
    bucket_name = f"agentcore-entra-inbound-{ACCOUNT_ID}-{REGION}"

    try:
        if REGION == "us-east-1":
            s3.create_bucket(Bucket=bucket_name)
        else:
            s3.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={"LocationConstraint": REGION},
            )
        print(f"  Created S3 bucket: {bucket_name}")
    except s3.exceptions.BucketAlreadyOwnedByYou:
        print(f"  Reusing S3 bucket: {bucket_name}")

    # Create zip with agent code
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(AGENT_FILE, AGENT_CODE)
        zf.writestr("requirements.txt", "strands-agents\nbedrock-agentcore\n")

    zip_buffer.seek(0)
    s3_key = f"agents/{AGENT_NAME}/agent.zip"
    s3.put_object(Bucket=bucket_name, Key=s3_key, Body=zip_buffer.read())
    print(f"  Uploaded agent code to s3://{bucket_name}/{s3_key}")

    return {"bucket": bucket_name, "key": s3_key}


# ── Step 3: Create AgentCore Runtime with Entra JWT Authorizer ────────────────


def create_runtime(role_arn: str, s3_info: dict) -> dict:
    """Create AgentCore Runtime with customJWTAuthorizer for Entra ID."""
    tenant_id = os.environ.get("ENTRA_TENANT_ID")
    audience = os.environ.get("ENTRA_AUDIENCE")

    if not tenant_id or not audience:
        raise ValueError(
            "Set ENTRA_TENANT_ID and ENTRA_AUDIENCE environment variables.\n"
            "Tenant ID: App Registration > Overview > Directory (tenant) ID\n"
            "Audience:  App Registration > Expose an API > Application ID URI"
        )

    discovery_url = (
        f"https://login.microsoftonline.com/{tenant_id}"
        "/.well-known/openid-configuration"
    )

    control = boto3.client("bedrock-agentcore-control", region_name=REGION)

    response = control.create_agent_runtime(
        agentRuntimeName=AGENT_NAME,
        agentRuntimeArtifact={
            "containerConfiguration": {
                "containerUri": (
                    f"{ACCOUNT_ID}.dkr.ecr.{REGION}.amazonaws.com/"
                    f"bedrock-agentcore/managed/runtimes/python3.13:latest"
                ),
            }
        },
        roleArn=role_arn,
        networkConfiguration={"networkMode": "PUBLIC"},
        authorizerConfiguration={
            "customJWTAuthorizer": {
                "discoveryUrl": discovery_url,
                "allowedAudience": [audience],
            }
        },
        codeConfiguration={
            "code": {
                "s3": {
                    "uri": f"s3://{s3_info['bucket']}/{s3_info['key']}",
                    "entryPoint": AGENT_FILE,
                }
            }
        },
    )

    runtime_id = response["agentRuntimeId"]
    runtime_arn = response["agentRuntimeArn"]
    print(f"  Created runtime: {AGENT_NAME}")
    print(f"  Runtime ID: {runtime_id}")
    print(f"  Discovery URL: {discovery_url}")
    print(f"  Allowed Audience: {audience}")

    # Wait for READY
    print("  Waiting for runtime to become READY...")
    while True:
        status_resp = control.get_agent_runtime(agentRuntimeId=runtime_id)
        status = status_resp.get("status", "UNKNOWN")
        print(f"    Status: {status}")
        if status == "READY":
            break
        if status in ("CREATE_FAILED", "DELETE_FAILED", "UPDATE_FAILED"):
            raise RuntimeError(f"Runtime creation failed with status: {status}")
        time.sleep(15)

    endpoint_url = (
        f"https://bedrock-agentcore.{REGION}.amazonaws.com"
        f"/runtimes/{urllib.parse.quote(runtime_arn, safe='')}/invocations"
        "?qualifier=DEFAULT"
    )

    config = {
        "agent_name": AGENT_NAME,
        "runtime_id": runtime_id,
        "runtime_arn": runtime_arn,
        "endpoint_url": endpoint_url,
        "discovery_url": discovery_url,
        "tenant_id": tenant_id,
        "audience": audience,
        "region": REGION,
        "role_arn": role_arn,
        "s3_bucket": s3_info["bucket"],
    }
    with open(RUNTIME_CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    print(f"  Config saved to {RUNTIME_CONFIG_FILE}")
    return config


# ── Step 4: Get Entra ID Bearer Token ─────────────────────────────────────────


def get_entra_token() -> str:
    """Acquire an access token from Entra ID using client credentials (M2M)."""
    tenant_id = os.environ.get("ENTRA_TENANT_ID")
    client_id = os.environ.get("ENTRA_CLIENT_ID")
    client_secret = os.environ.get("ENTRA_CLIENT_SECRET")
    scopes_str = os.environ.get("ENTRA_SCOPES", "")

    if not all([tenant_id, client_id, client_secret, scopes_str]):
        raise ValueError(
            "Set ENTRA_TENANT_ID, ENTRA_CLIENT_ID, ENTRA_CLIENT_SECRET, ENTRA_SCOPES.\n"
            "Scopes example: api://<app-id>/.default"
        )

    authority = f"https://login.microsoftonline.com/{tenant_id}"
    app = msal.ConfidentialClientApplication(
        client_id,
        authority=authority,
        client_credential=client_secret,
    )

    scopes = scopes_str.split()
    result = app.acquire_token_for_client(scopes=scopes)

    if "access_token" not in result:
        raise RuntimeError(
            f"Failed to acquire token: {result.get('error_description')}"
        )

    print("  Entra ID token acquired successfully")
    return result["access_token"]


# ── Step 5: Test Agent Invocation ─────────────────────────────────────────────


def test_agent(endpoint_url: str):
    """Test agent invocation — first without auth (should fail), then with auth."""
    session_id = str(uuid.uuid4())

    # Test 1: No auth — should get AccessDeniedException
    print("\n  Test 1: Invoking without bearer token (should fail)...")
    try:
        resp = requests.post(
            endpoint_url,
            headers={"Content-Type": "application/json"},
            json={"prompt": "hello"},
            timeout=30,
        )
        if resp.status_code in (401, 403):
            print(f"  Expected auth failure: HTTP {resp.status_code}")
        else:
            print(f"  Unexpected status {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"  Request error (may indicate auth failure): {e}")

    # Test 2: With valid Entra token
    print("\n  Test 2: Invoking with valid Entra ID bearer token...")
    bearer_token = get_entra_token()

    resp = requests.post(
        endpoint_url,
        headers={
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json",
            "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id,
        },
        json={"prompt": "Hello! I am testing Entra ID inbound authentication."},
        timeout=120,
    )
    resp.raise_for_status()
    print(f"  Agent responded: {resp.text[:300]}")

    # Test 3: Continue same session
    print("\n  Test 3: Continuing session (same session ID)...")
    resp2 = requests.post(
        endpoint_url,
        headers={
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json",
            "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id,
        },
        json={"prompt": "What was my previous message?"},
        timeout=120,
    )
    resp2.raise_for_status()
    print(f"  Agent responded: {resp2.text[:300]}")


# ── Step 6: Cleanup ────────────────────────────────────────────────────────────


def cleanup():
    """Delete all created resources."""
    try:
        with open(RUNTIME_CONFIG_FILE) as f:
            config = json.load(f)
    except FileNotFoundError:
        print("  No config file found. Nothing to clean up.")
        return

    control = boto3.client("bedrock-agentcore-control", region_name=config["region"])
    iam = boto3.client("iam", region_name=config["region"])
    s3 = boto3.client("s3", region_name=config["region"])

    try:
        control.delete_agent_runtime(agentRuntimeId=config["runtime_id"])
        print(f"  Deleted runtime: {config['agent_name']} ✓")
    except Exception as e:
        print(f"  Runtime delete error: {e}")

    role_name = config["role_arn"].split("/")[-1]
    try:
        for policy in iam.list_role_policies(RoleName=role_name)["PolicyNames"]:
            iam.delete_role_policy(RoleName=role_name, PolicyName=policy)
        iam.delete_role(RoleName=role_name)
        print(f"  Deleted IAM role: {role_name} ✓")
    except Exception as e:
        print(f"  Role delete error: {e}")

    try:
        bucket = config["s3_bucket"]
        objs = s3.list_objects_v2(Bucket=bucket).get("Contents", [])
        for obj in objs:
            s3.delete_object(Bucket=bucket, Key=obj["Key"])
        s3.delete_bucket(Bucket=bucket)
        print(f"  Deleted S3 bucket: {bucket} ✓")
    except Exception as e:
        print(f"  S3 cleanup error: {e}")


# ── Main ───────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="AgentCore Runtime with Entra ID inbound auth"
    )
    parser.add_argument(
        "--cleanup", action="store_true", help="Delete created resources"
    )
    parser.add_argument(
        "--test-only",
        action="store_true",
        help="Only run tests using existing runtime_config.json",
    )
    args = parser.parse_args()

    if args.cleanup:
        print("\n=== Cleaning Up ===")
        cleanup()
        return

    if args.test_only:
        with open(RUNTIME_CONFIG_FILE) as f:
            config = json.load(f)
        test_agent(config["endpoint_url"])
        return

    print("=== AgentCore Runtime: Entra ID Inbound Auth ===\n")

    role_name = f"agentcore-entra-inbound-{ACCOUNT_ID}-role"

    print("=== Step 1: Creating IAM Execution Role ===")
    role_arn = create_execution_role(role_name)

    print("\n=== Step 2: Uploading Agent Code to S3 ===")
    s3_info = upload_agent_to_s3()

    print("\n=== Step 3: Creating AgentCore Runtime with Entra JWT Authorizer ===")
    config = create_runtime(role_arn, s3_info)

    print("\n=== Step 4: Testing Agent Invocation ===")
    test_agent(config["endpoint_url"])

    print("\n=== Summary ===")
    print(f"  Runtime ARN: {config['runtime_arn']}")
    print(f"  Discovery URL: {config['discovery_url']}")
    print(f"  Audience: {config['audience']}")
    print("\n  To clean up: python entra_id_inbound_auth.py --cleanup")


if __name__ == "__main__":
    main()

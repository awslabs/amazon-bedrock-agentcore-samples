"""
Okta Inbound + Outbound Auth with AgentCore Runtime and Gateway.

Demonstrates a full Okta OAuth integration:
- Inbound Auth: AgentCore Runtime validates Okta JWT tokens
- Outbound Auth: Agent uses USER_FEDERATION flow to access a protected API
  through AgentCore Gateway using Okta scopes

Architecture:
    ┌──────────────────────────────────────────────────────────────────────┐
    │  User → Flask OAuth Server → Okta → access_token                    │
    │  User + access_token → AgentCore Runtime (Okta JWT validated)        │
    │  Runtime → @requires_access_token → Gateway (Okta JWT)               │
    │  Gateway → Travel Plans Lambda (returns mock travel data)            │
    └──────────────────────────────────────────────────────────────────────┘

Usage:
    python okta_gateway_auth.py
    python okta_gateway_auth.py --cleanup

Prerequisites:
    - AWS CLI configured
    - Okta developer account with:
        - App integration: OIDC Web Application
          Redirect URLs: http://127.0.0.1:5000/callback, https://bedrock-agentcore.{region}.amazonaws.com/...
          Scopes: okta.myAccount.read
        - Authorization server: custom audience + okta.myAccount.read scope
    - pip install -r requirements.txt
    - Set environment variables:
        OKTA_CLIENT_ID       - Application Client ID
        OKTA_CLIENT_SECRET   - Application Client Secret
        OKTA_AUDIENCE        - Audience value from Okta authorization server
        OKTA_DISCOVERY_URL   - https://{your-domain}/oauth2/default/.well-known/openid-configuration
        OKTA_AUTHORIZATION_URL - https://{your-domain}/oauth2/default/v1/authorize
        OKTA_TOKEN_URL       - https://{your-domain}/oauth2/default/v1/token
        OKTA_GATEWAY_URL     - AgentCore Gateway URL (set after gateway creation)
        OKTA_PROVIDER_NAME   - Credential provider name (set after provider creation)
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
import requests
from boto3.session import Session

# ── Configuration ─────────────────────────────────────────────────────────────

LAMBDA_NAME = f"okta-travel-lambda-{int(time.time()) % 100000}"
LAMBDA_ROLE_NAME = f"okta-travel-lambda-role-{int(time.time()) % 100000}"
GATEWAY_ROLE_NAME = f"okta-travel-gateway-role-{int(time.time()) % 100000}"
GATEWAY_NAME = f"okta-travel-gateway-{int(time.time()) % 100000}"
PROVIDER_NAME = f"okta-travel-provider-{int(time.time()) % 100000}"
AGENT_NAME = f"okta_travel_agent_{int(time.time()) % 100000}"
AGENT_FILE = "my_agent_mcp.py"
CONFIG_FILE = "okta_gateway_config.json"

# ── AWS Setup ──────────────────────────────────────────────────────────────────

session = Session()
REGION = session.region_name or "us-west-2"
ACCOUNT_ID = session.client("sts").get_caller_identity()["Account"]

print(f"Region:  {REGION}")
print(f"Account: {ACCOUNT_ID}")


# ── Lambda Function Code (Travel Plans API) ────────────────────────────────────

LAMBDA_CODE = """
import json

MOCK_TRAVEL_PLANS = [
    {
        "id": "plan-001", "user_id": "user-123", "email": "john.doe@example.com",
        "destination": "Paris, France", "departure_date": "2024-03-15",
        "return_date": "2024-03-22", "accommodation": "Hotel Le Marais",
        "activities": ["Eiffel Tower", "Louvre Museum", "Seine River Cruise"],
        "budget": 2500.00, "status": "confirmed"
    },
    {
        "id": "plan-002", "user_id": "user-123", "email": "john.doe@example.com",
        "destination": "Tokyo, Japan", "departure_date": "2024-05-10",
        "return_date": "2024-05-20", "accommodation": "Tokyo Grand Hotel",
        "activities": ["Mount Fuji", "Sensoji Temple", "Shibuya Crossing"],
        "budget": 3500.00, "status": "planned"
    },
    {
        "id": "plan-003", "user_id": "user-456", "email": "jane.smith@example.com",
        "destination": "New York, USA", "departure_date": "2024-04-01",
        "return_date": "2024-04-07", "accommodation": "Manhattan Plaza Hotel",
        "activities": ["Statue of Liberty", "Central Park", "Broadway Show"],
        "budget": 2000.00, "status": "confirmed"
    },
]

def lambda_handler(event, context):
    query_params = event.get("queryStringParameters") or {}
    user_id = query_params.get("user_id")
    email = query_params.get("email")

    if not user_id and not email:
        return {"statusCode": 400, "body": json.dumps({"error": "user_id or email required"})}

    plans = [
        p for p in MOCK_TRAVEL_PLANS
        if (user_id and p["user_id"] == user_id) or (email and p["email"].lower() == email.lower())
    ]

    if plans:
        return {"statusCode": 200, "body": json.dumps({"count": len(plans), "travel_plans": plans})}
    return {"statusCode": 404, "body": json.dumps({"message": "No plans found", "travel_plans": []})}
"""


# ── Agent Code (MCP Client against Gateway) ───────────────────────────────────


def get_agent_code(gateway_url: str, provider_name: str) -> str:
    return f'''import json
from mcp.client.streamable_http import streamablehttp_client
from strands import Agent
from strands.tools.mcp import MCPClient
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.identity.auth import requires_access_token

WELCOME_MESSAGE = "Welcome to the Travel Assistant! How can I help you today?"
SYSTEM_PROMPT = """You are a helpful travel support assistant.
When provided with a customer email, gather all necessary info and prepare the response.
When asked about existing travel plans, look for it and customize the summary."""

okta_access_token = None
app = BedrockAgentCoreApp()

@requires_access_token(
    provider_name="{provider_name}",
    scopes=["okta.myAccount.read"],
    auth_flow="USER_FEDERATION",
    on_auth_url=lambda x: print("\\nAuthorization URL:\\n" + x),
    force_authentication=False,
)
async def need_token_3LO_async(*, access_token: str) -> str:
    global okta_access_token
    okta_access_token = access_token
    return access_token

async def agent_task(user_message: str):
    global okta_access_token
    okta_access_token = await need_token_3LO_async(access_token="")

    mcp_client = MCPClient(lambda: streamablehttp_client(
        "{gateway_url}",
        headers={{"Authorization": f"Bearer {{okta_access_token}}"}},
    ))
    with mcp_client:
        agent = Agent(tools=mcp_client.list_tools_sync())
        response = agent(user_message)
        return response.message["content"][0]["text"]

@app.entrypoint
async def invoke(payload):
    user_message = payload.get("prompt", "No prompt found.")
    result = await agent_task(user_message)
    return result

if __name__ == "__main__":
    app.run()
'''


# ── Step 1: Create Lambda Function ────────────────────────────────────────────


def create_lambda() -> tuple:
    """Create IAM role + Lambda function for travel plans API."""
    iam = boto3.client("iam", region_name=REGION)
    lam = boto3.client("lambda", region_name=REGION)

    trust = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "lambda.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                }
            ],
        }
    )
    policy = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                    ],
                    "Resource": "arn:aws:logs:*:*:*",
                }
            ],
        }
    )

    try:
        r = iam.create_role(RoleName=LAMBDA_ROLE_NAME, AssumeRolePolicyDocument=trust)
        lambda_role_arn = r["Role"]["Arn"]
        iam.put_role_policy(
            RoleName=LAMBDA_ROLE_NAME, PolicyName="logs", PolicyDocument=policy
        )
        time.sleep(10)
        print(f"  Created Lambda role: {LAMBDA_ROLE_NAME}")
    except iam.exceptions.EntityAlreadyExistsException:
        lambda_role_arn = iam.get_role(RoleName=LAMBDA_ROLE_NAME)["Role"]["Arn"]

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("lambda_function.py", LAMBDA_CODE)
    buf.seek(0)

    try:
        resp = lam.create_function(
            FunctionName=LAMBDA_NAME,
            Runtime="python3.12",
            Role=lambda_role_arn,
            Handler="lambda_function.lambda_handler",
            Code={"ZipFile": buf.read()},
        )
        lambda_arn = resp["FunctionArn"]
        print(f"  Created Lambda: {LAMBDA_NAME}")
    except lam.exceptions.ResourceConflictException:
        lambda_arn = lam.get_function(FunctionName=LAMBDA_NAME)["Configuration"][
            "FunctionArn"
        ]
        print(f"  Reusing Lambda: {LAMBDA_NAME}")

    return lambda_arn, lambda_role_arn


# ── Step 2: Create Okta Credential Provider ───────────────────────────────────


def create_credential_provider() -> dict:
    """Create CustomOauth2 credential provider for Okta."""
    client_id = os.environ.get("OKTA_CLIENT_ID")
    client_secret = os.environ.get("OKTA_CLIENT_SECRET")
    discovery_url = os.environ.get("OKTA_DISCOVERY_URL")

    if not all([client_id, client_secret, discovery_url]):
        raise ValueError("Set OKTA_CLIENT_ID, OKTA_CLIENT_SECRET, OKTA_DISCOVERY_URL.")

    control = boto3.client("bedrock-agentcore-control", region_name=REGION)

    try:
        resp = control.create_oauth2_credential_provider(
            name=PROVIDER_NAME,
            credentialProviderVendor="CustomOauth2",
            oauth2ProviderConfigInput={
                "customOauth2ProviderConfig": {
                    "oauthDiscovery": {"discoveryUrl": discovery_url},
                    "clientId": client_id,
                    "clientSecret": client_secret,
                }
            },
        )
        provider_arn = resp["credentialProviderArn"]
        callback_url = resp["callbackUrl"]
        print(f"  Created credential provider: {PROVIDER_NAME}")
    except control.exceptions.ConflictException:
        resp = control.get_oauth2_credential_provider(name=PROVIDER_NAME)
        provider_arn = resp["credentialProviderArn"]
        callback_url = resp["callbackUrl"]
        print(f"  Reusing credential provider: {PROVIDER_NAME}")

    print(f"  Provider ARN: {provider_arn}")
    print(f"  Callback URL (add to Okta app redirect URIs): {callback_url}")
    return {"provider_arn": provider_arn, "callback_url": callback_url}


# ── Step 3: Create Gateway with Okta JWT Auth ─────────────────────────────────


def create_gateway(lambda_arn: str) -> dict:
    """Create AgentCore Gateway with Okta inbound auth and Lambda target."""
    discovery_url = os.environ.get("OKTA_DISCOVERY_URL")
    client_id = os.environ.get("OKTA_CLIENT_ID")
    audience = os.environ.get("OKTA_AUDIENCE")

    if not all([discovery_url, client_id, audience]):
        raise ValueError("Set OKTA_DISCOVERY_URL, OKTA_CLIENT_ID, OKTA_AUDIENCE.")

    iam = boto3.client("iam", region_name=REGION)
    trust = json.dumps(
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
        r = iam.create_role(RoleName=GATEWAY_ROLE_NAME, AssumeRolePolicyDocument=trust)
        gateway_role_arn = r["Role"]["Arn"]
        iam.put_role_policy(
            RoleName=GATEWAY_ROLE_NAME,
            PolicyName="invoke-lambda",
            PolicyDocument=json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Action": "lambda:InvokeFunction",
                            "Resource": lambda_arn,
                        }
                    ],
                }
            ),
        )
        time.sleep(5)
        print(f"  Created Gateway role: {GATEWAY_ROLE_NAME}")
    except iam.exceptions.EntityAlreadyExistsException:
        gateway_role_arn = iam.get_role(RoleName=GATEWAY_ROLE_NAME)["Role"]["Arn"]

    control = boto3.client("bedrock-agentcore-control", region_name=REGION)

    try:
        resp = control.create_gateway(
            name=GATEWAY_NAME,
            roleArn=gateway_role_arn,
            protocolType="MCP",
            authorizerType="CUSTOM_JWT",
            authorizerConfiguration={
                "customJWTAuthorizer": {
                    "discoveryUrl": discovery_url,
                    "allowedClients": [client_id],
                    "allowedAudience": [audience],
                }
            },
        )
        gateway_id = resp["gatewayId"]
        gateway_url = resp["gatewayUrl"]
        print(f"  Created Gateway: {GATEWAY_NAME}")
    except control.exceptions.ConflictException:
        for gw in control.list_gateways().get("gateways", []):
            if gw["name"] == GATEWAY_NAME:
                gateway_id, gateway_url = gw["gatewayId"], gw["gatewayUrl"]
                break

    # Create Lambda target with outbound Okta credential provider
    api_spec = [
        {
            "name": "get_travel_plans",
            "description": "Get travel plans for a user by user_id or email",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "User ID"},
                    "email": {"type": "string", "description": "User email"},
                },
            },
        }
    ]

    target_resp = control.create_gateway_target(
        gatewayIdentifier=gateway_id,
        name="TravelPlansLambda",
        description="Travel plans Lambda target with Okta outbound auth",
        targetConfiguration={
            "mcp": {
                "lambda": {
                    "lambdaArn": lambda_arn,
                    "toolSchema": {"inlinePayload": api_spec},
                }
            }
        },
        credentialProviderConfigurations=[
            {
                "credentialProviderType": "OAUTH",
                "oauthCredentialProvider": {
                    "providerArn": os.environ.get("OKTA_PROVIDER_ARN", ""),
                    "scopes": ["okta.myAccount.read"],
                },
            }
        ],
    )
    print("  Created Gateway target: TravelPlansLambda")
    print(f"  Gateway URL: {gateway_url}")

    return {
        "gateway_id": gateway_id,
        "gateway_url": gateway_url,
        "target_id": target_resp["targetId"],
        "gateway_role_arn": gateway_role_arn,
    }


# ── Step 4: Deploy Agent to Runtime ───────────────────────────────────────────


def deploy_agent(gateway_url: str) -> dict:
    """Deploy my_agent_mcp.py to AgentCore Runtime with Okta inbound auth."""
    discovery_url = os.environ.get("OKTA_DISCOVERY_URL")
    client_id = os.environ.get("OKTA_CLIENT_ID")
    audience = os.environ.get("OKTA_AUDIENCE")

    iam = boto3.client("iam", region_name=REGION)
    role_name = f"agentcore-okta-agent-{ACCOUNT_ID}-role"
    trust = json.dumps(
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
        r = iam.create_role(RoleName=role_name, AssumeRolePolicyDocument=trust)
        role_arn = r["Role"]["Arn"]
        iam.put_role_policy(
            RoleName=role_name,
            PolicyName="agent-policy",
            PolicyDocument=json.dumps(
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
                            "Action": ["bedrock-agentcore:GetResourceOauth2Token"],
                            "Resource": "*",
                        },
                        {
                            "Effect": "Allow",
                            "Action": ["secretsmanager:GetSecretValue"],
                            "Resource": "arn:aws:secretsmanager:*:*:secret:bedrock-agentcore*",
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
                    ],
                }
            ),
        )
        time.sleep(5)
        print(f"  Created agent role: {role_name}")
    except iam.exceptions.EntityAlreadyExistsException:
        role_arn = iam.get_role(RoleName=role_name)["Role"]["Arn"]

    # Upload to S3
    agent_code = get_agent_code(gateway_url, PROVIDER_NAME)
    s3 = boto3.client("s3", region_name=REGION)
    bucket_name = f"agentcore-okta-agent-{ACCOUNT_ID}-{REGION}"
    try:
        if REGION == "us-east-1":
            s3.create_bucket(Bucket=bucket_name)
        else:
            s3.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={"LocationConstraint": REGION},
            )
    except s3.exceptions.BucketAlreadyOwnedByYou:
        pass

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(AGENT_FILE, agent_code)
        zf.writestr("requirements.txt", "strands-agents\nbedrock-agentcore\nmcp\n")
    buf.seek(0)
    s3_key = f"agents/{AGENT_NAME}/agent.zip"
    s3.put_object(Bucket=bucket_name, Key=s3_key, Body=buf.read())

    control = boto3.client("bedrock-agentcore-control", region_name=REGION)
    resp = control.create_agent_runtime(
        agentRuntimeName=AGENT_NAME,
        agentRuntimeArtifact={
            "containerConfiguration": {
                "containerUri": (
                    f"{ACCOUNT_ID}.dkr.ecr.{REGION}.amazonaws.com/"
                    "bedrock-agentcore/managed/runtimes/python3.13:latest"
                ),
            }
        },
        roleArn=role_arn,
        networkConfiguration={"networkMode": "PUBLIC"},
        authorizerConfiguration={
            "customJWTAuthorizer": {
                "discoveryUrl": discovery_url,
                "allowedClients": [client_id],
                "allowedAudience": [audience],
            }
        },
        codeConfiguration={
            "code": {
                "s3": {"uri": f"s3://{bucket_name}/{s3_key}", "entryPoint": AGENT_FILE}
            }
        },
    )

    runtime_id = resp["agentRuntimeId"]
    runtime_arn = resp["agentRuntimeArn"]
    print(f"  Created runtime: {AGENT_NAME} ({runtime_id})")

    print("  Waiting for READY...")
    while True:
        s = control.get_agent_runtime(agentRuntimeId=runtime_id).get(
            "status", "UNKNOWN"
        )
        print(f"    Status: {s}")
        if s == "READY":
            break
        if s in ("CREATE_FAILED", "DELETE_FAILED", "UPDATE_FAILED"):
            raise RuntimeError(f"Runtime failed: {s}")
        time.sleep(15)

    endpoint_url = (
        f"https://bedrock-agentcore.{REGION}.amazonaws.com"
        f"/runtimes/{urllib.parse.quote(runtime_arn, safe='')}/invocations"
        "?qualifier=DEFAULT"
    )
    return {
        "runtime_id": runtime_id,
        "runtime_arn": runtime_arn,
        "endpoint_url": endpoint_url,
        "role_arn": role_arn,
        "s3_bucket": bucket_name,
    }


# ── Step 5: Get Token via Flask OAuth Server ──────────────────────────────────


def get_okta_token_via_flask():
    """
    Instructions for getting an Okta token via the Flask OAuth server.
    In production, run this server process to obtain the bearer token.
    """
    print("\n  To get an Okta authorization code token:")
    print("  1. Run the Flask OAuth server in a separate terminal:")
    print('     python -c "')
    print("     import os, requests, secrets")
    print("     from flask import Flask, redirect, request, session")
    print("     # See okta_flask_oauth.py for full implementation")
    print('     "')
    print("  2. Browse to http://127.0.0.1:5000 and login with Okta")
    print("  3. Copy the access token from the server output")
    print("  4. Set OKTA_BEARER_TOKEN=<token> and re-run with --test-only")
    print()
    print("  Alternatively, for M2M testing:")
    print("  Use client_credentials grant with OKTA_TOKEN_URL if your Okta")
    print("  authorization server allows it.")


# ── Step 6: Test Agent ────────────────────────────────────────────────────────


def test_agent(endpoint_url: str, bearer_token: str):
    """Invoke the agent with a valid Okta bearer token."""
    session_id = f"okta-gateway-session-{uuid.uuid4().hex[:8]}"

    resp = requests.post(
        endpoint_url,
        headers={
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json",
            "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id,
        },
        json={
            "prompt": "What flights does customer with user id user-123 have scheduled?"
        },
        timeout=120,
    )
    resp.raise_for_status()
    print(f"  Agent response: {resp.text[:500]}")


# ── Cleanup ────────────────────────────────────────────────────────────────────


def cleanup():
    """Delete all created resources."""
    try:
        with open(CONFIG_FILE) as f:
            config = json.load(f)
    except FileNotFoundError:
        print("  No config file found.")
        return

    control = boto3.client("bedrock-agentcore-control", region_name=REGION)
    lam = boto3.client("lambda", region_name=REGION)
    iam = boto3.client("iam", region_name=REGION)
    s3 = boto3.client("s3", region_name=REGION)

    for target_id in config.get("target_ids", []):
        try:
            control.delete_gateway_target(
                gatewayIdentifier=config["gateway_id"], targetId=target_id
            )
            print(f"  Deleted target: {target_id} ✓")
        except Exception as e:
            print(f"  Target delete: {e}")

    try:
        control.delete_gateway(gatewayIdentifier=config["gateway_id"])
        print(f"  Deleted Gateway: {config['gateway_name']} ✓")
    except Exception as e:
        print(f"  Gateway delete: {e}")

    if config.get("runtime_id"):
        try:
            control.delete_agent_runtime(agentRuntimeId=config["runtime_id"])
            print(f"  Deleted runtime: {config['agent_name']} ✓")
        except Exception as e:
            print(f"  Runtime delete: {e}")

    try:
        control.delete_oauth2_credential_provider(name=config["provider_name"])
        print(f"  Deleted provider: {config['provider_name']} ✓")
    except Exception as e:
        print(f"  Provider delete: {e}")

    try:
        lam.delete_function(FunctionName=config["lambda_name"])
        print(f"  Deleted Lambda: {config['lambda_name']} ✓")
    except Exception as e:
        print(f"  Lambda delete: {e}")

    for role_name in [
        config.get("lambda_role_name"),
        config.get("gateway_role_name"),
        config.get("agent_role_arn", "").split("/")[-1],
    ]:
        if not role_name:
            continue
        try:
            for p in iam.list_role_policies(RoleName=role_name)["PolicyNames"]:
                iam.delete_role_policy(RoleName=role_name, PolicyName=p)
            iam.delete_role(RoleName=role_name)
            print(f"  Deleted role: {role_name} ✓")
        except Exception as e:
            print(f"  Role delete: {e}")

    for bucket in [config.get("s3_bucket")]:
        if not bucket:
            continue
        try:
            for obj in s3.list_objects_v2(Bucket=bucket).get("Contents", []):
                s3.delete_object(Bucket=bucket, Key=obj["Key"])
            s3.delete_bucket(Bucket=bucket)
            print(f"  Deleted S3 bucket: {bucket} ✓")
        except Exception as e:
            print(f"  S3 cleanup: {e}")


# ── Main ───────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="AgentCore Runtime + Gateway with Okta auth"
    )
    parser.add_argument(
        "--cleanup", action="store_true", help="Delete created resources"
    )
    parser.add_argument(
        "--test-only",
        action="store_true",
        help="Test agent using existing config + OKTA_BEARER_TOKEN env var",
    )
    args = parser.parse_args()

    if args.cleanup:
        print("\n=== Cleaning Up ===")
        cleanup()
        return

    if args.test_only:
        with open(CONFIG_FILE) as f:
            config = json.load(f)
        bearer_token = os.environ.get("OKTA_BEARER_TOKEN")
        if not bearer_token:
            get_okta_token_via_flask()
            return
        test_agent(config["endpoint_url"], bearer_token)
        return

    print("=== AgentCore Runtime + Gateway: Okta Inbound + Outbound Auth ===\n")

    print("=== Step 1: Creating Lambda Function ===")
    lambda_arn, lambda_role_arn = create_lambda()

    print("\n=== Step 2: Creating Okta Credential Provider ===")
    provider_info = create_credential_provider()

    print("\n=== Step 3: Creating AgentCore Gateway with Okta Inbound Auth ===")
    gateway_info = create_gateway(lambda_arn)

    print("\n=== Step 4: Deploying Agent to Runtime ===")
    agent_info = deploy_agent(gateway_info["gateway_url"])

    config = {
        "gateway_name": GATEWAY_NAME,
        "gateway_id": gateway_info["gateway_id"],
        "gateway_url": gateway_info["gateway_url"],
        "lambda_name": LAMBDA_NAME,
        "lambda_arn": lambda_arn,
        "lambda_role_name": LAMBDA_ROLE_NAME,
        "gateway_role_name": GATEWAY_ROLE_NAME,
        "provider_name": PROVIDER_NAME,
        "agent_name": AGENT_NAME,
        "runtime_id": agent_info["runtime_id"],
        "runtime_arn": agent_info["runtime_arn"],
        "endpoint_url": agent_info["endpoint_url"],
        "agent_role_arn": agent_info["role_arn"],
        "s3_bucket": agent_info["s3_bucket"],
        "target_ids": [gateway_info["target_id"]],
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

    print("\n=== Step 5: How to Get an Okta Token ===")
    get_okta_token_via_flask()

    print("\n=== Summary ===")
    print(f"  Gateway: {GATEWAY_NAME} — {gateway_info['gateway_url']}")
    print(f"  Agent Runtime: {AGENT_NAME}")
    print(f"  Credential Provider: {PROVIDER_NAME}")
    print(f"  Callback URL (register in Okta): {provider_info['callback_url']}")
    print(
        "\n  To test: OKTA_BEARER_TOKEN=<token> python okta_gateway_auth.py --test-only"
    )
    print("  To clean up: python okta_gateway_auth.py --cleanup")


if __name__ == "__main__":
    main()

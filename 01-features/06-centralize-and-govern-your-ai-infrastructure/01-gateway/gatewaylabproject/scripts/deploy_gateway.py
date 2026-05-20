"""Create an AgentCore Gateway via boto3 with optional streaming and sessions.

Used by tutorials that need features the AgentCore CLI doesn't yet support
(streamingConfiguration, sessionConfiguration, supportedVersions).

Requires COGNITO_STACK_NAME in environment.

Usage:
    uv run python scripts/deploy_gateway.py --name streaming-gateway --streaming
    uv run python scripts/deploy_gateway.py --name session-gateway --sessions
    uv run python scripts/deploy_gateway.py --name elicitation-gateway --streaming --sessions
    uv run python scripts/deploy_gateway.py --name my-gateway --streaming --sessions --search-type SEMANTIC
"""

import argparse
import os
import sys
import time

import boto3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from gateway_admin import GatewayBoto3Client


def load_env(env_file):
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key, value)


def get_required_env(key):
    val = os.environ.get(key)
    if not val:
        print(f"ERROR: {key} not set. Export it or add to .env")
        sys.exit(1)
    return val


def main():
    parser = argparse.ArgumentParser(
        description="Create an AgentCore Gateway via boto3"
    )
    parser.add_argument("--name", required=True, help="Gateway name")
    parser.add_argument(
        "--streaming", action="store_true", help="Enable response streaming"
    )
    parser.add_argument("--sessions", action="store_true", help="Enable sessions")
    parser.add_argument(
        "--session-timeout",
        type=int,
        default=3600,
        help="Session timeout in seconds (default: 3600)",
    )
    parser.add_argument(
        "--search-type", default=None, help="Search type (e.g., SEMANTIC)"
    )
    parser.add_argument(
        "--interceptor-arn",
        default=None,
        help="Lambda ARN for interceptor (attaches at REQUEST or RESPONSE)",
    )
    parser.add_argument(
        "--interceptor-point",
        default="RESPONSE",
        help="Interception point: REQUEST or RESPONSE (default: RESPONSE)",
    )
    parser.add_argument(
        "--lambda-targets",
        action="store_true",
        help="Add lambda:InvokeFunction permission to gateway role",
    )
    parser.add_argument(
        "--env-file",
        default=None,
        help="Path to .env file for reading/writing (default: scripts/<name>/.env)",
    )
    args = parser.parse_args()

    env_file = args.env_file
    if not env_file:
        script_dir = os.path.join(
            os.path.dirname(__file__),
            args.name.replace("-gateway", "").replace("gateway", ""),
        )
        if os.path.isdir(script_dir):
            env_file = os.path.join(script_dir, ".env")
        else:
            env_file = os.path.join(os.path.dirname(__file__), ".env")

    load_env(env_file)

    cognito_stack = get_required_env("COGNITO_STACK_NAME")

    region = boto3.Session().region_name
    admin = GatewayBoto3Client(region=region)
    control = admin.client
    cfn = boto3.client("cloudformation", region_name=region)

    outputs = {
        o["OutputKey"]: o["OutputValue"]
        for o in cfn.describe_stacks(StackName=cognito_stack)["Stacks"][0]["Outputs"]
    }
    discovery_url = outputs["DiscoveryUrl"]
    gw_client_id = outputs["GatewayClientId"]

    print(f"--- Creating gateway IAM role for '{args.name}' ---")
    role_arn = admin.create_gateway_role(
        args.name, oauth_targets=True, lambda_targets=args.lambda_targets
    )

    mcp_config: dict = {"supportedVersions": ["2025-11-25"]}
    if args.streaming:
        mcp_config["streamingConfiguration"] = {"enableResponseStreaming": True}
    if args.sessions:
        mcp_config["sessionConfiguration"] = {
            "sessionTimeoutInSeconds": args.session_timeout
        }
    if args.search_type:
        mcp_config["searchType"] = args.search_type

    features = []
    if args.streaming:
        features.append("streaming")
    if args.sessions:
        features.append("sessions")
    if args.interceptor_arn:
        features.append(f"interceptor:{args.interceptor_point}")
    feature_str = " + ".join(features) if features else "base"

    print(f"\n--- Creating AgentCore Gateway '{args.name}' ({feature_str}) ---")
    create_kwargs: dict = {
        "name": args.name,
        "roleArn": role_arn,
        "protocolType": "MCP",
        "authorizerType": "CUSTOM_JWT",
        "authorizerConfiguration": {
            "customJWTAuthorizer": {
                "allowedClients": [gw_client_id],
                "discoveryUrl": discovery_url,
            }
        },
        "protocolConfiguration": {"mcp": mcp_config},
        "exceptionLevel": "DEBUG",
    }

    if args.interceptor_arn:
        create_kwargs["interceptorConfigurations"] = [
            {
                "interceptor": {"lambda": {"arn": args.interceptor_arn}},
                "interceptionPoints": [args.interceptor_point],
                "inputConfiguration": {"passRequestHeaders": True},
            }
        ]

    gw_resp = control.create_gateway(**create_kwargs)
    gateway_id = gw_resp["gatewayId"]
    gateway_url = gw_resp["gatewayUrl"]
    print(f"  Gateway ID:  {gateway_id}")
    print(f"  Gateway URL: {gateway_url}")

    print("\n  Waiting for gateway to become READY...")
    while True:
        time.sleep(10)
        gw = control.get_gateway(gatewayIdentifier=gateway_id)
        status = gw["status"]
        print(f"    Status: {status}")
        if status in ["READY", "FAILED", "CREATE_FAILED"]:
            break

    env_vars: dict[str, str] = {}
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    env_vars[key] = value
    env_vars["GATEWAY_ID"] = gateway_id
    env_vars["GATEWAY_URL"] = gateway_url
    os.makedirs(os.path.dirname(env_file), exist_ok=True)
    with open(env_file, "w") as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")
    print(f"\n  Saved GATEWAY_ID and GATEWAY_URL to {env_file}")


if __name__ == "__main__":
    main()

"""
Test script: Invokes the deployed AgentCore Runtime with a Cognito JWT bearer token.

Demonstrates:
  1. Invoke WITHOUT bearer token -> AccessDeniedException (expected)
  2. Invoke WITH valid Cognito bearer token -> success

Usage:
    python invoke.py [prompt]

    prompt defaults to "What is the weather in Seattle?"
"""

import boto3
import json
import subprocess
import sys


def get_bearer_token(config: dict) -> str:
    """Get a fresh Cognito access token."""
    cognito = boto3.client("cognito-idp", region_name=config["region"])
    auth = cognito.initiate_auth(
        ClientId=config["client_id"],
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={
            "USERNAME": config["username"],
            "PASSWORD": config["password"],
        },
    )
    return auth["AuthenticationResult"]["AccessToken"]


def get_agent_arn(region: str) -> str:
    """Read the deployed agent ARN from agentcore status output."""
    result = subprocess.run(
        ["agentcore", "status", "--json"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "agentcore status failed. Ensure the project is deployed:\n"
            f"  {result.stderr}"
        )
    status = json.loads(result.stdout)
    for resource in status.get("resources", []):
        if resource.get("type") == "agent" and resource.get("state") == "deployed":
            arn = resource.get("agentRuntimeArn")
            if arn:
                return arn
    raise ValueError(
        "No deployed agent found. Run 'agentcore deploy -y' first."
    )


def parse_event_stream(response: dict) -> str:
    """Extract text from the boto3 EventStream response."""
    events = []
    for event in response.get("response", []):
        raw = event if isinstance(event, bytes) else event.get("chunk", {}).get("bytes", b"")
        if raw:
            try:
                events.append(json.loads(raw.decode("utf-8")))
            except Exception:
                events.append(raw.decode("utf-8"))
    return str(events)


def main():
    prompt = sys.argv[1] if len(sys.argv) > 1 else "What is the weather in Seattle?"

    # Load Cognito config
    try:
        with open("cognito_config.json") as f:
            config = json.load(f)
    except FileNotFoundError:
        print("ERROR: cognito_config.json not found.")
        print("Run 'python setup_cognito.py' first.")
        sys.exit(1)

    region = config["region"]
    client = boto3.client("bedrock-agentcore", region_name=region)

    print("Resolving deployed agent ARN...")
    agent_arn = get_agent_arn(region)
    print(f"  Agent ARN: {agent_arn}")

    print(f"\nPrompt: '{prompt}'")

    # --- Test 1: No bearer token (should be rejected) ---
    print("\n[Test 1] Invoking WITHOUT bearer token (expect AccessDeniedException)...")
    try:
        resp = client.invoke_agent_runtime(
            agentRuntimeArn=agent_arn,
            runtimeUserId="testuser",
            qualifier="DEFAULT",
            payload=json.dumps({"prompt": prompt}),
        )
        print("  Unexpected success:", resp)
    except client.exceptions.AccessDeniedException as exc:
        print(f"  Correctly rejected: {exc}")
    except Exception as exc:
        print(f"  Error: {type(exc).__name__}: {exc}")

    # --- Test 2: Valid Cognito bearer token ---
    print("\n[Test 2] Invoking WITH valid Cognito bearer token...")
    bearer_token = get_bearer_token(config)
    print(f"  Token obtained (first 20 chars): {bearer_token[:20]}...")

    try:
        resp = client.invoke_agent_runtime(
            agentRuntimeArn=agent_arn,
            runtimeUserId=config["username"],
            qualifier="DEFAULT",
            payload=json.dumps({"prompt": prompt}),
            bearerToken=bearer_token,
        )
        result = parse_event_stream(resp)
        print(f"\nAgent response:\n{result}")
    except Exception as exc:
        print(f"  Error: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()

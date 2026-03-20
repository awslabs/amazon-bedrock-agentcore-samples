"""
Test script: Invokes the M2M + Auth Code agent with a Cognito bearer token.

Tests:
  1. M2M flow  — agent calls internal API using client credentials (no user interaction)
  2. Auth Code — agent accesses Google Calendar on behalf of the user (3LO consent flow)

For the 3LO test, this script:
  - Starts the OAuth2 callback server (localhost:9090)
  - Stores the user's bearer token so session binding can verify identity
  - Invokes the agent (which returns a Google consent URL on first call)
  - Waits for user to complete consent, then re-invokes to retrieve calendar events

Usage:
    # Test M2M flow
    python invoke.py --flow m2m

    # Test Auth Code (3LO) flow
    python invoke.py --flow authcode
"""

import argparse
import json
import subprocess
import sys
import time

import boto3

from oauth2_callback_server import (
    store_token_in_oauth2_callback_server,
    wait_for_oauth2_server_to_be_ready,
    get_oauth2_callback_url,
)


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


def get_agent_arn() -> str:
    result = subprocess.run(
        ["agentcore", "status", "--json"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"agentcore status failed:\n{result.stderr}")
    status = json.loads(result.stdout)
    for resource in status.get("resources", []):
        if resource.get("type") == "agent" and resource.get("state") == "deployed":
            arn = resource.get("agentRuntimeArn")
            if arn:
                return arn
    raise ValueError("No deployed agent found. Run 'agentcore deploy -y' first.")


def parse_event_stream(response: dict) -> str:
    events = []
    for event in response.get("response", []):
        raw = event if isinstance(event, bytes) else event.get("chunk", {}).get("bytes", b"")
        if raw:
            try:
                events.append(json.loads(raw.decode("utf-8")))
            except Exception:
                events.append(raw.decode("utf-8"))
    return str(events)


def invoke(client, agent_arn: str, prompt: str, bearer_token: str, user_id: str, region: str) -> str:
    resp = client.invoke_agent_runtime(
        agentRuntimeArn=agent_arn,
        runtimeUserId=user_id,
        qualifier="DEFAULT",
        payload=json.dumps({"prompt": prompt}),
        bearerToken=bearer_token,
    )
    return parse_event_stream(resp)


def test_m2m(client, agent_arn: str, bearer_token: str, config: dict):
    print("\n=== M2M Flow Test ===")
    print("The agent will call an internal API using client credentials (no user consent needed).")
    prompt = "Check the status of the internal API at /api/v1/status"
    print(f"Prompt: '{prompt}'")

    result = invoke(client, agent_arn, prompt, bearer_token, config["username"], config["region"])
    print(f"\nAgent response:\n{result}")


def test_authcode(client, agent_arn: str, bearer_token: str, config: dict):
    print("\n=== Auth Code (3LO) Flow Test ===")
    print("Starting OAuth2 callback server...")

    server_proc = subprocess.Popen(
        [sys.executable, "oauth2_callback_server.py", "--region", config["region"]],
    )

    try:
        if not wait_for_oauth2_server_to_be_ready():
            print("ERROR: OAuth2 callback server did not start in time.")
            return

        # Store the user's bearer token for session binding
        store_token_in_oauth2_callback_server(bearer_token)
        print(f"  Callback URL: {get_oauth2_callback_url()}")

        # First invocation: triggers consent URL
        prompt = "What is on my Google Calendar today?"
        print(f"\nPrompt: '{prompt}'")
        print("Invoking agent (first call — expect consent URL)...")

        result = invoke(client, agent_arn, prompt, bearer_token, config["username"], config["region"])
        print(f"\nAgent response:\n{result}")

        # If response contains an auth URL, wait for user to complete consent
        if "http" in result.lower() and ("google" in result.lower() or "oauth" in result.lower()):
            print("\nWaiting for you to complete the Google consent flow...")
            print("After authorizing in your browser, press Enter to re-invoke the agent.")
            input()

            print("Re-invoking agent to retrieve calendar events...")
            result2 = invoke(
                client, agent_arn, prompt, bearer_token, config["username"], config["region"]
            )
            print(f"\nAgent response:\n{result2}")

    finally:
        server_proc.terminate()
        server_proc.wait()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--flow",
        choices=["m2m", "authcode", "both"],
        default="both",
        help="Which flow to test (default: both)",
    )
    args = parser.parse_args()

    try:
        with open("cognito_config.json") as f:
            config = json.load(f)
    except FileNotFoundError:
        print("ERROR: cognito_config.json not found. Run 'python setup_cognito.py' first.")
        sys.exit(1)

    print("Getting Cognito bearer token...")
    bearer_token = get_bearer_token(config)
    print(f"  Token obtained (first 20 chars): {bearer_token[:20]}...")

    print("Resolving deployed agent ARN...")
    agent_arn = get_agent_arn()
    print(f"  Agent ARN: {agent_arn}")

    boto_client = boto3.client("bedrock-agentcore", region_name=config["region"])

    if args.flow in ("m2m", "both"):
        test_m2m(boto_client, agent_arn, bearer_token, config)

    if args.flow in ("authcode", "both"):
        test_authcode(boto_client, agent_arn, bearer_token, config)


if __name__ == "__main__":
    main()

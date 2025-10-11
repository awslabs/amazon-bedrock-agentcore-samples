#!/usr/bin/python
from urllib.parse import urlencode
import argparse
import asyncio
import json
import logging
import requests
import sys
import uuid


from utils import (
    generate_pkce_pair,
    get_auth_code_automatically,
    get_aws_info,
    get_nested_stack_name,
    get_ssm_parameter,
    get_stack_output,
    invoke_endpoint,
    load_access_token,
    save_access_token,
)

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """CLI tool to invoke a Bedrock agent by name."""

    parser = argparse.ArgumentParser(description="Agent Runtime CLI Tool")
    parser.add_argument("--prompt", required=True, help="Prompt to send to the agent")
    parser.add_argument(
        "--stack-name",
        default="customer-support-vpc",
        help="CloudFormation stack name (default: customer-support-vpc)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    # Set logging level based on arguments
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.verbose:
        logging.getLogger().setLevel(logging.INFO)
    else:
        logging.getLogger().setLevel(logging.WARNING)

    print("🚀 Agent Runtime CLI Tool")
    print("=" * 30)

    # Get AWS info
    account_id, region = get_aws_info()
    print(f"📋 AWS Account ID: {account_id}")
    print(f"🌍 AWS Region: {region}")

    # Get the nested AgentServerStack name from the parent stack
    print(f"📦 Parent Stack Name: {args.stack_name}")
    agent_stack_name = get_nested_stack_name(
        args.stack_name, "AgentServerStack", region
    )
    print(f"📦 Agent Stack Name: {agent_stack_name}")

    # Get runtime ID and provider name from the nested stack outputs
    runtime_id = get_stack_output(agent_stack_name, "AgentRuntimeId", region)
    # provider_name = get_stack_output(agent_stack_name, "AgentProviderName", region)
    print(f"🤖 Agent Runtime ID: {runtime_id}")
    # print(f"🔐 OAuth2 Provider: {provider_name}")

    # Try to load existing access token
    access_token = load_access_token(runtime_id)

    if access_token:
        print("✅ Using cached access token.")
    else:
        print("🔐 No cached token found. Starting authentication flow...")

        code_verifier, code_challenge = generate_pkce_pair()
        state = str(uuid.uuid4())

        client_id = get_ssm_parameter("/app/customersupportvpc/agentcore/web_client_id")
        cognito_domain = get_ssm_parameter(
            "/app/customersupportvpc/agentcore/cognito_domain"
        )
        redirect_uri = "http://localhost:8080/callback"

        login_params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": "email openid profile",
            "code_challenge_method": "S256",
            "code_challenge": code_challenge,
            "state": state,
        }

        login_url = f"{cognito_domain}/oauth2/authorize?{urlencode(login_params)}"

        # Try automated OAuth flow first
        auth_code = get_auth_code_automatically(login_url)

        # Fallback to manual flow if automation fails
        if not auth_code:
            print("\n🔧 Automated flow failed. Falling back to manual authentication:")
            print("🔐 Open the following URL in a browser to authenticate:")
            print(login_url)
            auth_code = input("📥 Paste the `code` from the redirected URL: ").strip()

        token_url = get_ssm_parameter(
            "/app/customersupportvpc/agentcore/cognito_token_url"
        )
        response = requests.post(
            token_url,
            data={
                "grant_type": "authorization_code",
                "client_id": client_id,
                "code": auth_code,
                "redirect_uri": redirect_uri,
                "code_verifier": code_verifier,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        if response.status_code != 200:
            print(f"❌ Failed to exchange code: {response.text}")
            sys.exit(1)

        access_token = response.json()["access_token"]

        # Save the token for future use
        save_access_token(access_token, runtime_id)
        print("✅ Access token acquired and saved.")

    # agent_arn = runtime_config["agents"][agent_name]["bedrock_agentcore"]["agent_arn"]
    agent_arn = f"arn:aws:bedrock-agentcore:{region}:{account_id}:runtime/{runtime_id}"
    session_id = str(uuid.uuid4())
    print("\n🤖 Starting interactive session with agent. Type 'q' or 'quit' to exit.\n")

    while True:
        user_input = input("👤 You: ").strip()

        if user_input.lower() in ["q", "quit"]:
            print("👋 Goodbye!")
            break

        if not user_input:
            continue

        print("🤖 Assistant: ", end="", flush=True)
        # asyncio.run(
        invoke_endpoint(
            agent_arn=agent_arn,
            payload=json.dumps({"prompt": user_input, "actor_id": "DEFAULT"}),
            bearer_token=access_token,
            session_id=session_id,
            stream=False,
        )
        # )
        print("\n")


if __name__ == "__main__":
    main()

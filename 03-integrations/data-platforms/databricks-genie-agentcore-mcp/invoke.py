"""Verify the gateway locally by asking Genie a question through MCP.

Runs a Strands agent on your machine against the deployed gateway — the fastest
way to confirm inbound auth, outbound auth and the Unity Catalog grants are all
in place before deploying to AgentCore Runtime.

Usage:
    python invoke.py
    python invoke.py "How has monthly active users changed over the last 12 months?"
    python invoke.py --list-tools
"""

import argparse
import json

from bedrock_agentcore_starter_toolkit.operations.gateway.client import GatewayClient
from mcp.client.streamable_http import streamablehttp_client
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient

from config import MODEL_ID, STATE_FILE, SYSTEM_PROMPT

DEFAULT_PROMPT = "What were our top 5 products by revenue last quarter?"


def load_config() -> dict:
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        raise SystemExit(f"{STATE_FILE} not found — run `python deploy.py` first.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "prompt", nargs="?", default=DEFAULT_PROMPT, help="question to ask Genie"
    )
    parser.add_argument(
        "--list-tools",
        action="store_true",
        help="list the tools exposed by the gateway and exit",
    )
    args = parser.parse_args()

    config = load_config()
    gw_client = GatewayClient(region_name=config["region"])

    print("Obtaining Cognito access token (inbound auth)...")
    token = gw_client.get_access_token_for_cognito(config["client_info"])

    mcp_client = MCPClient(
        lambda: streamablehttp_client(
            config["gateway_url"],
            headers={"Authorization": f"Bearer {token}"},
        )
    )

    mcp_client.start()
    try:
        tools = mcp_client.list_tools_sync()
        print(f"Available tools: {[t.tool_name for t in tools]}")
        if args.list_tools:
            return

        agent = Agent(
            model=BedrockModel(model_id=MODEL_ID),
            tools=tools,
            system_prompt=SYSTEM_PROMPT,
        )

        print(f"\nPrompt: {args.prompt}\n")
        # Strands streams the response to stdout as it arrives, so the return
        # value is not printed again here.
        agent(args.prompt)
    finally:
        # MCPClient is a context manager; stop() requires the three exception args.
        mcp_client.stop(None, None, None)
        print("\nMCP client stopped.")


if __name__ == "__main__":
    main()

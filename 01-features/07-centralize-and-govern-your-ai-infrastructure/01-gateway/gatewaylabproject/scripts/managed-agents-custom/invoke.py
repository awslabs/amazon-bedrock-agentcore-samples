"""Demo: Drive a Claude Managed Agents session through the gateway (requests).

Runs the full Managed Agents flow against the CUSTOM HTTP passthrough target:
create an agent, create an environment, start a session, send a user message,
and stream the agent's events back over SSE.

Auth model: the caller presents the Entra ID gateway JWT inbound
(Authorization: Bearer) AND its own Claude key as x-api-key. The gateway
validates the JWT and forwards x-api-key (plus the anthropic-* headers) outbound
to api.anthropic.com. The gateway does not store or inject the Claude key.

Requires in environment or .env:
  GATEWAY_URL    - shared gateway URL (written by deploy_gateway.py)
  TARGET_NAME    - passthrough target name (written by deploy.py)
  BEARER_TOKEN   - Entra ID gateway access token (aud: api://<gateway-client-id>)
  CLAUDE_API_KEY - your Claude API key with Managed Agents beta access

Usage:
    uv run python scripts/managed-agents-custom/invoke.py
"""

import json
import os
import sys

import requests

ANTHROPIC_VERSION = "2023-06-01"
MANAGED_AGENTS_BETA = "managed-agents-2026-04-01"
PROMPT = (
    "Create a Python script that generates the first 20 Fibonacci numbers "
    "and saves them to fibonacci.txt"
)


def load_env():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key, value)


def get_required_env(key):
    val = os.environ.get(key)
    if not val:
        print(f"ERROR: {key} not set. Export it or add to the script .env")
        sys.exit(1)
    return val


def main():
    load_env()

    gateway_url = get_required_env("GATEWAY_URL")
    target_name = get_required_env("TARGET_NAME")
    bearer_token = get_required_env("BEARER_TOKEN")
    claude_api_key = get_required_env("CLAUDE_API_KEY")

    # Path-based routing: the gateway forwards /{target}/{path} to
    # https://api.anthropic.com/{path}. The Entra JWT is the inbound credential;
    # x-api-key is the client's own Claude key, forwarded outbound.
    base = f"{gateway_url.rstrip('/')}/{target_name}"
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "x-api-key": claude_api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "anthropic-beta": MANAGED_AGENTS_BETA,
        "content-type": "application/json",
    }

    print(f"Gateway target base: {base}\n")

    # 1. Create the agent
    print("--- Creating agent ---")
    agent = requests.post(
        f"{base}/v1/agents",
        headers=headers,
        json={
            "name": "Coding Assistant",
            "model": "claude-opus-4-8",
            "system": "You are a helpful coding assistant. Write clean, well-documented code.",
            "tools": [{"type": "agent_toolset_20260401"}],
        },
        timeout=60,
    )
    agent.raise_for_status()
    agent_id = agent.json()["id"]
    print(f"  Agent ID: {agent_id}")

    # 2. Create the environment
    print("--- Creating environment ---")
    env = requests.post(
        f"{base}/v1/environments",
        headers=headers,
        json={
            "name": "quickstart-env",
            "config": {"type": "cloud", "networking": {"type": "unrestricted"}},
        },
        timeout=60,
    )
    env.raise_for_status()
    environment_id = env.json()["id"]
    print(f"  Environment ID: {environment_id}")

    # 3. Start a session
    print("--- Starting session ---")
    sess = requests.post(
        f"{base}/v1/sessions",
        headers=headers,
        json={
            "agent": agent_id,
            "environment_id": environment_id,
            "title": "Quickstart session",
        },
        timeout=60,
    )
    sess.raise_for_status()
    session_id = sess.json()["id"]
    print(f"  Session ID: {session_id}")

    # 4. Send a user message (buffered until the stream attaches)
    print("--- Sending user message ---")
    sent = requests.post(
        f"{base}/v1/sessions/{session_id}/events",
        headers=headers,
        json={
            "events": [
                {
                    "type": "user.message",
                    "content": [{"type": "text", "text": PROMPT}],
                }
            ]
        },
        timeout=60,
    )
    sent.raise_for_status()

    # 5. Open the SSE stream and process events as they arrive
    print("--- Streaming agent events ---\n")
    with requests.get(
        f"{base}/v1/sessions/{session_id}/stream",
        headers={**headers, "Accept": "text/event-stream"},
        stream=True,
        timeout=300,
    ) as stream:
        stream.raise_for_status()
        for line in stream.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            event = json.loads(line[len("data:") :].strip())
            etype = event.get("type")
            if etype == "agent.message":
                for block in event.get("content", []):
                    if block.get("type") == "text":
                        print(block["text"], end="", flush=True)
            elif etype == "agent.tool_use":
                print(f"\n[Using tool: {event.get('name')}]")
            elif etype == "session.status_idle":
                print("\n\nAgent finished.")
                break


if __name__ == "__main__":
    main()

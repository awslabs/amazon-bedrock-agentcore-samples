#!/usr/bin/env python3
"""
Agent smoke test — sends a natural language prompt to the Amazon Bedrock AgentCore Runtime
and prints the response. Tests the full flow: Runtime → Gateway → Lambda → Redaction.

Usage:
  python test/test_agent.py --persona hr-manager --prompt "Find all engineers"
  python test/test_agent.py --persona employee --prompt "Show me John Smith's email"
"""

import argparse
import json
import sys
import uuid

import boto3
import requests

sys.path.insert(0, ".")
from scripts.utils import get_ssm_parameter


def get_token(persona: str) -> str:
    client_id = get_ssm_parameter(f"/app/hrdlp/personas/{persona}/client-id")
    client_secret = get_ssm_parameter(f"/app/hrdlp/personas/{persona}/client-secret")
    token_url = get_ssm_parameter("/app/hrdlp/cognito-token-url")

    if not all([client_id, client_secret, token_url]):
        print(f"ERROR: Credentials for persona '{persona}' not in SSM. Run prereq.sh first.")
        sys.exit(1)

    resp = requests.post(
        token_url,
        data={"grant_type": "client_credentials"},
        auth=(client_id, client_secret),
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def invoke_agent(runtime_url: str, token: str, prompt: str, session_id: str) -> str:
    payload = {"prompt": prompt, "sessionId": session_id}
    resp = requests.post(
        runtime_url,
        json=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        timeout=120,
        stream=True,
    )
    resp.raise_for_status()
    full = ""
    for chunk in resp.iter_content(chunk_size=None, decode_unicode=True):
        if chunk:
            full += chunk
            print(chunk, end="", flush=True)
    print()
    return full


def main():
    parser = argparse.ArgumentParser(description="AgentCore Runtime smoke test")
    parser.add_argument("--persona", default="hr-manager",
                        choices=["hr-manager", "hr-specialist", "employee", "admin"])
    parser.add_argument("--prompt", default="Find all engineers in the company")
    args = parser.parse_args()

    runtime_url = get_ssm_parameter("/app/hrdlp/runtime-url")
    if not runtime_url:
        print("ERROR: Runtime URL not found in SSM (/app/hrdlp/runtime-url). Run agentcore_agent_runtime.py create first.")
        sys.exit(1)

    print(f"\n[test_agent] Persona: {args.persona}")
    print(f"[test_agent] Prompt: {args.prompt}\n")
    print("-" * 60)

    token = get_token(args.persona)
    session_id = str(uuid.uuid4())
    invoke_agent(runtime_url, token, args.prompt, session_id)

    print("-" * 60)
    print("[test_agent] Done.")


if __name__ == "__main__":
    main()

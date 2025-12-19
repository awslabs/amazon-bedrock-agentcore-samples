#!/usr/bin/env python3
"""
Test Agent Remotely

Tests the deployed supervisor agent on AWS Bedrock AgentCore.
Displays raw streaming events for debugging.

Usage:
    uv run --with boto3 --with requests --with colorama tests/test-agent-remote.py
    uv run --with boto3 --with requests --with colorama tests/test-agent-remote.py -q "What is the weather in Paris?"

Requirements:
    - AWS credentials configured
    - Agent deployed (npm run deploy:agent)
    - amplify_outputs.json exists
"""

import sys
import time
import argparse
from pathlib import Path

import requests
from colorama import Fore, Style, init

# Add tests folder to path for utils import
sys.path.insert(0, str(Path(__file__).parent))
from utils import (
    print_msg, print_section, get_agent_config,
    generate_session_id, process_streaming_response, REGION
)

init(autoreset=True)


def invoke_agent(config: dict, prompt: str, user_id: str, session_id: str) -> None:
    """Invoke remote agent and print streaming events."""
    runtime_arn = config["runtime_arn"]
    access_token = config["access_token"]
    
    encoded_arn = requests.utils.quote(runtime_arn, safe="")
    url = f"https://bedrock-agentcore.{REGION}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
        "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id
    }
    
    payload = {
        "prompt": prompt,
        "user_id": user_id,
        "session_id": session_id
    }
    
    response = requests.post(url, headers=headers, json=payload, stream=True, timeout=180)
    
    if response.status_code != 200:
        print_msg(f"HTTP {response.status_code}: {response.text[:500]}", "error")
        return
    
    process_streaming_response(response)


def run_chat(config: dict) -> None:
    """Run interactive chat session."""
    session_id = generate_session_id()
    user_id = "test-user"
    
    print(f"\n{Fore.CYAN}Session ID: {session_id}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Type 'exit' to quit{Style.RESET_ALL}")
    
    while True:
        try:
            prompt = input(f"\n{Fore.CYAN}You:{Style.RESET_ALL} ").strip()
            
            if not prompt:
                continue
            if prompt.lower() in ["exit", "quit"]:
                print(f"\n{Fore.GREEN}Goodbye!{Style.RESET_ALL}")
                break
            
            print(f"\n{Fore.GREEN}Agent:{Style.RESET_ALL}")
            start = time.time()
            invoke_agent(config, prompt, user_id, session_id)
            print(f"\n{Fore.CYAN}[{time.time() - start:.2f}s]{Style.RESET_ALL}")
            
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Fore.GREEN}Goodbye!{Style.RESET_ALL}")
            break


def run_single_query(config: dict, query: str) -> None:
    """Run a single query."""
    session_id = generate_session_id()
    
    print(f"Session ID: {session_id}")
    print(f"Query: {query}\n")
    print("Agent:")
    
    start = time.time()
    invoke_agent(config, query, "test-user", session_id)
    print(f"\n[{time.time() - start:.2f}s]")


def main():
    parser = argparse.ArgumentParser(description="Test remote concierge agent")
    parser.add_argument("--query", "-q", type=str, help="Single query (non-interactive)")
    args = parser.parse_args()
    
    print_section("Concierge Agent - Remote Test")
    
    print_msg("Connecting to deployed agent", "info")
    
    try:
        config = get_agent_config()
        print(f"Deployment ID: {config['deployment_id']}")
        print(f"Runtime ARN: {config['runtime_arn'][:60]}...")
        print_msg("Token obtained", "success")
    except Exception as e:
        print_msg(f"Setup failed: {e}", "error")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    if args.query:
        run_single_query(config, args.query)
    else:
        run_chat(config)


if __name__ == "__main__":
    main()

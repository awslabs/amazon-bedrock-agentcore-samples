"""
MCP (Model Context Protocol) Integration with AgentCore Harness.

Demonstrates how to connect Harness agents to external MCP servers:
  Part 1: Basic MCP integration with Exa search
  Part 2: Multiple MCP tools in one invocation
  Part 3: MCP with authentication (env var pattern)
  Part 4: Error handling for MCP calls
  Part 5: Advanced research assistant using MCP + file operations

Usage:
    python mcp_integration.py

Prerequisites:
    - AWS CLI configured with credentials
    - pip install -r ../../requirements.txt
    - AWS_DEFAULT_REGION environment variable set
    - (Optional) MCP_API_KEY environment variable for authenticated examples
"""

import json
import os
import sys
import time
import uuid
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.iam import create_harness_role, delete_harness_role
from utils.client import get_agentcore_control_client, get_agentcore_client

# ── Configuration ─────────────────────────────────────────────────────────────
MODEL_ID = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
EXA_MCP_URL = "https://mcp.exa.ai/mcp"

# ── Setup ─────────────────────────────────────────────────────────────────────
control = get_agentcore_control_client()
client = get_agentcore_client()

account_id = boto3.client("sts").get_caller_identity()["Account"]
print(f"Account: {account_id}")

# ── Create IAM Role & Harness ─────────────────────────────────────────────────
print("\n=== Setup: IAM Role & Harness ===")
role_arn = create_harness_role()
print(f"Execution Role ARN: {role_arn}")
print("Waiting for IAM propagation...")
time.sleep(10)

HARNESS_NAME = f"MCPIntegration_{uuid.uuid4().hex[:8]}"
resp = control.create_harness(harnessName=HARNESS_NAME, executionRoleArn=role_arn)
harness = resp["harness"]
harness_id = harness["harnessId"]
harness_arn = harness["arn"]
print(f"Harness ID:  {harness_id}")
print(f"Harness ARN: {harness_arn}")

for i in range(12):
    resp = control.get_harness(harnessId=harness_id)
    status = resp["harness"]["status"]
    print(f"  [{i + 1}] {status}")
    if status == "READY":
        print("✅ Harness is ready")
        break
    time.sleep(5)

# ── Helper: stream harness response ──────────────────────────────────────────


def stream_invoke(session_id, prompt, tools, timeout=300):
    """Invoke harness with MCP tools and stream the response."""
    response = client.invoke_harness(
        harnessArn=harness_arn,
        runtimeSessionId=session_id,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        tools=tools,
        model={"bedrockModelConfig": {"modelId": MODEL_ID}},
        timeoutSeconds=timeout,
    )
    result = {"text": "", "tool_uses": [], "errors": []}
    for event in response["stream"]:
        if "contentBlockStart" in event:
            start = event["contentBlockStart"].get("start", {})
            if "toolUse" in start:
                tool_name = start["toolUse"].get("name", "?")
                result["tool_uses"].append(tool_name)
                print(f"\n[Tool: {tool_name}]", flush=True)
        elif "contentBlockDelta" in event:
            delta = event["contentBlockDelta"].get("delta", {})
            if "text" in delta:
                result["text"] += delta["text"]
                print(delta["text"], end="", flush=True)
        elif "messageStop" in event:
            print("\n")
        elif "internalServerException" in event:
            error = event["internalServerException"]
            result["errors"].append(error)
            print(f"\n❌ Error: {error}")
    return result


# ── Part 1: Basic MCP Integration — Exa Search ────────────────────────────────
print("\n=== Part 1: Basic MCP Integration — Exa Search ===")
session1 = str(uuid.uuid4()).upper()
print(f"Session: {session1}\n")

result = stream_invoke(
    session_id=session1,
    prompt=(
        "Search for the latest developments in quantum computing in 2024. "
        "Find 3-5 recent articles and summarize the key breakthroughs."
    ),
    tools=[
        {
            "type": "remote_mcp",
            "name": "exa",
            "config": {"remoteMcp": {"url": EXA_MCP_URL}},
        }
    ],
)
print(f"Tools used: {result['tool_uses']}")

# ── Part 2: Multiple MCP Tools ────────────────────────────────────────────────
print("\n=== Part 2: Multiple MCP Tools ===")
session2 = str(uuid.uuid4()).upper()
print(f"Session: {session2}\n")

result = stream_invoke(
    session_id=session2,
    prompt=(
        "Compare search results from different sources about 'AWS re:Invent 2024 announcements'. "
        "What were the major announcements?"
    ),
    tools=[
        {
            "type": "remote_mcp",
            "name": "exa_search",
            "config": {"remoteMcp": {"url": EXA_MCP_URL}},
        },
        # Add other MCP servers here as needed:
        # {
        #     "type": "remote_mcp",
        #     "name": "brave_search",
        #     "config": {"remoteMcp": {"url": "https://mcp.brave.com/api"}},
        # },
    ],
)
print(f"Tools used: {result['tool_uses']}")

# ── Part 3: MCP with Authentication ──────────────────────────────────────────
print("\n=== Part 3: MCP with Authentication (env var pattern) ===")
api_key = os.getenv("MCP_API_KEY", "")

if api_key:
    # Example: authenticated MCP server with bearer token in headers
    # Header format may vary — check latest API docs for your MCP server
    tools_config = [
        {
            "type": "remote_mcp",
            "name": "authenticated_search",
            "config": {
                "remoteMcp": {
                    "url": EXA_MCP_URL,
                    # "headers": {"Authorization": f"Bearer {api_key}"}
                }
            },
        }
    ]
    print(
        f"✅ MCP configured with API key (first 8 chars): {api_key[:8]}..."
    )  # codeql[py/clear-text-logging-sensitive-data]
    print(f"Tool config: {json.dumps(tools_config, indent=2)}")
else:
    print("⚠️  No MCP_API_KEY found. Skipping authenticated example.")
    print("   Set it with: export MCP_API_KEY='your-key-here'")

# ── Part 4: Error Handling ────────────────────────────────────────────────────
print("\n=== Part 4: Error Handling — Invalid MCP URL ===")
session4 = str(uuid.uuid4()).upper()
print(f"Testing with invalid MCP URL (session: {session4})\n")

try:
    result = stream_invoke(
        session_id=session4,
        prompt="Search for 'test query'",
        tools=[
            {
                "type": "remote_mcp",
                "name": "invalid",
                "config": {
                    "remoteMcp": {"url": "https://invalid-mcp-url.example.com/mcp"}
                },
            }
        ],
        timeout=60,
    )
    print(f"Errors encountered: {len(result['errors'])}")
except Exception as e:
    # Expected: invalid MCP URL raises runtimeClientError — the harness rejects it
    # before the agent ever runs. This demonstrates graceful error surfacing.
    print(f"✅ Expected error for invalid MCP URL: {type(e).__name__}")
    print(f"   {str(e)[:200]}")

# ── Part 5: Advanced — Research Assistant ────────────────────────────────────
print("\n=== Part 5: Advanced — Research Assistant ===")
research_session = str(uuid.uuid4()).upper()
print(f"Research session: {research_session}\n")

research_prompt = """
Research topic: "Generative AI trends in enterprise adoption for 2024"

Please:
1. Search for recent articles and reports about enterprise AI adoption
2. Identify the top 5 trends
3. For each trend, provide:
   - Brief description
   - Key statistics or data points
   - Notable companies or use cases
4. Save the report as a structured JSON file at /tmp/ai_trends_report.json

Format the JSON as:
{
  "topic": "...",
  "date": "...",
  "trends": [{"name": "...", "description": "...", "statistics": [...], "examples": [...]}],
  "sources": [...]
}
"""

result = stream_invoke(
    session_id=research_session,
    prompt=research_prompt,
    tools=[
        {
            "type": "remote_mcp",
            "name": "exa",
            "config": {"remoteMcp": {"url": EXA_MCP_URL}},
        }
    ],
    timeout=300,
)

# Retrieve the report from the agent's VM
print("\n--- Retrieving research report from VM ---")
report_data = ""
resp = client.invoke_agent_runtime_command(
    agentRuntimeArn=harness_arn,
    runtimeSessionId=research_session,
    body={"command": "cat /tmp/ai_trends_report.json 2>/dev/null || echo '{}'"},
)
for event in resp["stream"]:
    if "chunk" in event:
        chunk = event["chunk"]
        if "contentDelta" in chunk and "stdout" in chunk["contentDelta"]:
            report_data += chunk["contentDelta"]["stdout"]

try:
    report = json.loads(report_data)
    print("✅ Research Report Generated:")
    print(json.dumps(report, indent=2)[:2000])  # show first 2000 chars
except json.JSONDecodeError:
    print("⚠️  Could not parse as JSON.")
    print(f"Raw output (first 500 chars): {report_data[:500]}")

# ── Cleanup ────────────────────────────────────────────────────────────────────
print("\n=== Cleanup ===")
control.delete_harness(harnessId=harness_id)
print(f"Deleted harness: {harness_id}")
delete_harness_role()
print("Done.")

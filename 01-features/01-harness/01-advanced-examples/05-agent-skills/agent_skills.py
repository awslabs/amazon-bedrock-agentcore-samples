"""
Agent Skills with AgentCore Harness.

Demonstrates how to extend agent capabilities with pre-built skill bundles:
  Part 1: Create a Harness with a Node.js container (required for skills)
  Part 2: Install the xlsx skill via ExecuteCommand
  Part 3: Use the skill to create an Excel travel budget spreadsheet
  Part 4: Advanced — quarterly sales report with multiple sheets
  Part 5: Download generated files from the agent's VM

Agent Skills are pre-built capability bundles that provide:
  - Specialized instructions for complex tasks
  - Code templates (xlsx, pdf, docx file formats)
  - Tool configurations and domain knowledge

Usage:
    python agent_skills.py

Prerequisites:
    - AWS CLI configured with credentials
    - pip install -r ../../requirements.txt
    - AWS_DEFAULT_REGION environment variable set
"""

import base64
import os
import sys
import time
import uuid
from pathlib import Path

import boto3
from botocore.config import Config

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.iam import create_harness_role, delete_harness_role
from utils.client import get_agentcore_control_client, get_agentcore_client

# ── Configuration ─────────────────────────────────────────────────────────────
MODEL_ID = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
NODE_CONTAINER = "public.ecr.aws/docker/library/node:slim"

# ── Setup ─────────────────────────────────────────────────────────────────────
control = get_agentcore_control_client()
# Use a long read_timeout: skills download + xlsx generation can take > 2 min
client = get_agentcore_client(config=Config(read_timeout=360))

account_id = boto3.client("sts").get_caller_identity()["Account"]
print(f"Account: {account_id}")

# ── Create IAM Role & Harness ─────────────────────────────────────────────────
print("\n=== Setup: IAM Role & Harness ===")
role_arn = create_harness_role()
print(f"Execution Role ARN: {role_arn}")
print("Waiting for IAM propagation...")
time.sleep(10)

HARNESS_NAME = f"SkillsDemo_{uuid.uuid4().hex[:8]}"
resp = control.create_harness(harnessName=HARNESS_NAME, executionRoleArn=role_arn)
harness = resp["harness"]
harness_id = harness["harnessId"]
harness_arn = harness["arn"]
print(f"Harness ID:  {harness_id}")
print(f"Harness ARN: {harness_arn}")

for i in range(12):
    status = control.get_harness(harnessId=harness_id)["harness"]["status"]
    print(f"  [{i + 1}] {status}")
    if status == "READY":
        print("✅ Harness is ready")
        break
    time.sleep(5)

# ── Attach Node.js Container (required for skill installation) ────────────────
print(f"\n=== Part 1: Attach Node.js Container ({NODE_CONTAINER}) ===")
control.update_harness(
    harnessId=harness_id,
    environmentArtifact={"optionalValue": {"containerConfiguration": {"containerUri": NODE_CONTAINER}}},
)
print("Waiting for container update...")
for i in range(12):
    status = control.get_harness(harnessId=harness_id)["harness"]["status"]
    print(f"  [{i + 1}] {status}")
    if status == "READY":
        print("✅ Harness updated with Node.js container")
        break
    time.sleep(5)

# ── Part 2: Install xlsx Skill ────────────────────────────────────────────────
print("\n=== Part 2: Install xlsx Skill ===")
session_id = str(uuid.uuid4()).upper()
print(f"Session ID: {session_id}\n")

print("Installing git and xlsx skill (this may take a minute)...")
resp = client.invoke_agent_runtime_command(
    agentRuntimeArn=harness_arn,
    runtimeSessionId=session_id,
    body={
        "command": "apt-get update && apt-get install git -y && "
        "npx skills add https://github.com/anthropics/skills --skill xlsx --yes"
    },
)

output = ""
for event in resp["stream"]:
    if "chunk" in event and "contentDelta" in event["chunk"]:
        delta = event["chunk"]["contentDelta"]
        if "stdout" in delta:
            output += delta["stdout"]
        if "stderr" in delta:
            output += delta["stderr"]

# Show last 500 chars (installation is verbose)
print(output[-500:] if len(output) > 500 else output)
print("✅ xlsx skill installed")

# Verify installation
resp = client.invoke_agent_runtime_command(
    agentRuntimeArn=harness_arn,
    runtimeSessionId=session_id,
    body={"command": "ls -la .agents/skills/xlsx/ 2>/dev/null && echo 'skill directory OK' || echo 'skill not found'"},
)
for event in resp["stream"]:
    if "chunk" in event and "contentDelta" in event["chunk"]:
        delta = event["chunk"]["contentDelta"]
        if "stdout" in delta:
            print(delta["stdout"], end="")

# ── Part 3: Create Travel Budget Spreadsheet ──────────────────────────────────
print("\n=== Part 3: Travel Budget Spreadsheet ===")

response = client.invoke_harness(
    harnessArn=harness_arn,
    runtimeSessionId=session_id,
    skills=[{"path": ".agents/skills/xlsx"}],
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "text": (
                        "Create an Excel spreadsheet with a 5-day Amsterdam trip budget. "
                        "Include columns for: Day, Category, Item, Cost (EUR), Cost (USD). "
                        "Add rows for accommodation, food, transport, museums, and activities for each day. "
                        "Include a total row with SUM formulas for EUR and USD columns. "
                        "Use currency conversion rate: 1 EUR = 1.10 USD. "
                        "Apply nice formatting: bold headers, currency formatting, alternating row colors. "
                        "Save it as /tmp/amsterdam_budget.xlsx"
                    )
                }
            ],
        }
    ],
    model={"bedrockModelConfig": {"modelId": MODEL_ID}},
)

for event in response["stream"]:
    if "contentBlockStart" in event:
        start = event["contentBlockStart"].get("start", {})
        if "toolUse" in start:
            print(f"\n[Tool: {start['toolUse'].get('name', '?')}]", flush=True)
    elif "contentBlockDelta" in event:
        delta = event["contentBlockDelta"].get("delta", {})
        if "text" in delta:
            print(delta["text"], end="", flush=True)
    elif "messageStop" in event:
        print("\n")

# Download the spreadsheet
print("Downloading amsterdam_budget.xlsx from agent VM...")
b64_data = ""
resp = client.invoke_agent_runtime_command(
    agentRuntimeArn=harness_arn,
    runtimeSessionId=session_id,
    body={"command": "base64 /tmp/amsterdam_budget.xlsx 2>/dev/null"},
)
for event in resp["stream"]:
    if "chunk" in event and "contentDelta" in event["chunk"]:
        delta = event["chunk"]["contentDelta"]
        if "stdout" in delta:
            b64_data += delta["stdout"]

if b64_data.strip():
    local_path = "/tmp/amsterdam_budget.xlsx"  # nosec B108
    with open(local_path, "wb") as f:
        f.write(base64.b64decode(b64_data.strip().replace("\n", "")))
    print(f"✅ Saved to {local_path} ({os.path.getsize(local_path):,} bytes)")
else:
    print("⚠️  No file generated — check agent response above")

# ── Part 4: Advanced — Quarterly Sales Report ────────────────────────────────
print("\n=== Part 4: Quarterly Sales Report (3 sheets) ===")

response = client.invoke_harness(
    harnessArn=harness_arn,
    runtimeSessionId=session_id,
    skills=[{"path": ".agents/skills/xlsx"}],
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "text": (
                        "Create a professional quarterly sales report Excel file with 3 sheets:\n"
                        "\n"
                        "Sheet 1 - Summary:\n"
                        "- Q1 2024 Sales Overview title\n"
                        "- Table with: Region, Target (USD), Actual (USD), Variance (%), Status\n"
                        "- 4 regions: North America, Europe, Asia Pacific, Latin America\n"
                        "- Use realistic numbers (targets 1M-5M, actual should vary ±20%)\n"
                        "- Variance formula: (Actual-Target)/Target * 100\n"
                        "- Status formula: IF variance >= 0, 'On Track', 'Below Target'\n"
                        "- Total row with SUM formulas\n"
                        "\n"
                        "Sheet 2 - Monthly Breakdown:\n"
                        "- Table with: Month, Region, Sales (USD)\n"
                        "- Data for Jan, Feb, Mar for each region\n"
                        "- Total row\n"
                        "\n"
                        "Sheet 3 - Top Products:\n"
                        "- Table with: Rank, Product, Category, Units Sold, Revenue (USD)\n"
                        "- 10 products with realistic data\n"
                        "\n"
                        "Formatting:\n"
                        "- Bold headers with background color\n"
                        "- Currency formatting for USD columns\n"
                        "- Percentage formatting for Variance column\n"
                        "- Conditional formatting: green for positive variance, red for negative\n"
                        "- Freeze top row in all sheets\n"
                        "\n"
                        "Save as /tmp/q1_sales_report.xlsx"
                    )
                }
            ],
        }
    ],
    model={"bedrockModelConfig": {"modelId": MODEL_ID}},
    timeoutSeconds=300,
)

for event in response["stream"]:
    if "contentBlockStart" in event:
        start = event["contentBlockStart"].get("start", {})
        if "toolUse" in start:
            print(f"\n[Tool: {start['toolUse'].get('name', '?')}]", flush=True)
    elif "contentBlockDelta" in event:
        delta = event["contentBlockDelta"].get("delta", {})
        if "text" in delta:
            print(delta["text"], end="", flush=True)
    elif "messageStop" in event:
        print("\n")

# Download the report
print("Downloading q1_sales_report.xlsx from agent VM...")
b64_data = ""
resp = client.invoke_agent_runtime_command(
    agentRuntimeArn=harness_arn,
    runtimeSessionId=session_id,
    body={"command": "base64 /tmp/q1_sales_report.xlsx 2>/dev/null"},
)
for event in resp["stream"]:
    if "chunk" in event and "contentDelta" in event["chunk"]:
        delta = event["chunk"]["contentDelta"]
        if "stdout" in delta:
            b64_data += delta["stdout"]

if b64_data.strip():
    local_path = "/tmp/q1_sales_report.xlsx"  # nosec B108
    with open(local_path, "wb") as f:
        f.write(base64.b64decode(b64_data.strip().replace("\n", "")))
    print(f"✅ Saved to {local_path} ({os.path.getsize(local_path):,} bytes)")
    print("   Sheets: 3 (Summary, Monthly Breakdown, Top Products)")
else:
    print("⚠️  No file generated")

# ── Cleanup ────────────────────────────────────────────────────────────────────
print("\n=== Cleanup ===")
control.delete_harness(harnessId=harness_id)
print(f"Deleted harness: {harness_id}")
delete_harness_role()
print("Done.")

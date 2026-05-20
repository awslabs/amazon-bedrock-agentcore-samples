"""
Execution Limits with AgentCore Harness.

Demonstrates how to control agent work per invocation using three limit parameters:
  - maxIterations: caps think → act → observe loop cycles
  - timeoutSeconds: wall-clock deadline for the entire invocation
  - maxTokens: maximum tokens the model can generate

Each limit is demonstrated with a before/after comparison showing what happens when
the agent hits a limit vs runs freely.

Usage:
    python execution_limits.py

Prerequisites:
    - AWS CLI configured with credentials
    - pip install -r ../../requirements.txt
    - AWS_DEFAULT_REGION environment variable set
"""

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

HARNESS_NAME = f"ExecLimits_{uuid.uuid4().hex[:8]}"
resp = control.create_harness(harnessName=HARNESS_NAME, executionRoleArn=role_arn)
harness = resp["harness"]
harness_id = harness["harnessId"]
harness_arn = harness["arn"]
print(f"Harness ID: {harness_id}")

for i in range(12):
    status = control.get_harness(harnessId=harness_id)["harness"]["status"]
    print(f"  [{i + 1}] {status}")
    if status == "READY":
        print("✅ Harness is ready")
        break
    time.sleep(5)

# ── Helper Functions ─────────────────────────────────────────────────────────


def invoke(prompt: str, **limits) -> str:
    """Invoke the harness with a prompt and optional execution limits.

    Pass any of: maxIterations=, timeoutSeconds=, maxTokens=
    Returns the session ID so you can use run() to inspect the VM.
    """
    sid = str(uuid.uuid4()).upper()
    limit_str = ", ".join(f"{k}={v}" for k, v in limits.items()) or "(defaults)"
    print(f"\n--- Limits: {limit_str} ---")
    print(f"Session: {sid}\n")

    response = client.invoke_harness(
        harnessArn=harness_arn,
        runtimeSessionId=sid,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        model={"bedrockModelConfig": {"modelId": MODEL_ID}},
        **limits,
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
            stop = event["messageStop"]
            reason = stop.get("stopReason", "")
            print(f"\n\n→ stopReason: {reason}")
        elif "metadata" in event:
            meta = event["metadata"]
            usage = meta.get("usage", {})
            if usage:
                print(
                    f"→ usage: input={usage.get('inputTokens', 0)}, output={usage.get('outputTokens', 0)}"
                )
        elif "internalServerException" in event:
            print(f"\nError: {event['internalServerException']}")
    print()
    return sid


def run(cmd: str, session_id: str):
    """Run a shell command on the agent's VM for a given session."""
    print(f"$ {cmd}")
    resp = client.invoke_agent_runtime_command(
        agentRuntimeArn=harness_arn,
        runtimeSessionId=session_id,
        body={"command": cmd},
    )
    for event in resp["stream"]:
        if "chunk" in event:
            chunk = event["chunk"]
            if "contentDelta" in chunk:
                d = chunk["contentDelta"]
                if "stdout" in d:
                    print(d["stdout"], end="", flush=True)
                if "stderr" in d:
                    print(d["stderr"], end="", flush=True)
            elif "contentStop" in chunk:
                print(f"\n[exit: {chunk['contentStop']['exitCode']}]")
    print()


# ── Demo 1: maxIterations ──────────────────────────────────────────────────────
print("\n=== Demo 1: maxIterations ===")
print("maxIterations=1: Agent gets one tool call before it must respond.")
print("Expected: Agent can't create all 3 files in one iteration.\n")

sid = invoke(
    "Create 3 files: hello.txt, world.txt, and readme.md with some content in each.",
    maxIterations=1,
)
run("ls -la", sid)

print("\nmaxIterations=10: Agent can complete all 3 files.")
sid = invoke(
    "Create 3 files: hello.txt, world.txt, and readme.md with some content in each.",
    maxIterations=10,
)
run("ls -la", sid)
run("cat *.md", sid)

# ── Demo 2: timeoutSeconds ────────────────────────────────────────────────────
print("\n=== Demo 2: timeoutSeconds ===")
print("timeoutSeconds=5: Tight deadline — complex task will time out.\n")

invoke(
    "Write a Python script that generates the first 50 prime numbers, save it to primes.py, "
    "then run it and show the output.",
    timeoutSeconds=5,
)

print("\ntimeoutSeconds=120: Generous timeout — task completes.\n")
invoke(
    "Write a Python script that generates the first 50 prime numbers, save it to primes.py, "
    "then run it and show the output.",
    timeoutSeconds=120,
)

# ── Demo 3: maxTokens ─────────────────────────────────────────────────────────
print("\n=== Demo 3: maxTokens ===")
print("maxTokens=10: Very tight token budget — model will be cut short.\n")

invoke(
    "Explain the history of the Python programming language in detail.",
    maxTokens=10,
)

print("\nmaxTokens=2048: Normal budget — full response.\n")
invoke(
    "Explain the history of the Python programming language in detail.",
    maxTokens=2048,
)

# ── Demo 4: Combining Limits ──────────────────────────────────────────────────
print("\n=== Demo 4: Combining Limits ===")
print("maxIterations=3 + timeoutSeconds=30 + maxTokens=1024\n")

invoke(
    "List all files in the current directory, then create a summary.txt with what you found.",
    maxIterations=3,
    timeoutSeconds=30,
    maxTokens=1024,
)

# ── Cleanup ────────────────────────────────────────────────────────────────────
print("\n=== Cleanup ===")
control.delete_harness(harnessId=harness_id)
print(f"Deleted harness: {harness_id}")
delete_harness_role()
print("Done.")

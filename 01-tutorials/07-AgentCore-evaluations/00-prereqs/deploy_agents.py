#!/usr/bin/env python3
"""
Deploy Strands and LangGraph agents to AgentCore Runtime.

Saves agent IDs and ARNs to agents_config.json for use in the tutorial notebook.
Run this script from the 00-prereqs directory:

    python deploy_agents.py

On subsequent runs, already-deployed agents are detected automatically and
the script simply waits for READY status before writing the config.
"""
import json
import os
import shutil
import subprocess
import time

import boto3
from boto3.session import Session

STRANDS_PROJECT = "acevalstrands2"
LANGGRAPH_PROJECT = "acevallanggraph2"
CONFIG_FILE = "agents_config.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_region():
    return Session().region_name


def get_account_id(region):
    return boto3.client("sts", region_name=region).get_caller_identity()["Account"]


def find_runtime(cp, project_name):
    """Return the first runtime whose ID contains project_name, or None."""
    paginator = cp.get_paginator("list_agent_runtimes")
    for page in paginator.paginate():
        for rt in page.get("agentRuntimeSummaries", page.get("agentRuntimes", [])):
            if project_name in rt.get("agentRuntimeId", ""):
                return rt
    return None


def wait_for_ready(region, agent_id, label, max_wait=600, poll_interval=15):
    """Poll until the agent reaches READY (or raises on failure/timeout)."""
    cp = boto3.client("bedrock-agentcore-control", region_name=region)
    terminal = {"READY", "FAILED", "CREATE_FAILED", "UPDATE_FAILED", "DELETE_FAILED"}
    elapsed = 0
    while elapsed < max_wait:
        resp = cp.get_agent_runtime(agentRuntimeId=agent_id)
        status = resp.get("agentRuntimeStatus") or resp.get("status", "UNKNOWN")
        print(f"  [{label}] status: {status}")
        if status in terminal:
            if status != "READY":
                raise RuntimeError(f"{label} deployment ended with status: {status}")
            return
        time.sleep(poll_interval)
        elapsed += poll_interval
    raise TimeoutError(f"{label} did not reach READY within {max_wait}s")


def _write_aws_targets(project, region, account_id):
    targets_path = os.path.join(project, "agentcore", "aws-targets.json")
    with open(targets_path, "w") as f:
        json.dump(
            [{"name": "default",
              "description": f"Default target ({region})",
              "account": account_id,
              "region": region}],
            f, indent=2,
        )


# ---------------------------------------------------------------------------
# Agent deployment
# ---------------------------------------------------------------------------

def deploy_strands(region, account_id, cp):
    print(f"\n=== Strands Agent ({STRANDS_PROJECT}) ===")

    existing = find_runtime(cp, STRANDS_PROJECT)
    if existing:
        agent_id = existing["agentRuntimeId"]
        agent_arn = existing["agentRuntimeArn"]
        print(f"  Already deployed: {agent_id}")
        wait_for_ready(region, agent_id, "Strands")
        return agent_id, agent_arn

    # Create project scaffold
    if not os.path.isdir(STRANDS_PROJECT):
        print("  Creating project scaffold...")
        subprocess.run(
            ["agentcore", "create", "--name", STRANDS_PROJECT,
             "--framework", "Strands", "--model-provider", "Bedrock", "--defaults"],
            check=True,
        )

    # Copy agent implementation
    shutil.copy("eval_agent_strands.py",
                os.path.join(STRANDS_PROJECT, "app", STRANDS_PROJECT, "main.py"))
    print("  Copied eval_agent_strands.py → main.py")

    # Add strands-agents-tools dependency
    pyproject = os.path.join(STRANDS_PROJECT, "app", STRANDS_PROJECT, "pyproject.toml")
    with open(pyproject) as f:
        content = f.read()
    if "strands-agents-tools" not in content:
        content = content.replace(
            '"bedrock-agentcore >= 1.0.3"',
            '"bedrock-agentcore >= 1.0.3",\n    "strands-agents-tools"',
        )
        with open(pyproject, "w") as f:
            f.write(content)
        print("  Added strands-agents-tools to pyproject.toml")

    _write_aws_targets(STRANDS_PROJECT, region, account_id)

    print("  Deploying (first run ~5 min)...")
    subprocess.run(["agentcore", "deploy", "-y"], cwd=STRANDS_PROJECT, check=True)

    runtime = find_runtime(cp, STRANDS_PROJECT)
    if runtime is None:
        raise RuntimeError("Strands runtime not found after deploy — check output above.")

    agent_id = runtime["agentRuntimeId"]
    agent_arn = runtime["agentRuntimeArn"]
    wait_for_ready(region, agent_id, "Strands")
    print(f"  Ready: {agent_id}")
    return agent_id, agent_arn


def deploy_langgraph(region, account_id, cp):
    print(f"\n=== LangGraph Agent ({LANGGRAPH_PROJECT}) ===")

    existing = find_runtime(cp, LANGGRAPH_PROJECT)
    if existing:
        agent_id = existing["agentRuntimeId"]
        agent_arn = existing["agentRuntimeArn"]
        print(f"  Already deployed: {agent_id}")
        wait_for_ready(region, agent_id, "LangGraph")
        return agent_id, agent_arn

    # Create project scaffold
    if not os.path.isdir(LANGGRAPH_PROJECT):
        print("  Creating project scaffold...")
        subprocess.run(
            ["agentcore", "create", "--name", LANGGRAPH_PROJECT,
             "--framework", "LangChain_LangGraph", "--model-provider", "Bedrock",
             "--defaults"],
            check=True,
        )

    # Copy agent implementation
    shutil.copy("eval_agent_langgraph.py",
                os.path.join(LANGGRAPH_PROJECT, "app", LANGGRAPH_PROJECT, "main.py"))
    print("  Copied eval_agent_langgraph.py → main.py")

    # Add langchain-community dependency
    pyproject = os.path.join(LANGGRAPH_PROJECT, "app", LANGGRAPH_PROJECT, "pyproject.toml")
    with open(pyproject) as f:
        content = f.read()
    if "langchain-community" not in content:
        content = content.replace(
            '"bedrock-agentcore >= 1.0.3"',
            '"bedrock-agentcore >= 1.0.3",\n    "langchain-community"',
        )
        with open(pyproject, "w") as f:
            f.write(content)
        print("  Added langchain-community to pyproject.toml")

    _write_aws_targets(LANGGRAPH_PROJECT, region, account_id)

    print("  Deploying (first run ~5 min)...")
    subprocess.run(["agentcore", "deploy", "-y"], cwd=LANGGRAPH_PROJECT, check=True)

    runtime = find_runtime(cp, LANGGRAPH_PROJECT)
    if runtime is None:
        raise RuntimeError("LangGraph runtime not found after deploy — check output above.")

    agent_id = runtime["agentRuntimeId"]
    agent_arn = runtime["agentRuntimeArn"]
    wait_for_ready(region, agent_id, "LangGraph")
    print(f"  Ready: {agent_id}")
    return agent_id, agent_arn


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    region = get_region()
    account_id = get_account_id(region)
    cp = boto3.client("bedrock-agentcore-control", region_name=region)

    print(f"Region : {region}")
    print(f"Account: {account_id}")

    strands_id, strands_arn = deploy_strands(region, account_id, cp)
    langgraph_id, langgraph_arn = deploy_langgraph(region, account_id, cp)

    config = {
        "strands":   {"agent_id": strands_id,   "agent_arn": strands_arn},
        "langgraph": {"agent_id": langgraph_id,  "agent_arn": langgraph_arn},
        "region": region,
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

    print(f"\nConfig saved to {CONFIG_FILE}")
    print(f"  Strands   agent_id : {strands_id}")
    print(f"  LangGraph agent_id : {langgraph_id}")


if __name__ == "__main__":
    main()

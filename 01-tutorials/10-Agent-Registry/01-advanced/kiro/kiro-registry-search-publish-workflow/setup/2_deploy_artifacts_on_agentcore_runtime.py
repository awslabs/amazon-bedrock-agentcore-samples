#!/usr/bin/env python3
"""
Step 2: Deploy agents to AgentCore Runtime.

All agents are HTTP protocol with IAM auth (no OAuth on agents).

Run:  python3 2_deploy_artifacts_on_agentcore_runtime.py market_research_agent [financial_analysis_agent ...]
"""

import argparse
import logging
import os
import shutil
import tempfile
from pathlib import Path

from bedrock_agentcore_starter_toolkit import Runtime
from setup import REGION

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("deploy")


def load_metadata(agent_name: str) -> dict:
    mod = __import__(f"seed_agents.{agent_name}", fromlist=["METADATA"])
    return mod.METADATA


def deploy_one(agent_name: str) -> dict:
    """Package and deploy a single agent to AgentCore Runtime. Returns name and ARN."""
    meta = load_metadata(agent_name)
    name = meta["name"]

    logger.info("Deploying: %s (HTTP) — Team: %s", name, meta.get("team", "unknown"))

    agent_file = Path("seed_agents") / meta["entrypoint"]
    req_file = Path("seed_agents") / "requirements.txt"
    project_dir = Path(tempfile.mkdtemp(prefix=f"ac-{name}-"))
    shutil.copy(agent_file, project_dir / meta["entrypoint"])
    if req_file.exists():
        shutil.copy(req_file, project_dir / "requirements.txt")

    original_dir = os.getcwd()
    os.chdir(project_dir)

    try:
        runtime = Runtime()
        runtime.configure(
            entrypoint=meta["entrypoint"],
            agent_name=name,
            protocol="HTTP",
            region=REGION,
            auto_create_execution_role=True,
            auto_create_ecr=True,
            requirements_file="requirements.txt" if req_file.exists() else None,
        )
        result = runtime.launch(auto_update_on_conflict=True)
        logger.info("Deployed: %s — ARN: %s", name, result.agent_arn)
        return {"name": name, "agent_arn": result.agent_arn}
    finally:
        os.chdir(original_dir)
        shutil.rmtree(project_dir, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description="Deploy agent(s) to AgentCore Runtime")
    parser.add_argument("agents", nargs="+", help="Agent module names (e.g. market_research_agent)")
    args = parser.parse_args()

    results = []
    for name in args.agents:
        try:
            results.append(deploy_one(name))
        except Exception as e:
            logger.error("Failed to deploy %s: %s", name, e)

    logger.info("Deployed %d/%d agents", len(results), len(args.agents))
    for r in results:
        logger.info("  %s | %s", r["name"], r["agent_arn"])


if __name__ == "__main__":
    main()

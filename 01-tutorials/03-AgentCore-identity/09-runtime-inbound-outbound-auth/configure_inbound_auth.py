"""
Post-deploy script: Configures Cognito JWT inbound auth on the AgentCore Runtime.

The agentcore CLI does not yet expose authorizationConfiguration in agentcore.json,
so this script applies it via the boto3 control plane API after deployment.

Run this once after 'agentcore deploy -y'.

Usage:
    python configure_inbound_auth.py
"""

import boto3
import json
import os
import re
import subprocess
import sys


def find_project_dir() -> str:
    base = os.path.dirname(os.path.abspath(__file__))
    for entry in os.listdir(base):
        candidate = os.path.join(base, entry)
        if os.path.isdir(candidate) and os.path.isdir(os.path.join(candidate, "agentcore")):
            return candidate
    raise FileNotFoundError("No agentcore project directory found. Run 'agentcore create' first.")


def get_runtime_id() -> str:
    project_dir = find_project_dir()
    result = subprocess.run(
        ["agentcore", "status", "--json"],
        capture_output=True,
        text=True,
        cwd=project_dir,
    )
    clean = re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", result.stdout).strip()
    status = json.loads(clean)
    for resource in status.get("resources", []):
        if resource.get("resourceType") == "agent" and resource.get("deploymentState") == "deployed":
            arn = resource.get("identifier", "")
            return arn.split("/")[-1]
    raise ValueError("No deployed agent found. Run 'agentcore deploy -y' first.")


def main():
    try:
        with open("cognito_config.json") as f:
            config = json.load(f)
    except FileNotFoundError:
        print("ERROR: cognito_config.json not found. Run 'python setup_cognito.py' first.")
        sys.exit(1)

    runtime_id = get_runtime_id()
    print(f"Configuring JWT inbound auth on runtime: {runtime_id}")

    ctrl = boto3.client("bedrock-agentcore-control", region_name=config["region"])

    # Fetch current runtime config — update_agent_runtime requires existing fields
    current = ctrl.get_agent_runtime(agentRuntimeId=runtime_id)

    ctrl.update_agent_runtime(
        agentRuntimeId=runtime_id,
        agentRuntimeArtifact=current["agentRuntimeArtifact"],
        roleArn=current["roleArn"],
        networkConfiguration=current["networkConfiguration"],
        authorizerConfiguration={
            "customJWTAuthorizer": {
                "discoveryUrl": config["discovery_url"],
                "allowedClients": [config["client_id"]],
            }
        },
    )

    print("JWT inbound auth configured.")
    print(f"  Discovery URL : {config['discovery_url']}")
    print(f"  Allowed Client: {config['client_id']}")
    print("\nWait ~30s for the change to propagate, then run: python invoke.py")


if __name__ == "__main__":
    main()

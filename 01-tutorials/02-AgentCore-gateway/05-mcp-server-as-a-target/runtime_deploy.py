"""Helper for deploying an MCP server to AgentCore Runtime.

Each MCP-server deploy in this tutorial repeats the same boilerplate:
  1. Build a customJWTAuthorizer from a Cognito client_id + discovery URL.
  2. Configure the Runtime with an entrypoint file + agent name.
  3. Launch and derive the qualifier=DEFAULT invocation URL from the ARN.

Wrapping that in one helper keeps each notebook cell focused on what is
different between deploys (entrypoint, agent_name) instead of the
boilerplate.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from bedrock_agentcore_starter_toolkit import Runtime


@dataclass
class DeployedRuntime:
    runtime: Runtime
    agent_arn: str
    agent_id: str
    agent_url: str


def deploy_mcp_server(
    *,
    entrypoint: str,
    agent_name: str,
    region: str,
    runtime_client_id: str,
    runtime_discovery_url: str,
    requirements_file: str = "requirements.txt",
) -> DeployedRuntime:
    """Configure + launch an MCP server on AgentCore Runtime.

    Returns the Runtime instance plus the agent's ARN, ID, and the
    `qualifier=DEFAULT` invocation URL the gateway target should point at.
    """
    for f in (entrypoint, requirements_file):
        if not os.path.exists(f):
            raise FileNotFoundError(f"Required file {f!r} not found in cwd")

    runtime = Runtime()

    auth_config = {
        "customJWTAuthorizer": {
            "allowedClients": [runtime_client_id],
            "discoveryUrl": runtime_discovery_url,
        }
    }

    print(f"Configuring AgentCore Runtime for {agent_name} ({entrypoint})...")
    runtime.configure(
        entrypoint=entrypoint,
        auto_create_execution_role=True,
        auto_create_ecr=True,
        requirements_file=requirements_file,
        region=region,
        authorizer_configuration=auth_config,
        protocol="MCP",
        agent_name=agent_name,
    )

    print(f"Launching {agent_name} (this may take several minutes)...")
    launch_result = runtime.launch()

    encoded_arn = launch_result.agent_arn.replace(":", "%3A").replace("/", "%2F")
    agent_url = (
        f"https://bedrock-agentcore.{region}.amazonaws.com/"
        f"runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
    )

    print(f"  agent_arn: {launch_result.agent_arn}")
    print(f"  agent_id:  {launch_result.agent_id}")
    print(f"  agent_url: {agent_url}")

    return DeployedRuntime(
        runtime=runtime,
        agent_arn=launch_result.agent_arn,
        agent_id=launch_result.agent_id,
        agent_url=agent_url,
    )

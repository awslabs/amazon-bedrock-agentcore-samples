"""Invoke the agent deployed on AgentCore Runtime.

Run after `agentcore deploy`. Reads the runtime ARN from the .bedrock_agentcore.yaml
the starter toolkit generates.

Usage:
    python invoke_runtime.py
    python invoke_runtime.py "Break down sales by region for the last fiscal year."
"""

import argparse
import json

import boto3
import yaml

from config import AWS_REGION

DEFAULT_PROMPT = "What were our top 5 products by revenue last quarter?"
# invoke_agent_runtime requires a session id of at least 33 characters.
SESSION_ID = "genie-test-session-123456789012345"


def resolve_agent_arn() -> str:
    """Read the deployed runtime ARN from the starter toolkit's config file."""
    try:
        with open(".bedrock_agentcore.yaml") as f:
            ac_config = yaml.safe_load(f)
    except FileNotFoundError:
        raise SystemExit(
            ".bedrock_agentcore.yaml not found — run `agentcore configure` and "
            "`agentcore deploy` first."
        )

    # The toolkit stores the ARN per-agent under
    # agents.<agent_name>.bedrock_agentcore.agent_arn
    agents = ac_config.get("agents", {})
    default_agent = ac_config.get("default_agent")
    agent_spec = agents.get(default_agent) or next(iter(agents.values()), {})
    agent_arn = (agent_spec.get("bedrock_agentcore") or {}).get("agent_arn", "")

    if not agent_arn:
        raise SystemExit("Agent ARN not found — run `agentcore deploy` first.")
    return agent_arn


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", nargs="?", default=DEFAULT_PROMPT)
    args = parser.parse_args()

    agent_arn = resolve_agent_arn()
    print(f"Invoking {agent_arn}")

    runtime = boto3.client("bedrock-agentcore", region_name=AWS_REGION)
    response = runtime.invoke_agent_runtime(
        agentRuntimeArn=agent_arn,
        runtimeSessionId=SESSION_ID,
        payload=json.dumps({"prompt": args.prompt}).encode(),
        qualifier="DEFAULT",
    )
    print("Agent response:")
    print(json.dumps(json.loads(response["response"].read()), indent=2))


if __name__ == "__main__":
    main()

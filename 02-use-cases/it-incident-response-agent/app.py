#!/usr/bin/env python3
"""CDK app entrypoint for the IT Incident Response Agent.

Reads `.env` for environment-specific configuration (stack name, region,
Auth0 credentials, model IDs) and instantiates a single stack.
"""

import os
import sys

import aws_cdk as cdk
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
from nag_suppressions import apply_nag_suppressions  # noqa: E402
from stacks.it_incident_stack import ItIncidentStack  # noqa: E402


def required(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        sys.stderr.write(
            f"ERROR: {key} not set. Copy .env.example to .env and fill it in.\n"
        )
        sys.exit(1)
    return val


def main() -> None:
    load_dotenv()

    stack_name = os.environ.get("STACK_NAME", "ItIncidentResponseAgent")
    region = os.environ.get("AWS_REGION", "us-west-2")
    account = os.environ.get("CDK_DEFAULT_ACCOUNT") or os.environ.get("AWS_ACCOUNT_ID")

    config = {
        "agent_model_id": os.environ.get(
            "AGENT_MODEL_ID", "us.anthropic.claude-sonnet-4-6-20250929-v1:0"
        ),
        "kb_embedding_model_id": os.environ.get(
            "KB_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0"
        ),
        "auth0_domain": required("AUTH0_DOMAIN"),
        "auth0_client_id": required("AUTH0_CLIENT_ID"),
        "auth0_client_secret": required("AUTH0_CLIENT_SECRET"),
        "auth0_audience": required("AUTH0_AUDIENCE"),
    }

    app = cdk.App()
    stack = ItIncidentStack(
        app,
        stack_name,
        config=config,
        env=cdk.Environment(account=account, region=region),
        description="Event-driven IT incident response agent on Amazon Bedrock AgentCore",
    )
    apply_nag_suppressions(stack)
    app.synth()


if __name__ == "__main__":
    main()

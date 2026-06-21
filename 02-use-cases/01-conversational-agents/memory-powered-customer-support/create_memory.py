"""
AgentCore Memory Store Creation

Creates a memory resource with both short-term and long-term
(semantic extraction) strategies for the customer support agent.

Strategies:
  - CustomerFacts: Extracts and stores customer preferences, names, contact info
  - IssueHistory: Extracts and stores support issue details and resolutions
"""

import os
import sys
import json

from bedrock_agentcore.memory import MemoryClient
from botocore.exceptions import ClientError

REGION = os.getenv("AWS_REGION", "us-east-1")
MEMORY_ROLE_ARN = os.environ.get("MEMORY_EXECUTION_ROLE_ARN")
MEMORY_NAME = "CustomerSupportMemory"
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "memory_config.json")


def create_memory_store():
    """Create the AgentCore Memory store with semantic strategies."""
    if not MEMORY_ROLE_ARN:
        print("Error: MEMORY_EXECUTION_ROLE_ARN environment variable is not set.")
        print("Run: python setup_iam.py")
        sys.exit(1)

    client = MemoryClient(region_name=REGION)

    # Define semantic extraction strategies for long-term memory
    strategies = [
        {
            "semanticMemoryStrategy": {
                "name": "CustomerFacts",
                "description": "Extracts customer preferences, personal details, "
                "and communication preferences from conversations.",
                "namespaces": ["/customers/{actorId}/facts"],
            }
        },
        {
            "semanticMemoryStrategy": {
                "name": "IssueHistory",
                "description": "Extracts support ticket details, issue descriptions, "
                "resolutions, and follow-up actions from conversations.",
                "namespaces": ["/customers/{actorId}/issues"],
            }
        },
    ]

    try:
        print(f"Creating memory store '{MEMORY_NAME}'...")
        memory = client.create_memory_and_wait(
            name=MEMORY_NAME,
            description="Customer Support Agent - tracks customer preferences "
            "and issue history across sessions",
            strategies=strategies,
            event_expiry_days=90,  # Keep events for 90 days
            memory_execution_role_arn=MEMORY_ROLE_ARN,
            max_wait=300,
            poll_interval=10,
        )

        memory_id = memory["id"]
        print(f"Memory store created successfully!")
        print(f"  Memory ID: {memory_id}")
        print(f"  Status: {memory['status']}")
        print(f"  Strategies: CustomerFacts, IssueHistory")

        # Save config for the agent to use
        config = {
            "memory_id": memory_id,
            "region": REGION,
            "strategies": {
                "customer_facts": "/customers/{actorId}/facts",
                "issue_history": "/customers/{actorId}/issues",
            },
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        print(f"\nConfig saved to {CONFIG_FILE}")

        return memory_id

    except ClientError as e:
        if "already exists" in str(e):
            print(f"Memory '{MEMORY_NAME}' already exists. Retrieving ID...")
            memories = client.list_memories()
            memory_id = next(
                (m["id"] for m in memories if m["id"].startswith(MEMORY_NAME)),
                None,
            )
            if memory_id:
                config = {
                    "memory_id": memory_id,
                    "region": REGION,
                    "strategies": {
                        "customer_facts": "/customers/{actorId}/facts",
                        "issue_history": "/customers/{actorId}/issues",
                    },
                }
                with open(CONFIG_FILE, "w") as f:
                    json.dump(config, f, indent=2)
                print(f"  Memory ID: {memory_id}")
                return memory_id
        raise


if __name__ == "__main__":
    create_memory_store()

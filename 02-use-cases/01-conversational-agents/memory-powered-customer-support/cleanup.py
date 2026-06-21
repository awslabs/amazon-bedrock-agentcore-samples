"""
Cleanup script for the Memory-Powered Customer Support Agent.

Deletes the AgentCore Memory resource and removes local config.
"""

import json
import os
import sys

from bedrock_agentcore.memory import MemoryClient

REGION = os.getenv("AWS_REGION", "us-east-1")
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "memory_config.json")


def cleanup():
    """Delete the memory store and local configuration."""
    if not os.path.exists(CONFIG_FILE):
        print("No memory_config.json found. Nothing to clean up.")
        return

    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)

    memory_id = config.get("memory_id")
    if not memory_id:
        print("No memory_id found in config. Nothing to clean up.")
        return

    client = MemoryClient(region_name=REGION)

    print(f"Deleting memory store: {memory_id}")
    try:
        client.delete_memory_and_wait(
            memory_id=memory_id,
            max_wait=300,
            poll_interval=10,
        )
        print("Memory store deleted successfully.")
    except Exception as e:
        print(f"Error deleting memory store: {e}")

    # Remove local config
    os.remove(CONFIG_FILE)
    print(f"Removed {CONFIG_FILE}")
    print("\nCleanup complete.")


if __name__ == "__main__":
    confirm = input(
        "This will permanently delete the memory store and all data. "
        "Continue? (y/N): "
    )
    if confirm.lower() == "y":
        cleanup()
    else:
        print("Cleanup cancelled.")

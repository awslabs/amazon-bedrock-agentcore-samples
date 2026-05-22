"""Event metadata and filtering.

What you learn:
    - Attach key-value metadata to events on CreateEvent
    - Filter ListEvents by metadata using EQUALS_TO / EXISTS / NOT_EXISTS

Caveat: event metadata is NOT encrypted with a customer-managed KMS key.
Do not put sensitive content in metadata — keep it in the payload.

Two surfaces:
    python event-metadata-filtering.py boto3
    python event-metadata-filtering.py sdk

Add `--cleanup` to delete the memory resource at the end. By default the
memory is kept so you can inspect it; the script prints the memoryId.

Prerequisites:
    pip install boto3 bedrock-agentcore
    export AWS_REGION=us-east-1   # use any AgentCore-supported region
"""

import os
import sys
import time
import uuid
from datetime import datetime, timezone

REGION = os.getenv("AWS_REGION", "us-east-1")
ACTOR_ID = "user-42"
SESSION_ID = f"sess-{int(time.time())}"


# === boto3 ============================================================
def run_with_boto3(cleanup: bool = False) -> None:
    import boto3

    control = boto3.client("bedrock-agentcore-control", region_name=REGION)
    data = boto3.client("bedrock-agentcore", region_name=REGION)

    memory_id = control.create_memory(
        name=f"EventMetadata_{int(time.time())}",
        description="Event metadata filtering tutorial",
        eventExpiryDuration=30,
    )["memory"]["id"]
    print(f"[boto3] Created memory {memory_id}")
    deadline = time.time() + 300
    while time.time() < deadline:
        if control.get_memory(memoryId=memory_id)["memory"]["status"] == "ACTIVE":
            break
        time.sleep(5)

    tagged_turns = [
        ("USER", "I had a fever last night.", {"topic": "health", "priority": "high"}),
        ("ASSISTANT", "Sorry to hear. How long has it lasted?", {"topic": "health"}),
        ("USER", "Also can you book me a flight to Lisbon?", {"topic": "travel"}),
        ("ASSISTANT", "Booking flight to Lisbon.", {"topic": "travel"}),
        ("USER", "Just checking in, no specific topic today.", {}),
    ]
    for role, text, meta in tagged_turns:
        kwargs = dict(
            memoryId=memory_id,
            actorId=ACTOR_ID,
            sessionId=SESSION_ID,
            eventTimestamp=datetime.now(timezone.utc),
            payload=[{"conversational": {"role": role, "content": {"text": text}}}],
        )
        if meta:
            kwargs["metadata"] = {k: {"stringValue": v} for k, v in meta.items()}
        data.create_event(**kwargs)

    health = data.list_events(
        memoryId=memory_id,
        actorId=ACTOR_ID,
        sessionId=SESSION_ID,
        includePayloads=True,
        filter={
            "eventMetadata": [
                {
                    "left": {"metadataKey": "topic"},
                    "operator": "EQUALS_TO",
                    "right": {"metadataValue": {"stringValue": "health"}},
                }
            ]
        },
    )["events"]
    print(f"[boto3] Health-tagged events: {len(health)}")

    priority = data.list_events(
        memoryId=memory_id,
        actorId=ACTOR_ID,
        sessionId=SESSION_ID,
        includePayloads=True,
        filter={"eventMetadata": [{"left": {"metadataKey": "priority"}, "operator": "EXISTS"}]},
    )["events"]
    print(f"[boto3] Events with priority set: {len(priority)}")

    if cleanup:
        control.delete_memory(memoryId=memory_id, clientToken=str(uuid.uuid4()))
        print(f"[boto3] Deleted memory {memory_id}")
    else:
        print(f"[boto3] Keeping memory {memory_id} (pass --cleanup to delete)")


# === AgentCore SDK ====================================================
def run_with_sdk(cleanup: bool = False) -> None:
    from bedrock_agentcore.memory import MemoryClient

    client = MemoryClient(region_name=REGION)
    memory = client.create_memory_and_wait(
        name=f"EventMetadataSdk_{int(time.time())}",
        description="Event metadata filtering (SDK)",
        strategies=[],
        event_expiry_days=30,
    )
    memory_id = memory["id"]
    print(f"[sdk] Created memory {memory_id}")

    tagged_turns = [
        ("USER", "I had a fever last night.", {"topic": "health", "priority": "high"}),
        ("ASSISTANT", "Sorry to hear. How long has it lasted?", {"topic": "health"}),
        ("USER", "Also can you book me a flight to Lisbon?", {"topic": "travel"}),
        ("ASSISTANT", "Booking flight to Lisbon.", {"topic": "travel"}),
        ("USER", "Just checking in, no specific topic today.", {}),
    ]
    for role, text, meta in tagged_turns:
        client.create_event(
            memory_id=memory_id,
            actor_id=ACTOR_ID,
            session_id=SESSION_ID,
            messages=[(text, role)],
            metadata={k: {"stringValue": v} for k, v in meta.items()} if meta else None,
        )

    health = client.list_events(
        memory_id=memory_id,
        actor_id=ACTOR_ID,
        session_id=SESSION_ID,
        event_metadata=[
            {
                "left": {"metadataKey": "topic"},
                "operator": "EQUALS_TO",
                "right": {"metadataValue": {"stringValue": "health"}},
            }
        ],
    )
    print(f"[sdk] Health-tagged events: {len(health)}")

    priority = client.list_events(
        memory_id=memory_id,
        actor_id=ACTOR_ID,
        session_id=SESSION_ID,
        event_metadata=[{"left": {"metadataKey": "priority"}, "operator": "EXISTS"}],
    )
    print(f"[sdk] Events with priority set: {len(priority)}")

    if cleanup:
        client.delete_memory_and_wait(memory_id=memory_id)
        print(f"[sdk] Deleted memory {memory_id}")
    else:
        print(f"[sdk] Keeping memory {memory_id} (pass --cleanup to delete)")


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--cleanup"]
    cleanup = "--cleanup" in sys.argv[1:]
    surface = args[0] if args else "boto3"
    if surface == "boto3":
        run_with_boto3(cleanup=cleanup)
    elif surface == "sdk":
        run_with_sdk(cleanup=cleanup)
    else:
        print(f"Unknown surface {surface!r}. Use boto3 | sdk.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

"""Event metadata and filtering.

What you learn:
    - Attach key-value metadata to events on CreateEvent
    - Filter ListEvents by metadata using EQUALS_TO / EXISTS / NOT_EXISTS

Caveat: event metadata is NOT encrypted with a customer-managed KMS key.
Do not put sensitive content in metadata — keep it in the payload.

Three surfaces:
    python event-metadata-filtering.py boto3
    python event-metadata-filtering.py sdk    # documents the SDK gap
    python event-metadata-filtering.py cli

Prerequisites:
    pip install boto3 bedrock-agentcore
    export AWS_REGION=us-east-1
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
def run_with_boto3() -> None:
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
        memoryId=memory_id, actorId=ACTOR_ID, sessionId=SESSION_ID, includePayloads=True,
        filter={"eventMetadata": [{
            "left": {"metadataKey": "topic"}, "operator": "EQUALS_TO",
            "right": {"metadataValue": {"stringValue": "health"}},
        }]},
    )["events"]
    print(f"[boto3] Health-tagged events: {len(health)}")

    priority = data.list_events(
        memoryId=memory_id, actorId=ACTOR_ID, sessionId=SESSION_ID, includePayloads=True,
        filter={"eventMetadata": [
            {"left": {"metadataKey": "priority"}, "operator": "EXISTS"}
        ]},
    )["events"]
    print(f"[boto3] Events with priority set: {len(priority)}")

    control.delete_memory(memoryId=memory_id, clientToken=str(uuid.uuid4()))
    print(f"[boto3] Deleted memory {memory_id}")


# === AgentCore SDK ====================================================
# MemoryClient.create_event does not accept event metadata, and list_events
# does not accept a filter. To use event metadata filtering, drop down to
# boto3 (see run_with_boto3 above) or call client.gmcp_client directly.
def run_with_sdk() -> None:
    print(
        "[sdk] Event metadata is not exposed by MemoryClient.\n"
        "      Use the boto3 path for CreateEvent metadata + ListEvents filter.\n"
        "      Tracking: bedrock_agentcore.memory.MemoryClient.create_event has\n"
        "      no `metadata=` parameter; list_events has no `filter=` parameter."
    )


# === AWS CLI ==========================================================
CLI_WALKTHROUGH = """\
# 1. Create memory
aws bedrock-agentcore-control create-memory \\
  --region "$AWS_REGION" --name "EventMetaCli-$(date +%s)" \\
  --event-expiry-duration 30 --client-token "$(uuidgen)"
export MEMORY_ID=<id>

# 2. Append an event with metadata. Metadata values are typed (stringValue).
aws bedrock-agentcore create-event \\
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \\
  --actor-id user-42 --session-id sess-cli \\
  --event-timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \\
  --payload '[{"conversational":{"role":"USER","content":{"text":"I had a fever."}}}]' \\
  --metadata '{"topic":{"stringValue":"health"},"priority":{"stringValue":"high"}}'

# 3. ListEvents filtered to topic=health
aws bedrock-agentcore list-events \\
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \\
  --actor-id user-42 --session-id sess-cli --include-payloads \\
  --filter '{
    "eventMetadata": [{
      "left":  {"metadataKey": "topic"},
      "operator": "EQUALS_TO",
      "right": {"metadataValue": {"stringValue": "health"}}
    }]
  }'

# 4. ListEvents filtered to events that have a priority key set
aws bedrock-agentcore list-events \\
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \\
  --actor-id user-42 --session-id sess-cli --include-payloads \\
  --filter '{"eventMetadata":[{"left":{"metadataKey":"priority"},"operator":"EXISTS"}]}'

# 5. Teardown
aws bedrock-agentcore-control delete-memory \\
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" --client-token "$(uuidgen)"
"""


def main() -> None:
    surface = sys.argv[1] if len(sys.argv) > 1 else "boto3"
    if surface == "boto3":
        run_with_boto3()
    elif surface == "sdk":
        run_with_sdk()
    elif surface == "cli":
        print(CLI_WALKTHROUGH)
    else:
        print(f"Unknown surface {surface!r}. Use boto3 | sdk | cli.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

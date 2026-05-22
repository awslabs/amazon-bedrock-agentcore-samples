"""User preference memory strategy — stable per-user settings.

What you learn:
    - Configure `userPreferenceMemoryStrategy` on CreateMemory
    - Mention a preference in conversation, wait for extraction
    - Retrieve preferences with RetrieveMemoryRecords

User-preference strategy extracts stable, persistent preferences
("prefers vegetarian food", "wants email notifications, not SMS").
Use it for personalisation that should outlive any single session.

Three surfaces:
    python user-preference.py boto3
    python user-preference.py sdk
    python user-preference.py cli

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
ACTOR_ID = "user-alex"
SESSION_ID = f"sess-{int(time.time())}"
EXTRACTION_WAIT_SECONDS = 60
NAMESPACE_TEMPLATE = "/users/{actorId}/preferences/"

TURNS = [
    ("USER", "I prefer window seats on flights, and aisle seats on trains."),
    ("ASSISTANT", "Noted."),
    ("USER", "I'm vegetarian — please always assume that for restaurants."),
    ("ASSISTANT", "Understood."),
    ("USER", "I prefer to receive booking confirmations by email, not SMS."),
    ("ASSISTANT", "Will do."),
]


# === boto3 ============================================================
def run_with_boto3() -> None:
    import boto3

    control = boto3.client("bedrock-agentcore-control", region_name=REGION)
    data = boto3.client("bedrock-agentcore", region_name=REGION)

    memory_id = control.create_memory(
        name=f"UserPref_{int(time.time())}",
        description="User preference strategy (boto3)",
        eventExpiryDuration=30,
        memoryStrategies=[{
            "userPreferenceMemoryStrategy": {
                "name": "UserPreferences",
                "description": "Stable preferences across sessions",
                "namespaces": [NAMESPACE_TEMPLATE],
            }
        }],
    )["memory"]["id"]
    print(f"[boto3] Created memory {memory_id}")
    deadline = time.time() + 300
    while time.time() < deadline:
        if control.get_memory(memoryId=memory_id)["memory"]["status"] == "ACTIVE":
            break
        time.sleep(5)

    for role, text in TURNS:
        data.create_event(
            memoryId=memory_id, actorId=ACTOR_ID, sessionId=SESSION_ID,
            eventTimestamp=datetime.now(timezone.utc),
            payload=[{"conversational": {"role": role, "content": {"text": text}}}],
        )
    print(f"[boto3] Waiting {EXTRACTION_WAIT_SECONDS}s for extraction...")
    time.sleep(EXTRACTION_WAIT_SECONDS)

    namespace = NAMESPACE_TEMPLATE.format(actorId=ACTOR_ID)
    hits = data.retrieve_memory_records(
        memoryId=memory_id, namespace=namespace,
        searchCriteria={"searchQuery": "user's preferences", "topK": 10},
    )["memoryRecordSummaries"]
    print(f"\n[boto3] Preferences in {namespace}:")
    for h in hits:
        print(f"  - {h['content']['text']}")

    control.delete_memory(memoryId=memory_id, clientToken=str(uuid.uuid4()))
    print(f"\n[boto3] Deleted memory {memory_id}")


# === AgentCore SDK ====================================================
def run_with_sdk() -> None:
    from bedrock_agentcore.memory import MemoryClient

    client = MemoryClient(region_name=REGION)
    memory = client.create_memory_and_wait(
        name=f"UserPrefSdk_{int(time.time())}",
        description="User preference strategy (SDK)",
        strategies=[{
            "userPreferenceMemoryStrategy": {
                "name": "UserPreferences",
                "description": "Stable preferences across sessions",
                "namespaces": [NAMESPACE_TEMPLATE],
            }
        }],
        event_expiry_days=30,
    )
    memory_id = memory["id"]
    print(f"[sdk] Created memory {memory_id}")

    client.create_event(
        memory_id=memory_id, actor_id=ACTOR_ID, session_id=SESSION_ID,
        messages=[(text, role) for role, text in TURNS],
    )
    print(f"[sdk] Waiting {EXTRACTION_WAIT_SECONDS}s for extraction...")
    time.sleep(EXTRACTION_WAIT_SECONDS)

    namespace = NAMESPACE_TEMPLATE.format(actorId=ACTOR_ID)
    hits = client.retrieve_memories(
        memory_id=memory_id, namespace=namespace,
        query="user's preferences", top_k=10,
    )
    print(f"\n[sdk] Preferences in {namespace}:")
    for h in hits:
        print(f"  - {h['content']['text']}")

    client.delete_memory_and_wait(memory_id=memory_id)
    print(f"\n[sdk] Deleted memory {memory_id}")


# === AWS CLI ==========================================================
CLI_WALKTHROUGH = """\
# 1. Create memory with a user-preference strategy
aws bedrock-agentcore-control create-memory \\
  --region "$AWS_REGION" --name "UserPrefCli-$(date +%s)" \\
  --event-expiry-duration 30 --client-token "$(uuidgen)" \\
  --memory-strategies '[{
    "userPreferenceMemoryStrategy": {
      "name": "UserPreferences",
      "description": "Stable preferences across sessions",
      "namespaces": ["/users/{actorId}/preferences/"]
    }
  }]'
export MEMORY_ID=<id>

# 2. Mention a few preferences
aws bedrock-agentcore create-event \\
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \\
  --actor-id user-alex --session-id sess-cli \\
  --event-timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \\
  --payload '[{"conversational":{"role":"USER","content":{"text":"I prefer window seats and email notifications."}}}]'

# 3. Wait ~60s, then retrieve
sleep 60
aws bedrock-agentcore retrieve-memory-records \\
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \\
  --namespace "/users/user-alex/preferences/" \\
  --search-criteria '{"searchQuery":"preferences","topK":10}'

# 4. Teardown
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

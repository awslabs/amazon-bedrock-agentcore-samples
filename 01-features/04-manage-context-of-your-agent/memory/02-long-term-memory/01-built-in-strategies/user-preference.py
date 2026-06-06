"""User preference memory strategy — stable per-user settings.

What you learn:
    - Configure `userPreferenceMemoryStrategy` on CreateMemory
    - Mention a preference in conversation, wait for extraction
    - Retrieve preferences with RetrieveMemoryRecords

User-preference strategy extracts stable, persistent preferences
("prefers vegetarian food", "wants email notifications, not SMS").
Use it for personalisation that should outlive any single session.

Three surfaces:
    python user-preference.py boto3      # raw boto3 (bedrock-agentcore / -control)
    python user-preference.py sdk        # AgentCore SDK, low-level MemoryClient
    python user-preference.py session    # AgentCore SDK, high-level MemorySessionManager

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
ACTOR_ID = "user-alex"
SESSION_ID = f"sess-{int(time.time())}"
EXTRACTION_WAIT_SECONDS = 60
# Preference extraction is semantic-class; it surfaced ~64s in testing, so the
# high-level session surface waits 90s (with margin) rather than the 60s above.
SESSION_EXTRACTION_WAIT_SECONDS = 90
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
def run_with_boto3(cleanup: bool = False) -> None:
    import boto3

    control = boto3.client("bedrock-agentcore-control", region_name=REGION)
    data = boto3.client("bedrock-agentcore", region_name=REGION)

    memory_id = control.create_memory(
        name=f"UserPref_{int(time.time())}",
        description="User preference strategy (boto3)",
        eventExpiryDuration=30,
        memoryStrategies=[
            {
                "userPreferenceMemoryStrategy": {
                    "name": "UserPreferences",
                    "description": "Stable preferences across sessions",
                    "namespaces": [NAMESPACE_TEMPLATE],
                }
            }
        ],
    )["memory"]["id"]
    print(f"[boto3] Created memory {memory_id}")
    deadline = time.time() + 300
    while time.time() < deadline:
        if control.get_memory(memoryId=memory_id)["memory"]["status"] == "ACTIVE":
            break
        time.sleep(5)

    for role, text in TURNS:
        data.create_event(
            memoryId=memory_id,
            actorId=ACTOR_ID,
            sessionId=SESSION_ID,
            eventTimestamp=datetime.now(timezone.utc),
            payload=[{"conversational": {"role": role, "content": {"text": text}}}],
        )
    print(f"[boto3] Waiting {EXTRACTION_WAIT_SECONDS}s for extraction...")
    time.sleep(EXTRACTION_WAIT_SECONDS)

    namespace = NAMESPACE_TEMPLATE.format(actorId=ACTOR_ID)
    hits = data.retrieve_memory_records(
        memoryId=memory_id,
        namespace=namespace,
        searchCriteria={"searchQuery": "user's preferences", "topK": 10},
    )["memoryRecordSummaries"]
    print(f"\n[boto3] Preferences in {namespace}:")
    for h in hits:
        print(f"  - {h['content']['text']}")

    if cleanup:
        control.delete_memory(memoryId=memory_id, clientToken=str(uuid.uuid4()))
        print(f"\n[boto3] Deleted memory {memory_id}")
    else:
        print(f"\n[boto3] Keeping memory {memory_id} (pass --cleanup to delete)")


# === AgentCore SDK ====================================================
def run_with_sdk(cleanup: bool = False) -> None:
    from bedrock_agentcore.memory import MemoryClient

    client = MemoryClient(region_name=REGION)
    memory = client.create_memory_and_wait(
        name=f"UserPrefSdk_{int(time.time())}",
        description="User preference strategy (SDK)",
        strategies=[
            {
                "userPreferenceMemoryStrategy": {
                    "name": "UserPreferences",
                    "description": "Stable preferences across sessions",
                    "namespaces": [NAMESPACE_TEMPLATE],
                }
            }
        ],
        event_expiry_days=30,
    )
    memory_id = memory["id"]
    print(f"[sdk] Created memory {memory_id}")

    client.create_event(
        memory_id=memory_id,
        actor_id=ACTOR_ID,
        session_id=SESSION_ID,
        messages=[(text, role) for role, text in TURNS],
    )
    print(f"[sdk] Waiting {EXTRACTION_WAIT_SECONDS}s for extraction...")
    time.sleep(EXTRACTION_WAIT_SECONDS)

    namespace = NAMESPACE_TEMPLATE.format(actorId=ACTOR_ID)
    hits = client.retrieve_memories(
        memory_id=memory_id,
        namespace=namespace,
        query="user's preferences",
        top_k=10,
    )
    print(f"\n[sdk] Preferences in {namespace}:")
    for h in hits:
        print(f"  - {h['content']['text']}")

    if cleanup:
        client.delete_memory_and_wait(memory_id=memory_id)
        print(f"\n[sdk] Deleted memory {memory_id}")
    else:
        print(f"\n[sdk] Keeping memory {memory_id} (pass --cleanup to delete)")


# === AgentCore SDK — high-level session API ==========================
def run_with_session(cleanup: bool = False) -> None:
    # MemoryClient owns the control plane (create/delete the resource);
    # MemorySessionManager is data-plane only, so we create the memory with
    # MemoryClient, then drive events + retrieval through a MemorySession.
    from bedrock_agentcore.memory import MemoryClient, MemorySessionManager
    from bedrock_agentcore.memory.constants import ConversationalMessage, MessageRole

    client = MemoryClient(region_name=REGION)
    memory = client.create_memory_and_wait(
        name=f"UserPrefSession_{int(time.time())}",
        description="User preference strategy (SDK session API)",
        strategies=[
            {
                "userPreferenceMemoryStrategy": {
                    "name": "UserPreferences",
                    "description": "Stable preferences across sessions",
                    # Current field is namespaceTemplates (namespaces is deprecated).
                    "namespaceTemplates": [NAMESPACE_TEMPLATE],
                }
            }
        ],
        event_expiry_days=30,
    )
    memory_id = memory["id"]
    print(f"[session] Created memory {memory_id}")

    # Bind a session, then write all turns in one add_turns call. add_turns
    # takes ConversationalMessage objects and maps to a single create_event.
    manager = MemorySessionManager(memory_id=memory_id, region_name=REGION)
    session = manager.create_memory_session(actor_id=ACTOR_ID, session_id=SESSION_ID)
    session.add_turns(
        messages=[ConversationalMessage(text, MessageRole[role]) for role, text in TURNS]
    )
    print(f"[session] Waiting {SESSION_EXTRACTION_WAIT_SECONDS}s for extraction...")
    time.sleep(SESSION_EXTRACTION_WAIT_SECONDS)

    namespace = NAMESPACE_TEMPLATE.format(actorId=ACTOR_ID)
    # Use namespace= (exact match); namespace_prefix= is deprecated.
    hits = session.search_long_term_memories(
        query="user's preferences", namespace=namespace, top_k=10
    )
    print(f"\n[session] Preferences in {namespace}:")
    for h in hits:
        # Each hit is a MemoryRecord (dict-like): content.text + score.
        print(f"  - {h['content']['text']}")

    if cleanup:
        client.delete_memory_and_wait(memory_id=memory_id)
        print(f"\n[session] Deleted memory {memory_id}")
    else:
        print(f"\n[session] Keeping memory {memory_id} (pass --cleanup to delete)")


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--cleanup"]
    cleanup = "--cleanup" in sys.argv[1:]
    surface = args[0] if args else "boto3"
    if surface == "boto3":
        run_with_boto3(cleanup=cleanup)
    elif surface == "sdk":
        run_with_sdk(cleanup=cleanup)
    elif surface == "session":
        run_with_session(cleanup=cleanup)
    else:
        print(f"Unknown surface {surface!r}. Use boto3 | sdk | session.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

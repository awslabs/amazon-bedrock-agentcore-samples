"""Episodic memory strategy — meaningful interaction sequences.

What you learn:
    - Configure `episodicMemoryStrategy` on CreateMemory
    - Drive a multi-turn interaction that has a beginning/middle/end
    - Retrieve episodes via RetrieveMemoryRecords

Episodic strategy captures "episodes" — meaningful sequences of turns
that hang together as one event in the user's life ("debugged a memory
leak in service X on Tuesday"). It also adds a *reflection* step that
generates cross-episode insights.

Two surfaces:
    python episodic.py boto3
    python episodic.py sdk

Add `--cleanup` to delete the memory resource at the end. By default the
memory is kept so you can inspect it; the script prints the memoryId.

SDK note: MemoryClient has no dedicated `add_episodic_strategy()` helper,
but `create_memory_and_wait` accepts the raw `episodicMemoryStrategy`
shape in its `strategies` list — shown below.

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
EXTRACTION_WAIT_SECONDS = 90
NAMESPACE_TEMPLATE = "/episodes/{actorId}/"

DEBUG_TURNS = [
    ("USER", "I'm seeing a memory leak in the payment service after the last deploy."),
    ("ASSISTANT", "When did the leak start?"),
    ("USER", "Right after we shipped the new caching layer on Monday."),
    ("ASSISTANT", "Have you checked for unbounded growth in the cache?"),
    ("USER", "Yes — found it. The TTL was unset; it's now fixed in v2.4.1."),
    ("ASSISTANT", "Great catch. I'll remember that the cache TTL was the culprit."),
]
DESIGN_TURNS = [
    ("USER", "Designing the new notifications service. Start with email or push?"),
    ("ASSISTANT", "What's the primary user persona?"),
    ("USER", "Mobile-first consumers."),
    ("ASSISTANT", "Then push-first makes sense; layer email later for transactional confirmations."),
    ("USER", "Agreed — we'll go push-first with FCM and APNs."),
]
QUERIES = ["memory leak debugging", "notifications design decisions"]


# === boto3 ============================================================
def run_with_boto3(cleanup: bool = False) -> None:
    import boto3

    control = boto3.client("bedrock-agentcore-control", region_name=REGION)
    data = boto3.client("bedrock-agentcore", region_name=REGION)

    memory_id = control.create_memory(
        name=f"Episodic_{int(time.time())}",
        description="Episodic strategy (boto3)",
        eventExpiryDuration=30,
        memoryStrategies=[
            {
                "episodicMemoryStrategy": {
                    "name": "Episodes",
                    "description": "Meaningful interaction sequences",
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

    for session_id, turns in [
        (f"debug-{int(time.time())}", DEBUG_TURNS),
        (f"design-{int(time.time())}", DESIGN_TURNS),
    ]:
        for role, text in turns:
            data.create_event(
                memoryId=memory_id,
                actorId=ACTOR_ID,
                sessionId=session_id,
                eventTimestamp=datetime.now(timezone.utc),
                payload=[{"conversational": {"role": role, "content": {"text": text}}}],
            )

    print(f"[boto3] Waiting {EXTRACTION_WAIT_SECONDS}s for extraction + reflection...")
    time.sleep(EXTRACTION_WAIT_SECONDS)

    namespace = NAMESPACE_TEMPLATE.format(actorId=ACTOR_ID)
    for query in QUERIES:
        hits = data.retrieve_memory_records(
            memoryId=memory_id,
            namespace=namespace,
            searchCriteria={"searchQuery": query, "topK": 3},
        )["memoryRecordSummaries"]
        print(f"\n[boto3] Q: {query}")
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
    # No add_episodic_strategy() helper — pass the raw strategy shape.
    memory = client.create_memory_and_wait(
        name=f"EpisodicSdk_{int(time.time())}",
        description="Episodic strategy (SDK)",
        strategies=[
            {
                "episodicMemoryStrategy": {
                    "name": "Episodes",
                    "description": "Meaningful interaction sequences",
                    "namespaces": [NAMESPACE_TEMPLATE],
                }
            }
        ],
        event_expiry_days=30,
    )
    memory_id = memory["id"]
    print(f"[sdk] Created memory {memory_id}")

    for session_id, turns in [
        (f"debug-sdk-{int(time.time())}", DEBUG_TURNS),
        (f"design-sdk-{int(time.time())}", DESIGN_TURNS),
    ]:
        client.create_event(
            memory_id=memory_id,
            actor_id=ACTOR_ID,
            session_id=session_id,
            messages=[(text, role) for role, text in turns],
        )

    print(f"[sdk] Waiting {EXTRACTION_WAIT_SECONDS}s for extraction + reflection...")
    time.sleep(EXTRACTION_WAIT_SECONDS)

    namespace = NAMESPACE_TEMPLATE.format(actorId=ACTOR_ID)
    for query in QUERIES:
        hits = client.retrieve_memories(memory_id=memory_id, namespace=namespace, query=query, top_k=3)
        print(f"\n[sdk] Q: {query}")
        for h in hits:
            print(f"  - {h['content']['text']}")

    if cleanup:
        client.delete_memory_and_wait(memory_id=memory_id)
        print(f"\n[sdk] Deleted memory {memory_id}")
    else:
        print(f"\n[sdk] Keeping memory {memory_id} (pass --cleanup to delete)")


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

"""Episodic memory strategy — meaningful interaction sequences.

What you learn:
    - Configure `episodicMemoryStrategy` on CreateMemory
    - Drive a multi-turn interaction that has a beginning/middle/end
    - Retrieve episodes via RetrieveMemoryRecords

Episodic strategy captures "episodes" — meaningful sequences of turns
that hang together as one event in the user's life ("debugged a memory
leak in service X on Tuesday"). It also adds a *reflection* step that
generates cross-episode insights.

Three surfaces:
    python episodic.py boto3
    python episodic.py sdk
    python episodic.py cli

SDK note: MemoryClient has no `add_episodic_strategy()` helper, but
create_memory_and_wait accepts the raw `episodicMemoryStrategy` shape
in its `strategies` list — shown below.

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
def run_with_boto3() -> None:
    import boto3

    control = boto3.client("bedrock-agentcore-control", region_name=REGION)
    data = boto3.client("bedrock-agentcore", region_name=REGION)

    memory_id = control.create_memory(
        name=f"Episodic_{int(time.time())}",
        description="Episodic strategy (boto3)",
        eventExpiryDuration=30,
        memoryStrategies=[{
            "episodicMemoryStrategy": {
                "name": "Episodes",
                "description": "Meaningful interaction sequences",
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

    for session_id, turns in [
        (f"debug-{int(time.time())}", DEBUG_TURNS),
        (f"design-{int(time.time())}", DESIGN_TURNS),
    ]:
        for role, text in turns:
            data.create_event(
                memoryId=memory_id, actorId=ACTOR_ID, sessionId=session_id,
                eventTimestamp=datetime.now(timezone.utc),
                payload=[{"conversational": {"role": role, "content": {"text": text}}}],
            )

    print(f"[boto3] Waiting {EXTRACTION_WAIT_SECONDS}s for extraction + reflection...")
    time.sleep(EXTRACTION_WAIT_SECONDS)

    namespace = NAMESPACE_TEMPLATE.format(actorId=ACTOR_ID)
    for query in QUERIES:
        hits = data.retrieve_memory_records(
            memoryId=memory_id, namespace=namespace,
            searchCriteria={"searchQuery": query, "topK": 3},
        )["memoryRecordSummaries"]
        print(f"\n[boto3] Q: {query}")
        for h in hits:
            print(f"  - {h['content']['text']}")

    control.delete_memory(memoryId=memory_id, clientToken=str(uuid.uuid4()))
    print(f"\n[boto3] Deleted memory {memory_id}")


# === AgentCore SDK ====================================================
def run_with_sdk() -> None:
    from bedrock_agentcore.memory import MemoryClient

    client = MemoryClient(region_name=REGION)
    # No add_episodic_strategy() helper — pass the raw strategy shape.
    memory = client.create_memory_and_wait(
        name=f"EpisodicSdk_{int(time.time())}",
        description="Episodic strategy (SDK)",
        strategies=[{
            "episodicMemoryStrategy": {
                "name": "Episodes",
                "description": "Meaningful interaction sequences",
                "namespaces": [NAMESPACE_TEMPLATE],
            }
        }],
        event_expiry_days=30,
    )
    memory_id = memory["id"]
    print(f"[sdk] Created memory {memory_id}")

    for session_id, turns in [
        (f"debug-sdk-{int(time.time())}", DEBUG_TURNS),
        (f"design-sdk-{int(time.time())}", DESIGN_TURNS),
    ]:
        client.create_event(
            memory_id=memory_id, actor_id=ACTOR_ID, session_id=session_id,
            messages=[(text, role) for role, text in turns],
        )

    print(f"[sdk] Waiting {EXTRACTION_WAIT_SECONDS}s for extraction + reflection...")
    time.sleep(EXTRACTION_WAIT_SECONDS)

    namespace = NAMESPACE_TEMPLATE.format(actorId=ACTOR_ID)
    for query in QUERIES:
        hits = client.retrieve_memories(
            memory_id=memory_id, namespace=namespace, query=query, top_k=3
        )
        print(f"\n[sdk] Q: {query}")
        for h in hits:
            print(f"  - {h['content']['text']}")

    client.delete_memory_and_wait(memory_id=memory_id)
    print(f"\n[sdk] Deleted memory {memory_id}")


# === AWS CLI ==========================================================
CLI_WALKTHROUGH = """\
# 1. Create memory with an episodic strategy
aws bedrock-agentcore-control create-memory \\
  --region "$AWS_REGION" --name "EpisodicCli-$(date +%s)" \\
  --event-expiry-duration 30 --client-token "$(uuidgen)" \\
  --memory-strategies '[{
    "episodicMemoryStrategy": {
      "name": "Episodes",
      "description": "Meaningful interaction sequences",
      "namespaces": ["/episodes/{actorId}/"]
    }
  }]'
export MEMORY_ID=<id>

# 2. Drive a multi-turn session that forms one episode (loop several events).
aws bedrock-agentcore create-event \\
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \\
  --actor-id user-alex --session-id debug-sess \\
  --event-timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \\
  --payload '[{"conversational":{"role":"USER","content":{"text":"Memory leak after deploy."}}}]'
# ... repeat to form a coherent episode ...

# 3. Wait ~90s for extraction + reflection, then retrieve.
sleep 90
aws bedrock-agentcore retrieve-memory-records \\
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \\
  --namespace "/episodes/user-alex/" \\
  --search-criteria '{"searchQuery":"memory leak debugging","topK":3}'

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

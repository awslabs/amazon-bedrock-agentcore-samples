"""Semantic memory strategy — extracting standalone facts.

What you learn:
    - Configure `semanticMemoryStrategy` on CreateMemory
    - Drive a short conversation, wait for asynchronous extraction
    - Retrieve facts back via RetrieveMemoryRecords (vector search)

Semantic strategy extracts standalone facts about the user or the world
("user's name is Alex", "based in Berlin"). It is the default choice for
"who is this user?" recall.

Three surfaces:
    python semantic.py boto3
    python semantic.py sdk
    python semantic.py cli

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
NAMESPACE_TEMPLATE = "/users/{actorId}/facts/"

TURNS = [
    ("USER", "Hi, I'm Alex. I'm based in Berlin and I work as a backend engineer."),
    ("ASSISTANT", "Nice to meet you, Alex."),
    ("USER", "I prefer Python over Java for most things, but I write Rust for performance-critical code."),
    ("ASSISTANT", "Good to know."),
    ("USER", "Also, I'm allergic to peanuts."),
    ("ASSISTANT", "I'll keep that in mind."),
]
QUERIES = [
    "What programming languages does the user prefer?",
    "Where is the user based?",
    "Any dietary restrictions?",
]


# === boto3 ============================================================
def run_with_boto3() -> None:
    import boto3

    control = boto3.client("bedrock-agentcore-control", region_name=REGION)
    data = boto3.client("bedrock-agentcore", region_name=REGION)

    memory_id = control.create_memory(
        name=f"Semantic_{int(time.time())}",
        description="Semantic strategy tutorial (boto3)",
        eventExpiryDuration=30,
        memoryStrategies=[{
            "semanticMemoryStrategy": {
                "name": "UserFacts",
                "description": "Standalone facts about the user",
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
    for query in QUERIES:
        hits = data.retrieve_memory_records(
            memoryId=memory_id, namespace=namespace,
            searchCriteria={"searchQuery": query, "topK": 3},
        )["memoryRecordSummaries"]
        print(f"\n[boto3] Q: {query}")
        for h in hits:
            print(f"  - {h['content']['text']} (score={h.get('score')})")

    control.delete_memory(memoryId=memory_id, clientToken=str(uuid.uuid4()))
    print(f"\n[boto3] Deleted memory {memory_id}")


# === AgentCore SDK ====================================================
def run_with_sdk() -> None:
    from bedrock_agentcore.memory import MemoryClient

    client = MemoryClient(region_name=REGION)
    # add_semantic_strategy is the SDK helper for the same shape as boto3.
    memory = client.create_memory_and_wait(
        name=f"SemanticSdk_{int(time.time())}",
        description="Semantic strategy (SDK)",
        strategies=[{
            "semanticMemoryStrategy": {
                "name": "UserFacts",
                "description": "Standalone facts about the user",
                "namespaces": [NAMESPACE_TEMPLATE],
            }
        }],
        event_expiry_days=30,
    )
    memory_id = memory["id"]
    print(f"[sdk] Created memory {memory_id}")

    # SDK takes (text, role) tuples and groups multiple messages into one event.
    client.create_event(
        memory_id=memory_id, actor_id=ACTOR_ID, session_id=SESSION_ID,
        messages=[(text, role) for role, text in TURNS],
    )
    print(f"[sdk] Waiting {EXTRACTION_WAIT_SECONDS}s for extraction...")
    time.sleep(EXTRACTION_WAIT_SECONDS)

    namespace = NAMESPACE_TEMPLATE.format(actorId=ACTOR_ID)
    for query in QUERIES:
        hits = client.retrieve_memories(
            memory_id=memory_id, namespace=namespace, query=query, top_k=3
        )
        print(f"\n[sdk] Q: {query}")
        for h in hits:
            print(f"  - {h['content']['text']} (score={h.get('score')})")

    client.delete_memory_and_wait(memory_id=memory_id)
    print(f"\n[sdk] Deleted memory {memory_id}")


# === AWS CLI ==========================================================
CLI_WALKTHROUGH = """\
# 1. Create memory with a semantic strategy
aws bedrock-agentcore-control create-memory \\
  --region "$AWS_REGION" --name "SemanticCli-$(date +%s)" \\
  --event-expiry-duration 30 --client-token "$(uuidgen)" \\
  --memory-strategies '[{
    "semanticMemoryStrategy": {
      "name": "UserFacts",
      "description": "Standalone facts about the user",
      "namespaces": ["/users/{actorId}/facts/"]
    }
  }]'
export MEMORY_ID=<id>

# 2. Drive a short conversation
aws bedrock-agentcore create-event \\
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \\
  --actor-id user-alex --session-id sess-cli \\
  --event-timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \\
  --payload '[{"conversational":{"role":"USER","content":{"text":"I prefer Python and live in Berlin."}}}]'

# 3. Wait for extraction (~60s) and retrieve
sleep 60
aws bedrock-agentcore retrieve-memory-records \\
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \\
  --namespace "/users/user-alex/facts/" \\
  --search-criteria '{"searchQuery":"language preference?","topK":3}'

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

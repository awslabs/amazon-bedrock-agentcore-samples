"""Summary memory strategy — rolling conversation summaries.

What you learn:
    - Configure `summaryMemoryStrategy` on CreateMemory
    - Drive a multi-turn conversation
    - Retrieve the rolling summary via RetrieveMemoryRecords

Summary strategy maintains a rolling, condensed view of the conversation.
Use it when you need to feed a long conversation into an LLM with a
bounded context window — give the model the rolling summary instead of
the raw transcript.

Three surfaces:
    python summary.py boto3
    python summary.py sdk
    python summary.py cli

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
EXTRACTION_WAIT_SECONDS = 75
NAMESPACE_TEMPLATE = "/sessions/{sessionId}/summary/"

TURNS = [
    ("USER", "I'd like to plan a 10-day trip to Japan in October."),
    ("ASSISTANT", "Great. Are you going for cultural sites, food, or nature?"),
    ("USER", "All three. I want to spend 4 days in Tokyo, 3 in Kyoto, and 3 in Hokkaido."),
    ("ASSISTANT", "Got it. Hokkaido in October is autumn foliage season — beautiful."),
    ("USER", "Budget is around 4000 EUR including flights from Berlin."),
    ("ASSISTANT", "That's reasonable for shoulder season."),
    ("USER", "I also want to do a day trip to Nikko from Tokyo."),
    ("ASSISTANT", "Nikko is a great choice for shrines and forests."),
]


# === boto3 ============================================================
def run_with_boto3() -> None:
    import boto3

    control = boto3.client("bedrock-agentcore-control", region_name=REGION)
    data = boto3.client("bedrock-agentcore", region_name=REGION)

    memory_id = control.create_memory(
        name=f"Summary_{int(time.time())}",
        description="Summary strategy (boto3)",
        eventExpiryDuration=30,
        memoryStrategies=[{
            "summaryMemoryStrategy": {
                "name": "SessionSummary",
                "description": "Rolling conversation summary",
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
    print(f"[boto3] Waiting {EXTRACTION_WAIT_SECONDS}s for summary consolidation...")
    time.sleep(EXTRACTION_WAIT_SECONDS)

    namespace = NAMESPACE_TEMPLATE.format(sessionId=SESSION_ID)
    hits = data.retrieve_memory_records(
        memoryId=memory_id, namespace=namespace,
        searchCriteria={"searchQuery": "trip plan", "topK": 5},
    )["memoryRecordSummaries"]
    print(f"\n[boto3] Summary records in {namespace}:")
    for h in hits:
        print(f"  - {h['content']['text']}")

    control.delete_memory(memoryId=memory_id, clientToken=str(uuid.uuid4()))
    print(f"\n[boto3] Deleted memory {memory_id}")


# === AgentCore SDK ====================================================
def run_with_sdk() -> None:
    from bedrock_agentcore.memory import MemoryClient

    client = MemoryClient(region_name=REGION)
    memory = client.create_memory_and_wait(
        name=f"SummarySdk_{int(time.time())}",
        description="Summary strategy (SDK)",
        strategies=[{
            "summaryMemoryStrategy": {
                "name": "SessionSummary",
                "description": "Rolling conversation summary",
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
    print(f"[sdk] Waiting {EXTRACTION_WAIT_SECONDS}s for summary consolidation...")
    time.sleep(EXTRACTION_WAIT_SECONDS)

    namespace = NAMESPACE_TEMPLATE.format(sessionId=SESSION_ID)
    hits = client.retrieve_memories(
        memory_id=memory_id, namespace=namespace, query="trip plan", top_k=5
    )
    print(f"\n[sdk] Summary records in {namespace}:")
    for h in hits:
        print(f"  - {h['content']['text']}")

    client.delete_memory_and_wait(memory_id=memory_id)
    print(f"\n[sdk] Deleted memory {memory_id}")


# === AWS CLI ==========================================================
CLI_WALKTHROUGH = """\
# 1. Create memory with a summary strategy. Summaries are typically per-session.
aws bedrock-agentcore-control create-memory \\
  --region "$AWS_REGION" --name "SummaryCli-$(date +%s)" \\
  --event-expiry-duration 30 --client-token "$(uuidgen)" \\
  --memory-strategies '[{
    "summaryMemoryStrategy": {
      "name": "SessionSummary",
      "description": "Rolling conversation summary",
      "namespaces": ["/sessions/{sessionId}/summary/"]
    }
  }]'
export MEMORY_ID=<id>

# 2. Drive a multi-turn conversation (loop several create-event calls).
aws bedrock-agentcore create-event \\
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \\
  --actor-id user-alex --session-id sess-cli \\
  --event-timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \\
  --payload '[{"conversational":{"role":"USER","content":{"text":"Plan a 10-day trip to Japan."}}}]'
# ... repeat for additional turns ...

# 3. Wait ~75s for consolidation, then retrieve the rolling summary.
sleep 75
aws bedrock-agentcore retrieve-memory-records \\
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \\
  --namespace "/sessions/sess-cli/summary/" \\
  --search-criteria '{"searchQuery":"trip plan","topK":5}'

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

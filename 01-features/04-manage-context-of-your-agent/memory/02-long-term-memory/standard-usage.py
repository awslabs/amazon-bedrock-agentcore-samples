"""Standard usage of AgentCore long-term memory.

The canonical long-term flow:
    1. create a memory resource with a built-in semantic strategy
    2. wait until the memory is ACTIVE
    3. drive a short conversation via CreateEvent
    4. wait for asynchronous extraction (~60s)
    5. retrieve relevant records with RetrieveMemoryRecords
    6. tear down

Two surfaces:
    python standard-usage.py boto3
    python standard-usage.py sdk

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
EXTRACTION_WAIT_SECONDS = 60
NAMESPACE_TEMPLATE = "/users/{actorId}/facts/"


# === boto3 ============================================================
def run_with_boto3(cleanup: bool = False) -> None:
    import boto3

    control = boto3.client("bedrock-agentcore-control", region_name=REGION)
    data = boto3.client("bedrock-agentcore", region_name=REGION)

    memory_id = control.create_memory(
        name=f"LtmStandard_{int(time.time())}",
        description="Long-term memory standard usage (boto3)",
        eventExpiryDuration=30,
        memoryStrategies=[
            {
                "semanticMemoryStrategy": {
                    "name": "UserFacts",
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

    for role, text in [
        ("USER", "I'm Alex. I prefer Python over Java and I'm based in Berlin."),
        ("ASSISTANT", "Got it, Alex."),
        ("USER", "I'm allergic to peanuts, by the way."),
        ("ASSISTANT", "Noted."),
    ]:
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
        searchCriteria={"searchQuery": "Alex's preferences and constraints?", "topK": 5},
    )["memoryRecordSummaries"]
    print(f"[boto3] Retrieved {len(hits)} records from {namespace}")
    for h in hits:
        print(f"  - {h['content']['text']}")

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
        name=f"LtmStandardSdk_{int(time.time())}",
        description="Long-term memory standard usage (SDK)",
        strategies=[
            {
                "semanticMemoryStrategy": {
                    "name": "UserFacts",
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
        messages=[
            ("I'm Alex. I prefer Python over Java and I'm based in Berlin.", "USER"),
            ("Got it, Alex.", "ASSISTANT"),
            ("I'm allergic to peanuts, by the way.", "USER"),
            ("Noted.", "ASSISTANT"),
        ],
    )

    print(f"[sdk] Waiting {EXTRACTION_WAIT_SECONDS}s for extraction...")
    time.sleep(EXTRACTION_WAIT_SECONDS)

    namespace = NAMESPACE_TEMPLATE.format(actorId=ACTOR_ID)
    hits = client.retrieve_memories(
        memory_id=memory_id,
        namespace=namespace,
        query="Alex's preferences and constraints?",
        top_k=5,
    )
    print(f"[sdk] Retrieved {len(hits)} records from {namespace}")
    for h in hits:
        print(f"  - {h['content']['text']}")

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

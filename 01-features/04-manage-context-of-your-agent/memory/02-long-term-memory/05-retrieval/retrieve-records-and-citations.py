"""Retrieving long-term memory records.

What you learn:
    - RetrieveMemoryRecords for semantic search inside a namespace
    - ListMemoryRecords to enumerate without a query
    - GetMemoryRecord to read a single record by id
    - Reading the score, namespaces, and metadata returned with each hit

Two surfaces:
    python retrieve-records-and-citations.py boto3
    python retrieve-records-and-citations.py sdk

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
NAMESPACE_TEMPLATE = "/users/{actorId}/facts/"

TURNS = [
    ("USER", "I'm Alex; I'm based in Berlin and I prefer Python."),
    ("ASSISTANT", "Got it."),
    ("USER", "I'm allergic to peanuts and avoid dairy when I can."),
    ("ASSISTANT", "Noted."),
    ("USER", "I take the U-Bahn daily; I don't own a car."),
    ("ASSISTANT", "Understood."),
]


# === boto3 ============================================================
def run_with_boto3(cleanup: bool = False) -> None:
    import boto3

    control = boto3.client("bedrock-agentcore-control", region_name=REGION)
    data = boto3.client("bedrock-agentcore", region_name=REGION)

    memory_id = control.create_memory(
        name=f"Retrieval_{int(time.time())}",
        description="Retrieval tutorial (boto3)",
        eventExpiryDuration=30,
        memoryStrategies=[
            {
                "semanticMemoryStrategy": {
                    "name": "Facts",
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
    semantic = data.retrieve_memory_records(
        memoryId=memory_id,
        namespace=namespace,
        searchCriteria={"searchQuery": "dietary restrictions", "topK": 5},
    )["memoryRecordSummaries"]
    print(f"\n[boto3] Semantic search 'dietary restrictions' ({len(semantic)}):")
    for h in semantic:
        print(f"  - score={h.get('score'):.3f} | {h['content']['text']}")

    listed = data.list_memory_records(memoryId=memory_id, namespace=namespace)["memoryRecordSummaries"]
    print(f"\n[boto3] ListMemoryRecords ({len(listed)}):")
    for h in listed:
        print(f"  - {h['memoryRecordId']}: {h['content']['text']}")

    if listed:
        full = data.get_memory_record(memoryId=memory_id, memoryRecordId=listed[0]["memoryRecordId"])["memoryRecord"]
        print("\n[boto3] GetMemoryRecord (one):")
        print(f"  id={full['memoryRecordId']}")
        print(f"  text={full['content']['text']}")
        print(f"  createdAt={full.get('createdAt')}")

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
        name=f"RetrievalSdk_{int(time.time())}",
        description="Retrieval tutorial (SDK)",
        strategies=[
            {
                "semanticMemoryStrategy": {
                    "name": "Facts",
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
    semantic = client.retrieve_memories(
        memory_id=memory_id,
        namespace=namespace,
        query="dietary restrictions",
        top_k=5,
    )
    print(f"\n[sdk] Semantic search ({len(semantic)}):")
    for h in semantic:
        print(f"  - score={h.get('score'):.3f} | {h['content']['text']}")

    # ListMemoryRecords / GetMemoryRecord are forwarded via __getattr__,
    # so call them directly on the MemoryClient with boto3-shaped kwargs.
    listed = client.list_memory_records(memoryId=memory_id, namespace=namespace)["memoryRecordSummaries"]
    print(f"\n[sdk] ListMemoryRecords ({len(listed)}):")
    for h in listed:
        print(f"  - {h['memoryRecordId']}: {h['content']['text']}")

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

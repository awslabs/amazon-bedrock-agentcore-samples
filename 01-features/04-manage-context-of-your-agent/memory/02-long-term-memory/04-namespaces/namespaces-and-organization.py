"""Namespaces — organising long-term memory records.

What you learn:
    - Namespace templates with {actorId}, {sessionId}, {memoryStrategyId}
    - Trailing slash semantics (prevents prefix collisions)
    - Querying by exact namespace (`namespace=`) vs by hierarchy (`namespacePath=`)

Best practice: design namespaces hierarchically from day one — they are
the unit of both retrieval and IAM scoping.

Two surfaces:
    python namespaces-and-organization.py boto3
    python namespaces-and-organization.py sdk

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
EXTRACTION_WAIT_SECONDS = 60
FACTS_TEMPLATE = "/users/{actorId}/facts/"
SUMMARY_TEMPLATE = "/users/{actorId}/sessions/{sessionId}/summary/"

ACTORS = [
    ("alice", "Hi, I'm Alice and I love jazz."),
    ("bob", "Hi, I'm Bob and I love bouldering."),
]


def _strategies() -> list[dict]:
    return [
        {"semanticMemoryStrategy": {"name": "Facts", "namespaces": [FACTS_TEMPLATE]}},
        {
            "summaryMemoryStrategy": {
                "name": "Summaries",
                "namespaces": [SUMMARY_TEMPLATE],
            }
        },
    ]


# === boto3 ============================================================
def run_with_boto3(cleanup: bool = False) -> None:
    import boto3

    control = boto3.client("bedrock-agentcore-control", region_name=REGION)
    data = boto3.client("bedrock-agentcore", region_name=REGION)

    memory_id = control.create_memory(
        name=f"Namespaces_{int(time.time())}",
        description="Namespaces tutorial (boto3)",
        eventExpiryDuration=30,
        memoryStrategies=_strategies(),
    )["memory"]["id"]
    print(f"[boto3] Created memory {memory_id}")
    deadline = time.time() + 300
    while time.time() < deadline:
        if control.get_memory(memoryId=memory_id)["memory"]["status"] == "ACTIVE":
            break
        time.sleep(5)

    for actor_id, intro in ACTORS:
        sess = f"{actor_id}-{int(time.time())}"
        for role, text in [
            ("USER", intro),
            ("ASSISTANT", "Nice to meet you."),
            ("USER", "Tell me about my history with you."),
            ("ASSISTANT", "Sure."),
        ]:
            data.create_event(
                memoryId=memory_id,
                actorId=actor_id,
                sessionId=sess,
                eventTimestamp=datetime.now(timezone.utc),
                payload=[{"conversational": {"role": role, "content": {"text": text}}}],
            )
    print(f"[boto3] Waiting {EXTRACTION_WAIT_SECONDS}s for extraction...")
    time.sleep(EXTRACTION_WAIT_SECONDS)

    alice_facts = data.retrieve_memory_records(
        memoryId=memory_id,
        namespace="/users/alice/facts/",
        searchCriteria={"searchQuery": "alice's interests", "topK": 5},
    )["memoryRecordSummaries"]
    print(f"\n[boto3] Alice facts ({len(alice_facts)}):")
    for h in alice_facts:
        print(f"  - {h['content']['text']}")

    everything = data.retrieve_memory_records(
        memoryId=memory_id,
        namespacePath="/users/",
        searchCriteria={"searchQuery": "anything we know about users", "topK": 20},
    )["memoryRecordSummaries"]
    print(f"\n[boto3] All under /users/* ({len(everything)}):")
    for h in everything:
        print(f"  - [{','.join(h.get('namespaces', []))}] {h['content']['text']}")

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
        name=f"NamespacesSdk_{int(time.time())}",
        description="Namespaces tutorial (SDK)",
        strategies=_strategies(),
        event_expiry_days=30,
    )
    memory_id = memory["id"]
    print(f"[sdk] Created memory {memory_id}")

    for actor_id, intro in ACTORS:
        sess = f"{actor_id}-sdk-{int(time.time())}"
        client.create_event(
            memory_id=memory_id,
            actor_id=actor_id,
            session_id=sess,
            messages=[
                (intro, "USER"),
                ("Nice to meet you.", "ASSISTANT"),
                ("Tell me about my history with you.", "USER"),
                ("Sure.", "ASSISTANT"),
            ],
        )
    print(f"[sdk] Waiting {EXTRACTION_WAIT_SECONDS}s for extraction...")
    time.sleep(EXTRACTION_WAIT_SECONDS)

    alice_facts = client.retrieve_memories(
        memory_id=memory_id,
        namespace="/users/alice/facts/",
        query="alice's interests",
        top_k=5,
    )
    print(f"\n[sdk] Alice facts ({len(alice_facts)}):")
    for h in alice_facts:
        print(f"  - {h['content']['text']}")

    # retrieve_memories accepts either `namespace` (exact) or
    # `namespace_path` (hierarchical prefix).
    everything = client.retrieve_memories(
        memory_id=memory_id,
        namespace_path="/users/",
        query="anything we know about users",
        top_k=20,
    )
    print(f"\n[sdk] All under /users/* ({len(everything)}):")
    for h in everything:
        print(f"  - [{','.join(h.get('namespaces', []))}] {h['content']['text']}")

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

"""Namespaces — organising long-term memory records.

What you learn:
    - Namespace templates with {actorId}, {sessionId}, {memoryStrategyId}
    - Trailing slash semantics (prevents prefix collisions)
    - Querying by exact namespace (`namespace=`) vs by hierarchy (`namespacePath=`)

Best practice: design namespaces hierarchically from day one — they are
the unit of both retrieval and IAM scoping.

Three surfaces:
    python namespaces-and-organization.py boto3      # raw boto3 (bedrock-agentcore / -control)
    python namespaces-and-organization.py sdk        # AgentCore SDK, low-level MemoryClient
    python namespaces-and-organization.py session    # AgentCore SDK, high-level MemorySessionManager

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
SESSION_EXTRACTION_WAIT_SECONDS = 90  # semantic extraction surfaces ~60-90s; extra margin
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


def _session_strategies() -> list[dict]:
    # Same two-strategy shape as _strategies(), but written with the current
    # namespaceTemplates field (namespaces is deprecated).
    return [
        {"semanticMemoryStrategy": {"name": "Facts", "namespaceTemplates": [FACTS_TEMPLATE]}},
        {
            "summaryMemoryStrategy": {
                "name": "Summaries",
                "namespaceTemplates": [SUMMARY_TEMPLATE],
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


# === AgentCore SDK — high-level session API ==========================
def run_with_session(cleanup: bool = False) -> None:
    # MemoryClient owns the control plane (create/delete the resource);
    # MemorySessionManager is data-plane only, so we create the memory with
    # MemoryClient, then drive events + retrieval through MemorySessions.
    from bedrock_agentcore.memory import MemoryClient, MemorySessionManager
    from bedrock_agentcore.memory.constants import ConversationalMessage, MessageRole

    client = MemoryClient(region_name=REGION)
    memory = client.create_memory_and_wait(
        name=f"NamespacesSession_{int(time.time())}",
        description="Namespaces tutorial (SDK session API)",
        strategies=_session_strategies(),
        event_expiry_days=30,
    )
    memory_id = memory["id"]
    print(f"[session] Created memory {memory_id}")

    # One MemorySession per actor: the session is bound to (actorId, sessionId),
    # which is what determines where {actorId}/{sessionId} namespaces resolve to.
    manager = MemorySessionManager(memory_id=memory_id, region_name=REGION)
    for actor_id, intro in ACTORS:
        sess = f"{actor_id}-session-{int(time.time())}"
        session = manager.create_memory_session(actor_id=actor_id, session_id=sess)
        session.add_turns(
            messages=[
                ConversationalMessage(intro, MessageRole.USER),
                ConversationalMessage("Nice to meet you.", MessageRole.ASSISTANT),
                ConversationalMessage("Tell me about my history with you.", MessageRole.USER),
                ConversationalMessage("Sure.", MessageRole.ASSISTANT),
            ]
        )
    print(f"[session] Waiting {SESSION_EXTRACTION_WAIT_SECONDS}s for extraction...")
    time.sleep(SESSION_EXTRACTION_WAIT_SECONDS)

    # Retrieval is scoped by the namespace argument, not the session's bound
    # actor, so a single MemorySession can search across every namespace the
    # memory demonstrates. We search each resolved namespace in turn.
    query_session = manager.create_memory_session(actor_id=ACTORS[0][0])

    # 1) Exact-match on one actor's resolved facts namespace.
    alice_facts = query_session.search_long_term_memories(
        query="alice's interests",
        namespace=FACTS_TEMPLATE.format(actorId="alice"),
        top_k=5,
    )
    print(f"\n[session] Alice facts ({len(alice_facts)}):")
    for h in alice_facts:
        print(f"  - {h['content']['text']}")

    # 2) Hierarchical path prefix spanning every actor's namespaces.
    everything = query_session.search_long_term_memories(
        query="anything we know about users",
        namespace_path="/users/",
        top_k=20,
    )
    print(f"\n[session] All under /users/* ({len(everything)}):")
    for h in everything:
        # Each hit is a MemoryRecord (dict-like): namespaces + content.text.
        print(f"  - [{','.join(h.get('namespaces', []))}] {h['content']['text']}")

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

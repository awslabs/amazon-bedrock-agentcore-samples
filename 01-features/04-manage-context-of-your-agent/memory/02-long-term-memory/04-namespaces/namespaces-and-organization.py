"""Namespaces — organising long-term memory records.

What you learn:
    - Namespace templates with {actorId} (also available: {sessionId}, {memoryStrategyId})
    - Querying by exact namespace (`namespace=`) vs by hierarchy (`namespacePath=`)
    - Multi-tenancy: put the tenant inside actorId ("tenantA/user1") and
      `namespacePath` can then target a single tenant.

The template leads with the data type — "/facts/{actorId}/" — so both actorId
shapes land in one queryable tree:
    actorId "user1"         -> /facts/user1/
    actorId "tenantA/user1" -> /facts/tenantA/user1/

Two ways to run it:
    python namespaces-and-organization.py boto3    # the raw AWS API. Shows exactly what's on the wire.
    python namespaces-and-organization.py sdk      # the AgentCore SDK (MemorySessionManager). The recommended way.

The `sdk` path needs bedrock-agentcore 1.14 or newer (`search_long_term_memories(namespace=...)`).
Add `--cleanup` to delete the memory resource at the end. The same flow via
the AWS CLI is in the README.

Prerequisites:
    pip install boto3 "bedrock-agentcore>=1.14"
    export AWS_REGION=us-east-1   # any AgentCore-supported region
"""

import os
import sys
import time
import uuid
from datetime import datetime, timezone

REGION = os.getenv("AWS_REGION", "us-east-1")
EXTRACTION_WAIT_SECONDS = 60
SDK_EXTRACTION_WAIT_SECONDS = 90  # semantic extraction surfaces ~60-90s; extra margin
FACTS_TEMPLATE = "/facts/{actorId}/"

# Two plain actors and two actors under one tenant — same memory, same template.
ACTORS = [
    ("user1", "Hi, I'm Priya and I love jazz."),
    ("user2", "Hi, I'm Ben and I love bouldering."),
    ("tenantA/user1", "Hi, I'm Carol from AcmeCorp and I love chess."),
    ("tenantA/user2", "Hi, I'm Dan from AcmeCorp and I love sailing."),
]

# The three query scopes both paths demonstrate:
#   namespace="/facts/user1/"          -> one user (exact)
#   namespacePath="/facts/tenantA/"    -> every user under tenantA, nobody else
#   namespacePath="/facts/"            -> everything: plain users and all tenants
QUERIES = [
    ("Exact — /facts/user1/", "user1's interests", {"namespace": "/facts/user1/"}),
    (
        "Tenant — /facts/tenantA/*",
        "tenantA users",
        {"namespacePath": "/facts/tenantA/"},
    ),
    ("All — /facts/*", "anything we know", {"namespacePath": "/facts/"}),
]


def _print_hits(prefix: str, label: str, hits: list) -> None:
    print(f"\n[{prefix}] {label} ({len(hits)}):")
    for h in hits:
        print(f"  - [{','.join(h.get('namespaces', []))}] {h['content']['text']}")


# === boto3 ============================================================
def run_with_boto3(cleanup: bool = False) -> None:
    import boto3

    control = boto3.client("bedrock-agentcore-control", region_name=REGION)
    data = boto3.client("bedrock-agentcore", region_name=REGION)

    memory_id = control.create_memory(
        name=f"Namespaces_{int(time.time())}",
        description="Namespaces tutorial (boto3)",
        eventExpiryDuration=30,
        memoryStrategies=[
            {
                "semanticMemoryStrategy": {
                    "name": "Facts",
                    "namespaceTemplates": [FACTS_TEMPLATE],
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

    for actor_id, intro in ACTORS:
        data.create_event(
            memoryId=memory_id,
            actorId=actor_id,
            sessionId=f"{actor_id.replace('/', '-')}-{int(time.time())}",
            eventTimestamp=datetime.now(timezone.utc),
            payload=[
                {"conversational": {"role": "USER", "content": {"text": intro}}},
                {
                    "conversational": {
                        "role": "ASSISTANT",
                        "content": {"text": "Nice to meet you."},
                    }
                },
            ],
        )
    print(f"[boto3] Waiting {EXTRACTION_WAIT_SECONDS}s for extraction...")
    time.sleep(EXTRACTION_WAIT_SECONDS)

    for label, query, scope in QUERIES:
        hits = data.retrieve_memory_records(
            memoryId=memory_id,
            searchCriteria={"searchQuery": query, "topK": 20},
            **scope,
        )["memoryRecordSummaries"]
        _print_hits("boto3", label, hits)

    if cleanup:
        control.delete_memory(memoryId=memory_id, clientToken=str(uuid.uuid4()))
        print(f"\n[boto3] Deleted memory {memory_id}")
    else:
        print(f"\n[boto3] Keeping memory {memory_id} (pass --cleanup to delete)")


# === AgentCore SDK — high-level MemorySessionManager =================
def run_with_sdk(cleanup: bool = False) -> None:
    # MemoryClient owns the control plane (create/delete the resource);
    # MemorySessionManager is data-plane only.
    from bedrock_agentcore.memory import MemoryClient, MemorySessionManager
    from bedrock_agentcore.memory.constants import ConversationalMessage, MessageRole

    client = MemoryClient(region_name=REGION)
    memory = client.create_memory_and_wait(
        name=f"NamespacesSdk_{int(time.time())}",
        description="Namespaces tutorial (SDK)",
        strategies=[
            {
                "semanticMemoryStrategy": {
                    "name": "Facts",
                    "namespaceTemplates": [FACTS_TEMPLATE],
                }
            }
        ],
        event_expiry_days=30,
    )
    memory_id = memory["id"]
    print(f"[sdk] Created memory {memory_id}")

    # One MemorySession per actor — including the tenant-qualified actorIds.
    manager = MemorySessionManager(memory_id=memory_id, region_name=REGION)
    for actor_id, intro in ACTORS:
        session = manager.create_memory_session(
            actor_id=actor_id,
            session_id=f"{actor_id.replace('/', '-')}-{int(time.time())}",
        )
        session.add_turns(
            messages=[
                ConversationalMessage(intro, MessageRole.USER),
                ConversationalMessage("Nice to meet you.", MessageRole.ASSISTANT),
            ]
        )
    print(f"[sdk] Waiting {SDK_EXTRACTION_WAIT_SECONDS}s for extraction...")
    time.sleep(SDK_EXTRACTION_WAIT_SECONDS)

    # Retrieval is scoped by the namespace argument, not the session's bound
    # actor, so one session can run all three scopes.
    query_session = manager.create_memory_session(actor_id=ACTORS[0][0])
    for label, query, scope in QUERIES:
        kwargs = (
            {"namespace": scope["namespace"]} if "namespace" in scope else {"namespace_path": scope["namespacePath"]}
        )
        hits = query_session.search_long_term_memories(query=query, top_k=20, **kwargs)
        _print_hits("sdk", label, hits)

    if cleanup:
        client.delete_memory_and_wait(memory_id=memory_id)
        print(f"\n[sdk] Deleted memory {memory_id}")
    else:
        print(f"\n[sdk] Keeping memory {memory_id} (pass --cleanup to delete)")


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--cleanup"]
    cleanup = "--cleanup" in sys.argv[1:]
    mode = args[0] if args else "boto3"
    if mode == "boto3":
        run_with_boto3(cleanup=cleanup)
    elif mode == "sdk":
        run_with_sdk(cleanup=cleanup)
    else:
        print(f"Unknown mode {mode!r}. Use boto3 | sdk.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

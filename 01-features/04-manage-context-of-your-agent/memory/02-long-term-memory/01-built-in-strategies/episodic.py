"""Episodic memory strategy — meaningful interaction sequences.

What you learn:
    - Configure `episodicMemoryStrategy` on CreateMemory
    - Drive a multi-turn interaction that has a beginning/middle/end
    - Retrieve episodes via RetrieveMemoryRecords

Episodic strategy captures "episodes" — meaningful sequences of turns
that hang together as one event in the user's life ("debugged a memory
leak in service X on Tuesday"). It also adds a *reflection* step that
generates cross-episode insights.

Two ways to run it:
    python episodic.py boto3    # the raw AWS API, no SDK. Shows exactly what's on the wire.
    python episodic.py sdk      # the AgentCore SDK (MemorySessionManager). The recommended way.

The `sdk` path needs bedrock-agentcore 1.14 or newer, because it searches with
`search_long_term_memories(namespace=...)`. Older versions only accept the deprecated
`namespace_prefix=`.

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
# Reflection namespace for the episodic strategy. The service requires that the
# reflection namespace be the SAME AS or a PREFIX OF the episode namespace
# (the SDK notes it "can be less nested"); without reflectionConfiguration,
# CreateMemory rejects an episodic strategy with a ValidationException. We reuse
# the episode namespace here, which is always a valid (same-as) choice.
REFLECTION_NAMESPACE_TEMPLATE = "/episodes/{actorId}/"
# Episodic extraction + reflection is the SLOWEST built-in strategy: it needs an
# episode boundary to consolidate, so the high-level sdk run waits 16
# minutes. The faster 90s above is fine for the boto3 path, which only
# demonstrates the write path; the sdk run actually retrieves episodes.
SESSION_EXTRACTION_WAIT_SECONDS = 960

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


# === AgentCore SDK — high-level MemorySessionManager =================
def run_with_sdk(cleanup: bool = False) -> None:
    # MemoryClient owns the control plane (create/delete the resource);
    # MemorySessionManager is data-plane only, so we create the memory with
    # MemoryClient, then drive events + retrieval through MemorySession objects.
    from bedrock_agentcore.memory import MemoryClient, MemorySessionManager
    from bedrock_agentcore.memory.constants import ConversationalMessage, MessageRole

    client = MemoryClient(region_name=REGION)
    # Episodic REQUIRES reflectionConfiguration. The reflection namespace must be
    # the same as (or a prefix of) the episode namespaceTemplates; otherwise
    # CreateMemory throws a ValidationException. namespaces is deprecated — both
    # the strategy and its reflection block use namespaceTemplates.
    memory = client.create_memory_and_wait(
        name=f"EpisodicSession_{int(time.time())}",
        description="Episodic strategy (SDK session API)",
        strategies=[
            {
                "episodicMemoryStrategy": {
                    "name": "Episodes",
                    "description": "Meaningful interaction sequences",
                    "namespaceTemplates": [NAMESPACE_TEMPLATE],
                    "reflectionConfiguration": {
                        "namespaceTemplates": [REFLECTION_NAMESPACE_TEMPLATE],
                    },
                }
            }
        ],
        event_expiry_days=30,
    )
    memory_id = memory["id"]
    print(f"[sdk] Created memory {memory_id}")

    # Each scenario is its own session. add_turns takes ConversationalMessage
    # objects and maps to a single create_event. Episodes only consolidate once
    # the interaction has a clear conclusion, so each scenario's final turn
    # closes the episode (e.g. "now fixed in v2.4.1", "we'll go push-first").
    manager = MemorySessionManager(memory_id=memory_id, region_name=REGION)
    for session_id, turns in [
        (f"debug-session-{int(time.time())}", DEBUG_TURNS),
        (f"design-session-{int(time.time())}", DESIGN_TURNS),
    ]:
        session = manager.create_memory_session(actor_id=ACTOR_ID, session_id=session_id)
        session.add_turns(messages=[ConversationalMessage(text, MessageRole[role]) for role, text in turns])

    namespace = NAMESPACE_TEMPLATE.format(actorId=ACTOR_ID)
    # Reuse one session handle for retrieval (search is actor/namespace-scoped,
    # not bound to a single conversation). Use namespace= (exact match);
    # namespace_prefix= is deprecated.
    reader = manager.create_memory_session(actor_id=ACTOR_ID)

    # Episodic extraction + reflection is slow (often 15-20 min) and its exact
    # timing varies, so poll instead of sleeping a fixed amount: ask for the first
    # records and return as soon as they appear, up to a cap. A blind sleep either
    # wastes time or, if it ends too early, prints nothing even though the records
    # surface moments later.
    print(f"[sdk] Waiting up to {SESSION_EXTRACTION_WAIT_SECONDS}s for extraction + reflection...")
    deadline = time.time() + SESSION_EXTRACTION_WAIT_SECONDS
    while time.time() < deadline:
        if reader.search_long_term_memories(query=QUERIES[0], namespace=namespace, top_k=1):
            print("[sdk] Records available.")
            break
        time.sleep(30)
    else:
        print(f"[sdk] No records after {SESSION_EXTRACTION_WAIT_SECONDS}s (episodic can lag; try again later).")

    for query in QUERIES:
        hits = reader.search_long_term_memories(query=query, namespace=namespace, top_k=3)
        print(f"\n[sdk] Q: {query}")
        for h in hits:
            # Each hit is a MemoryRecord (dict-like): content.text + score.
            print(f"  - {h['content']['text']}")

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

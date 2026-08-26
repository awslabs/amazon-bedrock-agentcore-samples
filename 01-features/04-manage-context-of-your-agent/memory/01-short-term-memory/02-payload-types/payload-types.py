"""Event payload types — conversational, JSON, and blob.

An event's `payload` is a *list* of payload items, and not every item has to be a
conversation turn. This script writes all three types and shows which ones reach
long-term memory:

What you learn:
    - `conversational` — a turn with a role and text
    - `json` — non-conversational structured content (behavioural events, telemetry,
      app state), up to 100 KB per payload item
    - `blob` — arbitrary data, stored in short-term memory only
    - Mixed payloads: several items of different types in a single event
    - Conversational and JSON items are extracted into long-term memory; blob is not

The scenario is a car dealership. Most of what a shopper reveals is never said out
loud — cars viewed, filters applied, a financing approval. Those are `json` events,
and extraction reads them the same way it reads speech.

Two ways to run it:
    python payload-types.py boto3    # the raw AWS API, no SDK. Shows exactly what's on the wire.
    python payload-types.py sdk      # the AgentCore SDK (MemorySessionManager).

The `sdk` path is partial by necessity: `add_turns` accepts `ConversationalMessage`
and `BlobMessage`, but the SDK has no JSON message type (checked through
bedrock-agentcore 1.22), so JSON events go through boto3 `create_event` even there.
That path also shows `get_last_k_turns` skipping every non-conversational item.

This tutorial attaches extraction strategies even though it lives under short-term
memory — the difference between the three payload types *is* what extraction does
with them, and that can't be shown without a strategy.

Add `--cleanup` to delete the memory resource at the end. By default the
memory is kept so you can inspect it; the script prints the memoryId.

Prerequisites:
    pip install boto3 bedrock-agentcore
    export AWS_REGION=us-east-1   # use any AgentCore-supported region
"""

import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone

REGION = os.getenv("AWS_REGION", "us-east-1")
ACTOR_ID = "customer-456"
SESSION_ID = f"shopping-{int(time.time())}"
FACTS_NAMESPACE = "/customers/{actorId}/facts/"
PREFS_NAMESPACE = "/customers/{actorId}/preferences/"
EXTRACTION_WAIT_SECONDS = 150  # JSON extraction runs the same pipeline as speech; allow margin

# Four JSON-only events. Field names are part of the input to extraction — call it
# `view_duration_sec`, not `d2`, or the model has nothing to reason about.
JSON_EVENTS = [
    {
        "event": "car_viewed",
        "car_id": "VH-1044",
        "make": "Honda",
        "model": "Civic",
        "year": 2022,
        "transmission": "automatic",
        "view_duration_sec": 112,
        "price": 21000,
    },
    {
        "event": "search_filter_applied",
        "filters": {
            "body_style": "sedan",
            "min_year": 2021,
            "max_price": 23000,
            "transmission": "automatic",
            "make_preference": ["Honda", "Toyota", "Mazda"],
        },
    },
    {
        "event": "financing_pre_approved",
        "term_months": 48,
        "apr": 5.9,
        "max_amount": 25000,
    },
    {
        "event": "test_drive_scheduled",
        "car_id": "VH-2093",
        "location": "CDMX-Polanco",
        "date": "2026-09-12",
    },
]

USER_TEXT = "Automatic sedan please. I really liked the Corolla."
ASSISTANT_TEXT = "Good choice. You're pre-approved at 5.9% APR — want me to hold it?"

# One event, three payload items: what the shopper said, what they did, what the
# agent replied. Extraction sees the speech and the behaviour together and can
# corroborate one with the other.
MIXED_PAYLOAD = [
    {"conversational": {"role": "USER", "content": {"text": USER_TEXT}}},
    {
        "json": {
            "content": {
                "event": "car_viewed",
                "car_id": "VH-3310",
                "make": "Toyota",
                "model": "Corolla",
                "year": 2023,
                "view_duration_sec": 185,
            }
        }
    },
    {"conversational": {"role": "ASSISTANT", "content": {"text": ASSISTANT_TEXT}}},
]

# Blob content. Short-term memory only: it round-trips through ListEvents/GetEvent
# but no strategy ever reads it, so nothing derived from it appears in retrieval.
BLOB_DATA = {
    "document": "trade-in-appraisal.pdf",
    "encoding": "base64",
    "bytes": "JVBERi0xLjQKJcfsj6IKNSAwIG9iago8PAo=",
}


def describe_payload(payload) -> str:
    """Summarise an event payload as its item types, e.g. 'conversational + json'."""
    if not isinstance(payload, list):
        return type(payload).__name__
    # Each item is a single-key dict: {"conversational": ...} / {"json": ...} / {"blob": ...}
    return " + ".join(next(iter(item), "?") if isinstance(item, dict) else "?" for item in payload)


def create_dealership_memory(control) -> str:
    """Create a memory with semantic + user-preference strategies, wait for ACTIVE."""
    memory_id = control.create_memory(
        name=f"PayloadTypes_{int(time.time())}",
        description="Event payload types tutorial",
        eventExpiryDuration=30,
        memoryStrategies=[
            {
                "semanticMemoryStrategy": {
                    "name": "ShopperFacts",
                    "description": "Standalone facts about the shopper",
                    "namespaces": [FACTS_NAMESPACE],
                }
            },
            {
                "userPreferenceMemoryStrategy": {
                    "name": "ShopperPreferences",
                    "description": "Stable vehicle preferences",
                    "namespaces": [PREFS_NAMESPACE],
                }
            },
        ],
    )["memory"]["id"]
    deadline = time.time() + 300
    while time.time() < deadline:
        if control.get_memory(memoryId=memory_id)["memory"]["status"] == "ACTIVE":
            break
        time.sleep(5)
    return memory_id


JSON_PAYLOAD_LIMIT_BYTES = 100 * 1024  # 100 KB per json payload item


def write_json_events(data, memory_id: str) -> None:
    """Write the four JSON-only events. Structured content goes under json.content."""
    for content in JSON_EVENTS:
        # A json payload item is capped at 100 KB. Check locally rather than
        # discovering it as a ValidationException on a large document.
        size = len(json.dumps(content).encode("utf-8"))
        if size > JSON_PAYLOAD_LIMIT_BYTES:
            raise ValueError(f"json payload is {size} bytes, over the {JSON_PAYLOAD_LIMIT_BYTES}-byte limit")
        data.create_event(
            memoryId=memory_id,
            actorId=ACTOR_ID,
            sessionId=SESSION_ID,
            eventTimestamp=datetime.now(timezone.utc),
            payload=[{"json": {"content": content}}],
        )
    print(f"  wrote {len(JSON_EVENTS)} json-only events")


def show_retrieved_records(data, memory_id: str, prefix: str) -> None:
    """Poll both namespaces until records appear, then print them."""
    facts_ns = FACTS_NAMESPACE.format(actorId=ACTOR_ID)
    prefs_ns = PREFS_NAMESPACE.format(actorId=ACTOR_ID)
    print(f"{prefix} Polling up to {EXTRACTION_WAIT_SECONDS}s for extraction...")

    def retrieve(namespace: str, query: str):
        return data.retrieve_memory_records(
            memoryId=memory_id,
            namespace=namespace,
            searchCriteria={"searchQuery": query, "topK": 10},
        )["memoryRecordSummaries"]

    deadline = time.time() + EXTRACTION_WAIT_SECONDS
    while True:
        facts = retrieve(facts_ns, "what car is the customer interested in, and what financing do they have?")
        prefs = retrieve(prefs_ns, "what body style, transmission, and brands does the customer prefer?")
        if (facts and prefs) or time.time() >= deadline:
            break
        time.sleep(10)
    if not facts and not prefs:
        print(f"{prefix} No records after {EXTRACTION_WAIT_SECONDS}s — extraction may still be running.")

    print(f"\n{prefix} Facts in {facts_ns}:")
    for record in facts:
        print(f"  - {record['content']['text']}")
    print(f"\n{prefix} Preferences in {prefs_ns}:")
    for record in prefs:
        print(f"  - {record['content']['text']}")
    print(
        f"\n{prefix} Everything above came from json payloads and the mixed event.\n"
        f"{prefix} Nothing came from the blob event — blob is never extracted."
    )


# === boto3 ============================================================
def run_with_boto3(cleanup: bool = False) -> None:
    import boto3

    control = boto3.client("bedrock-agentcore-control", region_name=REGION)
    data = boto3.client("bedrock-agentcore", region_name=REGION)

    memory_id = create_dealership_memory(control)
    print(f"[boto3] Created memory {memory_id}")

    write_json_events(data, memory_id)

    # One event carrying conversational and json items together.
    data.create_event(
        memoryId=memory_id,
        actorId=ACTOR_ID,
        sessionId=SESSION_ID,
        eventTimestamp=datetime.now(timezone.utc),
        payload=MIXED_PAYLOAD,
    )
    print("  wrote 1 mixed conversational + json event")

    # Blob: accepted by CreateEvent, stored, but skipped by every strategy.
    data.create_event(
        memoryId=memory_id,
        actorId=ACTOR_ID,
        sessionId=SESSION_ID,
        eventTimestamp=datetime.now(timezone.utc),
        payload=[{"blob": BLOB_DATA}],
    )
    print("  wrote 1 blob event")

    # All three types round-trip through short-term memory unchanged.
    events = data.list_events(
        memoryId=memory_id,
        actorId=ACTOR_ID,
        sessionId=SESSION_ID,
        includePayloads=True,
    )["events"]
    print(f"\n[boto3] Session {SESSION_ID} has {len(events)} events:")
    for event in events:
        print(f"  {event['eventId']}  payload: {describe_payload(event.get('payload'))}")

    show_retrieved_records(data, memory_id, "[boto3]")

    if cleanup:
        control.delete_memory(memoryId=memory_id, clientToken=str(uuid.uuid4()))
        print(f"\n[boto3] Deleted memory {memory_id}")
    else:
        print(f"\n[boto3] Keeping memory {memory_id} (pass --cleanup to delete)")


# === AgentCore SDK — high-level MemorySessionManager =================
def run_with_sdk(cleanup: bool = False) -> None:
    # MemoryClient owns the control plane; MemorySessionManager is data-plane only.
    import boto3
    from bedrock_agentcore.memory import MemoryClient, MemorySessionManager
    from bedrock_agentcore.memory.constants import BlobMessage, ConversationalMessage, MessageRole

    client = MemoryClient(region_name=REGION)
    memory = client.create_memory_and_wait(
        name=f"PayloadTypesSession_{int(time.time())}",
        description="Event payload types (SDK session API)",
        strategies=[
            {
                "semanticMemoryStrategy": {
                    "name": "ShopperFacts",
                    "description": "Standalone facts about the shopper",
                    # Current field is namespaceTemplates (namespaces is deprecated).
                    "namespaceTemplates": [FACTS_NAMESPACE],
                }
            },
            {
                "userPreferenceMemoryStrategy": {
                    "name": "ShopperPreferences",
                    "description": "Stable vehicle preferences",
                    "namespaceTemplates": [PREFS_NAMESPACE],
                }
            },
        ],
        event_expiry_days=30,
    )
    memory_id = memory["id"]
    print(f"[sdk] Created memory {memory_id}")

    manager = MemorySessionManager(memory_id=memory_id, region_name=REGION)
    session = manager.create_memory_session(actor_id=ACTOR_ID, session_id=SESSION_ID)
    data = boto3.client("bedrock-agentcore", region_name=REGION)

    # SDK gap: add_turns accepts ConversationalMessage and BlobMessage only — there
    # is no JSON message type, so json payloads need create_event directly.
    print("[sdk] add_turns has no JSON type; writing json events with boto3 create_event")
    write_json_events(data, memory_id)

    # Conversational and blob items do have SDK types. add_turns writes the whole
    # list as one event, so mixing them in a single call is a single mixed payload.
    session.add_turns(
        messages=[
            ConversationalMessage("Automatic sedan please. I really liked the Corolla.", MessageRole.USER),
            ConversationalMessage(
                "Good choice. You're pre-approved at 5.9% APR — want me to hold it?",
                MessageRole.ASSISTANT,
            ),
        ]
    )
    print("  wrote 1 conversational event via add_turns")
    session.add_turns(messages=[BlobMessage(BLOB_DATA)])
    print("  wrote 1 blob event via add_turns(BlobMessage(...))")

    events = session.list_events(include_payload=True)
    print(f"\n[sdk] Session {SESSION_ID} has {len(events)} events:")
    for event in events:
        print(f"  {event['eventId']}  payload: {describe_payload(event.get('payload'))}")

    # get_last_k_turns rebuilds logical turns from conversational items only. The
    # json and blob events are in the session but invisible here — if you rehydrate
    # a prompt this way, structured context silently does not reach the model.
    turns = session.get_last_k_turns(k=10)
    conversational_texts = [msg for turn in turns for msg in turn]
    print(
        f"\n[sdk] get_last_k_turns returned {len(turns)} turn(s) / "
        f"{len(conversational_texts)} message(s) — json and blob items are dropped"
    )

    show_retrieved_records(data, memory_id, "[sdk]")

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

"""Standard usage of AgentCore short-term memory.

The canonical short-term flow:
    1. create a memory resource
    2. wait until it is ACTIVE
    3. append a few events to a session
    4. list the events back to reload context
    5. fetch one event in full
    6. tear down

The same flow is shown two ways. Pick the surface that matches how you'll
deploy: boto3 for raw control or AgentCore SDK for ergonomic helpers.

Run a single surface:
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


# === boto3 ============================================================
def run_with_boto3(cleanup: bool = False) -> None:
    import boto3

    control = boto3.client("bedrock-agentcore-control", region_name=REGION)
    data = boto3.client("bedrock-agentcore", region_name=REGION)

    memory_id = control.create_memory(
        name=f"StmStandard_{int(time.time())}",
        description="Short-term memory standard usage (boto3)",
        eventExpiryDuration=30,
    )["memory"]["id"]
    print(f"[boto3] Created memory {memory_id}")

    deadline = time.time() + 300
    while time.time() < deadline:
        if control.get_memory(memoryId=memory_id)["memory"]["status"] == "ACTIVE":
            break
        time.sleep(5)

    for role, text in [
        ("USER", "Hi, I'm Alex. I prefer Python over Java."),
        ("ASSISTANT", "Got it, Alex — I'll lean toward Python in examples."),
        ("USER", "What did I tell you about my language preference?"),
    ]:
        data.create_event(
            memoryId=memory_id,
            actorId=ACTOR_ID,
            sessionId=SESSION_ID,
            eventTimestamp=datetime.now(timezone.utc),
            payload=[{"conversational": {"role": role, "content": {"text": text}}}],
        )

    events = data.list_events(
        memoryId=memory_id,
        actorId=ACTOR_ID,
        sessionId=SESSION_ID,
        includePayloads=True,
    )["events"]
    print(f"[boto3] Session {SESSION_ID} has {len(events)} events")

    first = data.get_event(
        memoryId=memory_id,
        actorId=ACTOR_ID,
        sessionId=SESSION_ID,
        eventId=events[0]["eventId"],
    )["event"]
    print(f"[boto3] First event payload: {first['payload']}")

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
        name=f"StmStandardSdk_{int(time.time())}",
        description="Short-term memory standard usage (SDK)",
        strategies=[],
        event_expiry_days=30,
    )
    memory_id = memory["id"]
    print(f"[sdk] Created memory {memory_id}")

    # SDK takes (text, role) tuples and groups multiple messages into one event.
    client.create_event(
        memory_id=memory_id,
        actor_id=ACTOR_ID,
        session_id=SESSION_ID,
        messages=[
            ("Hi, I'm Alex. I prefer Python over Java.", "USER"),
            ("Got it, Alex — I'll lean toward Python in examples.", "ASSISTANT"),
            ("What did I tell you about my language preference?", "USER"),
        ],
    )

    # get_last_k_turns is the SDK's idiomatic equivalent to ListEvents.
    turns = client.get_last_k_turns(memory_id=memory_id, actor_id=ACTOR_ID, session_id=SESSION_ID, k=5)
    print(f"[sdk] Session {SESSION_ID} has {len(turns)} turns")
    for turn in turns:
        for msg in turn:
            print(f"  {msg['role']}: {msg['content']['text']}")

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

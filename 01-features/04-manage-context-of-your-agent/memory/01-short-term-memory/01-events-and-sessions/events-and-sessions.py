"""Events and sessions — the building blocks of short-term memory.

What you learn:
    - CreateEvent appends an immutable, timestamped event to a session
    - ListEvents pages through the session in chronological order
    - GetEvent fetches one event in full
    - ListSessions discovers prior sessions for an actor

Three surfaces, same flow:
    python events-and-sessions.py boto3
    python events-and-sessions.py sdk
    python events-and-sessions.py cli

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
ACTOR_ID = "user-42"


# === boto3 ============================================================
def run_with_boto3() -> None:
    import boto3

    control = boto3.client("bedrock-agentcore-control", region_name=REGION)
    data = boto3.client("bedrock-agentcore", region_name=REGION)

    memory_id = control.create_memory(
        name=f"EventsAndSessions_{int(time.time())}",
        description="Events and sessions tutorial",
        eventExpiryDuration=30,
    )["memory"]["id"]
    print(f"[boto3] Created memory {memory_id}")
    deadline = time.time() + 300
    while time.time() < deadline:
        if control.get_memory(memoryId=memory_id)["memory"]["status"] == "ACTIVE":
            break
        time.sleep(5)

    session_a = f"session-a-{int(time.time())}"
    session_b = f"session-b-{int(time.time())}"

    for session_id, turns in [
        (
            session_a,
            [
                ("USER", "Book me a flight from Berlin to Lisbon."),
                ("ASSISTANT", "Sure — for which dates?"),
                ("USER", "Next Monday, returning Friday."),
            ],
        ),
        (
            session_b,
            [
                ("USER", "What did I book last week?"),
                ("ASSISTANT", "You booked Berlin to Lisbon, Mon–Fri."),
            ],
        ),
    ]:
        for role, text in turns:
            data.create_event(
                memoryId=memory_id,
                actorId=ACTOR_ID,
                sessionId=session_id,
                payload=[{"conversational": {"role": role, "content": {"text": text}}}],
            )

    events = data.list_events(
        memoryId=memory_id,
        actorId=ACTOR_ID,
        sessionId=session_a,
        includePayloads=True,
    )["events"]
    print(f"[boto3] Session {session_a} has {len(events)} events")

    one = data.get_event(
        memoryId=memory_id,
        actorId=ACTOR_ID,
        sessionId=session_a,
        eventId=events[0]["eventId"],
    )["event"]
    print(f"[boto3] First event id: {one['eventId']}")

    sessions = data.list_sessions(memoryId=memory_id, actorId=ACTOR_ID)[
        "sessionSummaries"
    ]
    print(f"[boto3] Actor {ACTOR_ID} has {len(sessions)} session(s)")

    control.delete_memory(memoryId=memory_id, clientToken=str(uuid.uuid4()))
    print(f"[boto3] Deleted memory {memory_id}")


# === AgentCore SDK ====================================================
# Note: MemoryClient does not expose ListSessions. For session discovery,
# fall back to the underlying boto3 client (`bedrock-agentcore-control` client) or to
# raw boto3 as shown in the boto3 path above.
def run_with_sdk() -> None:
    from bedrock_agentcore.memory import MemoryClient

    client = MemoryClient(region_name=REGION)
    memory = client.create_memory_and_wait(
        name=f"EventsAndSessionsSdk_{int(time.time())}",
        description="Events and sessions (SDK)",
        strategies=[],
        event_expiry_days=30,
    )
    memory_id = memory["id"]
    print(f"[sdk] Created memory {memory_id}")

    session_a = f"session-a-{int(time.time())}"
    session_b = f"session-b-{int(time.time())}"

    client.create_event(
        memory_id=memory_id,
        actor_id=ACTOR_ID,
        session_id=session_a,
        messages=[
            ("Book me a flight from Berlin to Lisbon.", "USER"),
            ("Sure — for which dates?", "ASSISTANT"),
            ("Next Monday, returning Friday.", "USER"),
        ],
    )
    client.create_event(
        memory_id=memory_id,
        actor_id=ACTOR_ID,
        session_id=session_b,
        messages=[
            ("What did I book last week?", "USER"),
            ("You booked Berlin to Lisbon, Mon–Fri.", "ASSISTANT"),
        ],
    )

    events = client.list_events(
        memory_id=memory_id,
        actor_id=ACTOR_ID,
        session_id=session_a,
        include_payload=True,
    )
    print(f"[sdk] Session {session_a} has {len(events)} events")

    turns = client.get_last_k_turns(
        memory_id=memory_id, actor_id=ACTOR_ID, session_id=session_a, k=5
    )
    print(f"[sdk] Last {len(turns)} turn(s) in session_a")

    print(
        "[sdk] (ListSessions has no SDK helper — use boto3 list_sessions for discovery)"
    )
    client.delete_memory_and_wait(memory_id=memory_id)
    print(f"[sdk] Deleted memory {memory_id}")


# === AWS CLI ==========================================================
CLI_WALKTHROUGH = """\
# 1. Create memory + capture id
aws bedrock-agentcore-control create-memory \\
  --region "$AWS_REGION" \\
  --name "EventsAndSessionsCli-$(date +%s)" \\
  --event-expiry-duration 30 \\
  --client-token "$(uuidgen)"
export MEMORY_ID=<id-from-response>

# 2. Append events to two distinct sessions for the same actor
for sid in session-a session-b; do
  aws bedrock-agentcore create-event \\
    --region "$AWS_REGION" --memory-id "$MEMORY_ID" \\
    --actor-id user-42 --session-id "$sid" \\
    --event-timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \\
    --payload '[{"conversational":{"role":"USER","content":{"text":"hello"}}}]'
done

# 3. ListEvents within one session
aws bedrock-agentcore list-events \\
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \\
  --actor-id user-42 --session-id session-a --include-payloads

# 4. GetEvent for one event by id
aws bedrock-agentcore get-event \\
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \\
  --actor-id user-42 --session-id session-a --event-id <event-id>

# 5. ListSessions discovers prior sessions for the actor
aws bedrock-agentcore list-sessions \\
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" --actor-id user-42

# 6. Teardown
aws bedrock-agentcore-control delete-memory \\
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \\
  --client-token "$(uuidgen)"
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

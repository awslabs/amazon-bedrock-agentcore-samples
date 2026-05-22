"""Actor and session isolation.

What you learn:
    - A single memory resource serves many actors
    - Events are scoped by (actorId, sessionId) — no cross-actor leakage
    - ListEvents under one actor never returns another actor's events

Three surfaces:
    python actor-session-isolation.py boto3
    python actor-session-isolation.py sdk
    python actor-session-isolation.py cli

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


# === boto3 ============================================================
def run_with_boto3() -> None:
    import boto3

    control = boto3.client("bedrock-agentcore-control", region_name=REGION)
    data = boto3.client("bedrock-agentcore", region_name=REGION)

    memory_id = control.create_memory(
        name=f"ActorIsolation_{int(time.time())}",
        description="Actor/session isolation tutorial",
        eventExpiryDuration=30,
    )["memory"]["id"]
    print(f"[boto3] Created memory {memory_id}")
    deadline = time.time() + 300
    while time.time() < deadline:
        if control.get_memory(memoryId=memory_id)["memory"]["status"] == "ACTIVE":
            break
        time.sleep(5)

    alice_session = f"alice-{int(time.time())}"
    bob_session = f"bob-{int(time.time())}"

    def write(actor, session, role, text):
        data.create_event(
            memoryId=memory_id, actorId=actor, sessionId=session,
            eventTimestamp=datetime.now(timezone.utc),
            payload=[{"conversational": {"role": role, "content": {"text": text}}}],
        )

    write("alice", alice_session, "USER", "I'm flying to Tokyo next week.")
    write("alice", alice_session, "ASSISTANT", "Got it.")
    write("bob", bob_session, "USER", "Remind me about my dentist appointment.")
    write("bob", bob_session, "ASSISTANT", "Friday at 3pm.")

    alice_events = data.list_events(
        memoryId=memory_id, actorId="alice", sessionId=alice_session, includePayloads=True
    )["events"]
    bob_events = data.list_events(
        memoryId=memory_id, actorId="bob", sessionId=bob_session, includePayloads=True
    )["events"]
    print(f"[boto3] Alice: {len(alice_events)} events | Bob: {len(bob_events)} events")

    alice_sessions = data.list_sessions(memoryId=memory_id, actorId="alice")["sessionSummaries"]
    bob_sessions = data.list_sessions(memoryId=memory_id, actorId="bob")["sessionSummaries"]
    print(f"[boto3] Alice sessions: {[s['sessionId'] for s in alice_sessions]}")
    print(f"[boto3] Bob sessions:   {[s['sessionId'] for s in bob_sessions]}")

    control.delete_memory(memoryId=memory_id, clientToken=str(uuid.uuid4()))
    print(f"[boto3] Deleted memory {memory_id}")


# === AgentCore SDK ====================================================
def run_with_sdk() -> None:
    from bedrock_agentcore.memory import MemoryClient

    client = MemoryClient(region_name=REGION)
    memory = client.create_memory_and_wait(
        name=f"ActorIsolationSdk_{int(time.time())}",
        description="Actor/session isolation (SDK)",
        strategies=[],
        event_expiry_days=30,
    )
    memory_id = memory["id"]
    print(f"[sdk] Created memory {memory_id}")

    alice_session = f"alice-{int(time.time())}"
    bob_session = f"bob-{int(time.time())}"

    client.create_event(
        memory_id=memory_id, actor_id="alice", session_id=alice_session,
        messages=[
            ("I'm flying to Tokyo next week.", "USER"),
            ("Got it.", "ASSISTANT"),
        ],
    )
    client.create_event(
        memory_id=memory_id, actor_id="bob", session_id=bob_session,
        messages=[
            ("Remind me about my dentist appointment.", "USER"),
            ("Friday at 3pm.", "ASSISTANT"),
        ],
    )

    alice_events = client.list_events(
        memory_id=memory_id, actor_id="alice", session_id=alice_session
    )
    bob_events = client.list_events(
        memory_id=memory_id, actor_id="bob", session_id=bob_session
    )
    print(f"[sdk] Alice: {len(alice_events)} events | Bob: {len(bob_events)} events")

    print("[sdk] (ListSessions has no SDK helper — use boto3 list_sessions)")
    client.delete_memory_and_wait(memory_id=memory_id)
    print(f"[sdk] Deleted memory {memory_id}")


# === AWS CLI ==========================================================
CLI_WALKTHROUGH = """\
# Single memory resource serves many actors. Events are scoped by (actorId, sessionId).

aws bedrock-agentcore-control create-memory \\
  --region "$AWS_REGION" --name "ActorIsoCli-$(date +%s)" \\
  --event-expiry-duration 30 --client-token "$(uuidgen)"
export MEMORY_ID=<id>

# Two actors, two sessions
for actor in alice bob; do
  aws bedrock-agentcore create-event \\
    --region "$AWS_REGION" --memory-id "$MEMORY_ID" \\
    --actor-id "$actor" --session-id "${actor}-session" \\
    --event-timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \\
    --payload "[{\\"conversational\\":{\\"role\\":\\"USER\\",\\"content\\":{\\"text\\":\\"hello from $actor\\"}}}]"
done

# Each actor only sees their own events
aws bedrock-agentcore list-events --region "$AWS_REGION" \\
  --memory-id "$MEMORY_ID" --actor-id alice --session-id alice-session
aws bedrock-agentcore list-events --region "$AWS_REGION" \\
  --memory-id "$MEMORY_ID" --actor-id bob --session-id bob-session

# ListSessions is also actor-scoped
aws bedrock-agentcore list-sessions --region "$AWS_REGION" \\
  --memory-id "$MEMORY_ID" --actor-id alice
aws bedrock-agentcore list-sessions --region "$AWS_REGION" \\
  --memory-id "$MEMORY_ID" --actor-id bob

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

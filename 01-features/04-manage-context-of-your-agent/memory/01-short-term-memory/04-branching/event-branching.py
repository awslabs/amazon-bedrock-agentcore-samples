"""Event branching — fork a session for what-if or parallel flows.

What you learn:
    - Set `branch` on CreateEvent to fork from a parent event
    - Filter ListEvents by branch name
    - includeParentBranches=True walks the branch ancestry up to the root

Use cases: exploratory "what if I had said X instead?" turns, parallel
sub-agents that each contribute on a separate branch over a shared parent.

Two surfaces:
    python event-branching.py boto3
    python event-branching.py sdk

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


# === boto3 ============================================================
def run_with_boto3(cleanup: bool = False) -> None:
    import boto3

    control = boto3.client("bedrock-agentcore-control", region_name=REGION)
    data = boto3.client("bedrock-agentcore", region_name=REGION)
    session_id = f"sess-{int(time.time())}"

    memory_id = control.create_memory(
        name=f"Branching_{int(time.time())}",
        description="Event branching tutorial",
        eventExpiryDuration=30,
    )["memory"]["id"]
    print(f"[boto3] Created memory {memory_id}")
    deadline = time.time() + 300
    while time.time() < deadline:
        if control.get_memory(memoryId=memory_id)["memory"]["status"] == "ACTIVE":
            break
        time.sleep(5)

    def append(role, text, branch=None):
        kwargs = dict(
            memoryId=memory_id,
            actorId=ACTOR_ID,
            sessionId=session_id,
            eventTimestamp=datetime.now(timezone.utc),
            payload=[{"conversational": {"role": role, "content": {"text": text}}}],
        )
        if branch is not None:
            kwargs["branch"] = branch
        return data.create_event(**kwargs)["event"]

    append("USER", "I'm planning a trip to Lisbon.")
    fork_point = append("ASSISTANT", "When are you thinking of going?")

    autumn = {"name": "autumn", "rootEventId": fork_point["eventId"]}
    append("USER", "October — the weather is mild then.", branch=autumn)
    append("ASSISTANT", "October is great. Here are flights for the second week.", branch=autumn)

    winter = {"name": "winter", "rootEventId": fork_point["eventId"]}
    append("USER", "Actually, what about December for Christmas markets?", branch=winter)
    append("ASSISTANT", "December is busier and pricier. Here's what's available.", branch=winter)

    autumn_only = data.list_events(
        memoryId=memory_id,
        actorId=ACTOR_ID,
        sessionId=session_id,
        includePayloads=True,
        filter={"branch": {"name": "autumn", "includeParentBranches": False}},
    )["events"]
    print(f"[boto3] Autumn-only events: {len(autumn_only)}")

    winter_full = data.list_events(
        memoryId=memory_id,
        actorId=ACTOR_ID,
        sessionId=session_id,
        includePayloads=True,
        filter={"branch": {"name": "winter", "includeParentBranches": True}},
    )["events"]
    print(f"[boto3] Winter with parents: {len(winter_full)}")

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
        name=f"BranchingSdk_{int(time.time())}",
        description="Event branching (SDK)",
        strategies=[],
        event_expiry_days=30,
    )
    memory_id = memory["id"]
    session_id = f"sess-{int(time.time())}"
    print(f"[sdk] Created memory {memory_id}")

    # Seed a couple of turns on the root branch.
    root_event = client.create_event(
        memory_id=memory_id,
        actor_id=ACTOR_ID,
        session_id=session_id,
        messages=[
            ("I'm planning a trip to Lisbon.", "USER"),
            ("When are you thinking of going?", "ASSISTANT"),
        ],
    )

    # fork_conversation creates a new branch rooted at the given event.
    client.fork_conversation(
        memory_id=memory_id,
        actor_id=ACTOR_ID,
        session_id=session_id,
        root_event_id=root_event["eventId"],
        branch_name="autumn",
        new_messages=[
            ("October — the weather is mild then.", "USER"),
            ("October is great. Here are flights for the second week.", "ASSISTANT"),
        ],
    )
    client.fork_conversation(
        memory_id=memory_id,
        actor_id=ACTOR_ID,
        session_id=session_id,
        root_event_id=root_event["eventId"],
        branch_name="winter",
        new_messages=[
            ("Actually, what about December for Christmas markets?", "USER"),
            ("December is busier and pricier. Here's what's available.", "ASSISTANT"),
        ],
    )

    branches = client.list_branches(memory_id=memory_id, actor_id=ACTOR_ID, session_id=session_id)
    print(f"[sdk] Branches in session: {[b.get('name') for b in branches]}")

    autumn_only = client.list_branch_events(
        memory_id=memory_id,
        actor_id=ACTOR_ID,
        session_id=session_id,
        branch_name="autumn",
        include_parent_events=False,
    )
    winter_full = client.list_branch_events(
        memory_id=memory_id,
        actor_id=ACTOR_ID,
        session_id=session_id,
        branch_name="winter",
        include_parent_events=True,
    )
    print(f"[sdk] Autumn-only events: {len(autumn_only)} | Winter with parents: {len(winter_full)}")

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

"""Skipping long-term memory extraction for specific events.

What you learn:
    - Use extractionMode="SKIP" on CreateEvent to store an event in short-term
      memory without triggering long-term extraction
    - Verify that skipped events do not produce memory records
    - Common use cases: bulk import, system messages, sensitive turns

The flow:
    1. Create a memory with a semantic strategy
    2. Send 8 events normally (extraction will run)
    3. Send 4 events with extractionMode="SKIP" (no extraction)
    4. Wait for extraction to complete
    5. Retrieve records — only the non-skipped events produce results

Prerequisites:
    pip install boto3
    export AWS_REGION=us-east-1   # use any AgentCore-supported region
"""

import os
import time
import uuid
from datetime import datetime, timezone

REGION = os.getenv("AWS_REGION", "us-east-1")
ACTOR_ID = "user-42"
SESSION_ID = f"sess-skip-{int(time.time())}"
EXTRACTION_WAIT_SECONDS = 90
NAMESPACE_TEMPLATE = "/users/{actorId}/facts/"


# === boto3 ============================================================
def run_with_boto3(cleanup: bool = False) -> None:
    import boto3

    control = boto3.client("bedrock-agentcore-control", region_name=REGION)
    data = boto3.client("bedrock-agentcore", region_name=REGION)

    memory_id = control.create_memory(
        name=f"SkipExtraction_{int(time.time())}",
        description="Demonstrates extractionMode=SKIP (boto3)",
        eventExpiryDuration=30,
        memoryStrategies=[
            {
                "semanticMemoryStrategy": {
                    "name": "UserFacts",
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

    # --- Normal events: these WILL be extracted into long-term memory ---
    normal_turns = [
        ("USER", "My name is Alex. I'm a software engineer."),
        ("ASSISTANT", "Nice to meet you, Alex! What languages do you work with?"),
        ("USER", "I mostly write Python. It's my favorite language."),
        ("ASSISTANT", "Python is great! Where are you based?"),
        ("USER", "I live in Berlin, Germany. I moved here two years ago."),
        ("ASSISTANT", "Berlin is a fantastic city for tech. Anything else I should know?"),
        ("USER", "Yes — I'm allergic to peanuts. Please keep that in mind."),
        ("ASSISTANT", "Noted, I'll remember your peanut allergy."),
    ]
    for role, text in normal_turns:
        data.create_event(
            memoryId=memory_id,
            actorId=ACTOR_ID,
            sessionId=SESSION_ID,
            eventTimestamp=datetime.now(timezone.utc),
            payload=[{"conversational": {"role": role, "content": {"text": text}}}],
        )
    print(f"[boto3] Sent {len(normal_turns)} normal events (will be extracted)")

    # --- Skipped events: stored in STM but NOT extracted into LTM ---
    skipped_turns = [
        ("USER", "I just won the lottery and my bank account number is 123456789."),
        ("ASSISTANT", "That's exciting! Congratulations on winning."),
        ("USER", "My social security number is 987-65-4321, can you store that for me?"),
        ("ASSISTANT", "I've noted that information for you."),
    ]
    for role, text in skipped_turns:
        data.create_event(
            memoryId=memory_id,
            actorId=ACTOR_ID,
            sessionId=SESSION_ID,
            eventTimestamp=datetime.now(timezone.utc),
            payload=[{"conversational": {"role": role, "content": {"text": text}}}],
            extractionMode="SKIP",
        )
    print(f"[boto3] Sent {len(skipped_turns)} skipped events (extractionMode=SKIP, no extraction)")

    # --- Verify the skipped events are still in short-term memory ---
    events = data.list_events(
        memoryId=memory_id,
        actorId=ACTOR_ID,
        sessionId=SESSION_ID,
        includePayloads=True,
    )["events"]
    print(f"[boto3] Short-term memory has {len(events)} events (all 12 stored)")

    # --- Wait for extraction, then retrieve long-term records ---
    print(f"[boto3] Waiting {EXTRACTION_WAIT_SECONDS}s for extraction...")
    time.sleep(EXTRACTION_WAIT_SECONDS)

    namespace = NAMESPACE_TEMPLATE.format(actorId=ACTOR_ID)
    hits = data.retrieve_memory_records(
        memoryId=memory_id,
        namespace=namespace,
        searchCriteria={"searchQuery": "What do I know about Alex?", "topK": 10},
    )["memoryRecordSummaries"]
    print(f"[boto3] Retrieved {len(hits)} long-term records (only from non-skipped events)")
    for h in hits:
        print(f"  - {h['content']['text']}")

    if cleanup:
        control.delete_memory(memoryId=memory_id, clientToken=str(uuid.uuid4()))
        print(f"[boto3] Deleted memory {memory_id}")
    else:
        print(f"[boto3] Keeping memory {memory_id} (pass --cleanup to delete)")


if __name__ == "__main__":
    import sys

    cleanup = "--cleanup" in sys.argv[1:]
    run_with_boto3(cleanup=cleanup)

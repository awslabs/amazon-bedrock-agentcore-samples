"""Batch CRUD on memory records — bypassing the extraction pipeline.

What you learn:
    - BatchCreateMemoryRecords to insert records you've extracted yourself
    - BatchUpdateMemoryRecords to overwrite content of existing records
    - BatchDeleteMemoryRecords to remove records by id

These are the data-plane CRUD APIs. Use them when you've extracted
records outside AgentCore (e.g. via a self-managed strategy) or for
back-fills, migrations, and admin tooling.

Each call accepts up to 100 records and reports per-record success/failure.

Two surfaces:
    python batch-create-update-delete.py boto3
    python batch-create-update-delete.py sdk

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

REGION = os.getenv("AWS_REGION", "us-east-1")
ACTOR_ID = "user-alex"
NAMESPACE = f"/users/{ACTOR_ID}/notes/"


# === boto3 ============================================================
def run_with_boto3(cleanup: bool = False) -> None:
    import boto3

    control = boto3.client("bedrock-agentcore-control", region_name=REGION)
    data = boto3.client("bedrock-agentcore", region_name=REGION)

    memory_id = control.create_memory(
        name=f"BatchCRUD_{int(time.time())}",
        description="Batch APIs tutorial (boto3)",
        eventExpiryDuration=30,
    )["memory"]["id"]
    print(f"[boto3] Created memory {memory_id}")
    deadline = time.time() + 300
    while time.time() < deadline:
        if control.get_memory(memoryId=memory_id)["memory"]["status"] == "ACTIVE":
            break
        time.sleep(5)

    create_resp = data.batch_create_memory_records(
        memoryId=memory_id,
        records=[
            {
                "requestIdentifier": "note-lang",
                "namespaces": [NAMESPACE],
                "timestamp": str(int(time.time())),
                "content": {"text": "Alex prefers Python over Java."},
            },
            {
                "requestIdentifier": "note-city",
                "namespaces": [NAMESPACE],
                "timestamp": str(int(time.time())),
                "content": {"text": "Alex is based in Berlin."},
            },
            {
                "requestIdentifier": "note-allergy",
                "namespaces": [NAMESPACE],
                "timestamp": str(int(time.time())),
                "content": {"text": "Alex is allergic to peanuts."},
            },
        ],
    )
    successes = create_resp.get("successfulRecords", [])
    print(f"[boto3] Created {len(successes)} ({len(create_resp.get('failedRecords', []))} failed)")
    record_ids = {r["requestIdentifier"]: r["memoryRecordId"] for r in successes}

    update_resp = data.batch_update_memory_records(
        memoryId=memory_id,
        records=[
            {
                "memoryRecordId": record_ids["note-lang"],
                "content": {"text": "Alex prefers Python and writes Rust for hot paths."},
            }
        ],
    )
    print(f"[boto3] Updated {len(update_resp.get('successfulRecords', []))}")

    delete_resp = data.batch_delete_memory_records(
        memoryId=memory_id,
        records=[{"memoryRecordId": record_ids["note-allergy"]}],
    )
    print(f"[boto3] Deleted {len(delete_resp.get('successfulRecords', []))}")

    remaining = data.list_memory_records(memoryId=memory_id, namespace=NAMESPACE)["memoryRecordSummaries"]
    print(f"\n[boto3] Remaining ({len(remaining)}):")
    for r in remaining:
        print(f"  - {r['content']['text']}")

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
        name=f"BatchCRUDSdk_{int(time.time())}",
        description="Batch APIs tutorial (SDK)",
        strategies=[],
        event_expiry_days=30,
    )
    memory_id = memory["id"]
    print(f"[sdk] Created memory {memory_id}")

    create_resp = client.batch_create_memory_records(
        memoryId=memory_id,
        records=[
            {
                "requestIdentifier": "note-lang",
                "namespaces": [NAMESPACE],
                "timestamp": str(int(time.time())),
                "content": {"text": "Alex prefers Python over Java."},
            },
            {
                "requestIdentifier": "note-city",
                "namespaces": [NAMESPACE],
                "timestamp": str(int(time.time())),
                "content": {"text": "Alex is based in Berlin."},
            },
            {
                "requestIdentifier": "note-allergy",
                "namespaces": [NAMESPACE],
                "timestamp": str(int(time.time())),
                "content": {"text": "Alex is allergic to peanuts."},
            },
        ],
    )
    successes = create_resp.get("successfulRecords", [])
    print(f"[sdk] Created {len(successes)} ({len(create_resp.get('failedRecords', []))} failed)")
    record_ids = {r["requestIdentifier"]: r["memoryRecordId"] for r in successes}

    update_resp = client.batch_update_memory_records(
        memoryId=memory_id,
        records=[
            {
                "memoryRecordId": record_ids["note-lang"],
                "content": {"text": "Alex prefers Python and writes Rust for hot paths."},
            }
        ],
    )
    print(f"[sdk] Updated {len(update_resp.get('successfulRecords', []))}")

    delete_resp = client.batch_delete_memory_records(
        memoryId=memory_id,
        records=[{"memoryRecordId": record_ids["note-allergy"]}],
    )
    print(f"[sdk] Deleted {len(delete_resp.get('successfulRecords', []))}")

    remaining = client.list_memory_records(memoryId=memory_id, namespace=NAMESPACE)["memoryRecordSummaries"]
    print(f"\n[sdk] Remaining ({len(remaining)}):")
    for r in remaining:
        print(f"  - {r['content']['text']}")

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

"""Batch CRUD on memory records — bypassing the extraction pipeline.

What you learn:
    - BatchCreateMemoryRecords to insert records you've extracted yourself
    - BatchUpdateMemoryRecords to overwrite content of existing records
    - BatchDeleteMemoryRecords to remove records by id

These are the data-plane CRUD APIs. Use them when you've extracted
records outside AgentCore (e.g. via a self-managed strategy) or for
back-fills, migrations, and admin tooling.

Each call accepts up to 100 records and reports per-record success/failure.

Three surfaces:
    python batch-create-update-delete.py boto3
    python batch-create-update-delete.py sdk    # documents the SDK gap
    python batch-create-update-delete.py cli

SDK note: MemoryClient does not wrap the batch CRUD APIs. Use the wrapped
boto3 client (`client.gmcp_client`) or boto3 directly.

Prerequisites:
    pip install boto3 bedrock-agentcore
    export AWS_REGION=us-east-1
"""

import os
import sys
import time
import uuid

REGION = os.getenv("AWS_REGION", "us-east-1")
ACTOR_ID = "user-alex"
NAMESPACE = f"/users/{ACTOR_ID}/notes/"


# === boto3 ============================================================
def run_with_boto3() -> None:
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
            {"requestIdentifier": "note-lang", "namespaces": [NAMESPACE],
             "timestamp": str(int(time.time())),
             "content": {"text": "Alex prefers Python over Java."}},
            {"requestIdentifier": "note-city", "namespaces": [NAMESPACE],
             "timestamp": str(int(time.time())),
             "content": {"text": "Alex is based in Berlin."}},
            {"requestIdentifier": "note-allergy", "namespaces": [NAMESPACE],
             "timestamp": str(int(time.time())),
             "content": {"text": "Alex is allergic to peanuts."}},
        ],
    )
    successes = create_resp.get("successfulRecords", [])
    print(f"[boto3] Created {len(successes)} ({len(create_resp.get('failedRecords', []))} failed)")
    record_ids = {r["requestIdentifier"]: r["memoryRecordId"] for r in successes}

    update_resp = data.batch_update_memory_records(
        memoryId=memory_id,
        records=[{
            "memoryRecordId": record_ids["note-lang"],
            "content": {"text": "Alex prefers Python and writes Rust for hot paths."},
        }],
    )
    print(f"[boto3] Updated {len(update_resp.get('successfulRecords', []))}")

    delete_resp = data.batch_delete_memory_records(
        memoryId=memory_id,
        records=[{"memoryRecordId": record_ids["note-allergy"]}],
    )
    print(f"[boto3] Deleted {len(delete_resp.get('successfulRecords', []))}")

    remaining = data.list_memory_records(memoryId=memory_id, namespace=NAMESPACE)[
        "memoryRecordSummaries"
    ]
    print(f"\n[boto3] Remaining ({len(remaining)}):")
    for r in remaining:
        print(f"  - {r['content']['text']}")

    control.delete_memory(memoryId=memory_id, clientToken=str(uuid.uuid4()))
    print(f"\n[boto3] Deleted memory {memory_id}")


# === AgentCore SDK ====================================================
# MemoryClient does not wrap batch_create_memory_records,
# batch_update_memory_records, or batch_delete_memory_records.
def run_with_sdk() -> None:
    print(
        "[sdk] Batch CRUD is not exposed by MemoryClient.\n"
        "      For BatchCreate / BatchUpdate / BatchDelete record APIs, use the\n"
        "      boto3 path (see run_with_boto3) or call the wrapped client:\n"
        "        client.gmcp_client.batch_create_memory_records(...)\n"
        "        client.gmcp_client.batch_update_memory_records(...)\n"
        "        client.gmcp_client.batch_delete_memory_records(...)"
    )


# === AWS CLI ==========================================================
CLI_WALKTHROUGH = """\
# 1. Create memory (no strategies needed for direct record CRUD).
aws bedrock-agentcore-control create-memory \\
  --region "$AWS_REGION" --name "BatchCli-$(date +%s)" \\
  --event-expiry-duration 30 --client-token "$(uuidgen)"
export MEMORY_ID=<id>

# 2. BatchCreate — insert records you extracted yourself
aws bedrock-agentcore batch-create-memory-records \\
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \\
  --records '[
    {"requestIdentifier":"note-lang","namespaces":["/users/user-alex/notes/"],
     "timestamp":"'"$(date +%s)"'",
     "content":{"text":"Alex prefers Python over Java."}},
    {"requestIdentifier":"note-city","namespaces":["/users/user-alex/notes/"],
     "timestamp":"'"$(date +%s)"'",
     "content":{"text":"Alex is based in Berlin."}}
  ]'
# Capture memoryRecordId values from the response.

# 3. BatchUpdate
aws bedrock-agentcore batch-update-memory-records \\
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \\
  --records '[{"memoryRecordId":"<id>","content":{"text":"updated text"}}]'

# 4. BatchDelete
aws bedrock-agentcore batch-delete-memory-records \\
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \\
  --records '[{"memoryRecordId":"<id>"}]'

# 5. Teardown
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

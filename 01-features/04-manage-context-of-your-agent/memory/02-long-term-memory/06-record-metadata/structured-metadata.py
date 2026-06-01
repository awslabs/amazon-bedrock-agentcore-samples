"""Structured metadata on memory records.

What you learn:
    - Attach metadata when calling BatchCreateMemoryRecords
    - Filter retrieval with metadataFilters on RetrieveMemoryRecords
    - Use indexedKeys on CreateMemory to declare filterable keys

Use record metadata for hard constraints (region, tier, source, language)
that should be enforced at the index, not in the LLM prompt.

Two surfaces:
    python structured-metadata.py boto3
    python structured-metadata.py sdk

Add `--cleanup` to delete the memory resource at the end. By default the
memory is kept so you can inspect it; the script prints the memoryId.

SDK note: `indexedKeys` on CreateMemory is not yet exposed by MemoryClient —
please use the boto3 API to set it.

Prerequisites:
    pip install boto3 bedrock-agentcore
    export AWS_REGION=us-east-1   # use any AgentCore-supported region
"""

import os
import sys
import time
import uuid

REGION = os.getenv("AWS_REGION", "us-east-1")
ACTOR_ID = "tenant-acme"
NAMESPACE = f"/tenants/{ACTOR_ID}/notes/"


def _records() -> list[dict]:
    return [
        {
            "requestIdentifier": "rec-eu-premium",
            "content": {"text": "Acme prefers GDPR-compliant data residency."},
            "namespaces": [NAMESPACE],
            "timestamp": str(int(time.time())),
            "metadata": {
                "region": {"stringValue": "EU"},
                "tier": {"stringValue": "premium"},
            },
        },
        {
            "requestIdentifier": "rec-us-basic",
            "content": {"text": "Acme has a US billing address."},
            "namespaces": [NAMESPACE],
            "timestamp": str(int(time.time())),
            "metadata": {
                "region": {"stringValue": "US"},
                "tier": {"stringValue": "basic"},
            },
        },
        {
            "requestIdentifier": "rec-eu-basic",
            "content": {"text": "Acme support tickets are routed to the Berlin team."},
            "namespaces": [NAMESPACE],
            "timestamp": str(int(time.time())),
            "metadata": {
                "region": {"stringValue": "EU"},
                "tier": {"stringValue": "basic"},
            },
        },
    ]


# === boto3 ============================================================
def run_with_boto3(cleanup: bool = False) -> None:
    import boto3

    control = boto3.client("bedrock-agentcore-control", region_name=REGION)
    data = boto3.client("bedrock-agentcore", region_name=REGION)

    memory_id = control.create_memory(
        name=f"RecordMetadata_{int(time.time())}",
        description="Structured metadata (boto3)",
        eventExpiryDuration=30,
        indexedKeys=[
            {"key": "region", "type": "STRING"},
            {"key": "tier", "type": "STRING"},
        ],
    )["memory"]["id"]
    print(f"[boto3] Created memory {memory_id}")
    deadline = time.time() + 300
    while time.time() < deadline:
        if control.get_memory(memoryId=memory_id)["memory"]["status"] == "ACTIVE":
            break
        time.sleep(5)

    resp = data.batch_create_memory_records(memoryId=memory_id, records=_records())
    print(f"[boto3] Created {len(resp.get('successfulRecords', []))} records")

    hits = data.retrieve_memory_records(
        memoryId=memory_id,
        namespace=NAMESPACE,
        searchCriteria={
            "searchQuery": "Acme",
            "topK": 10,
            "metadataFilters": [
                {
                    "left": {"metadataKey": "region"},
                    "operator": "EQUALS_TO",
                    "right": {"metadataValue": {"stringValue": "EU"}},
                }
            ],
        },
    )["memoryRecordSummaries"]
    print(f"\n[boto3] EU-only results ({len(hits)}):")
    for h in hits:
        print(f"  - {h['content']['text']} | meta={h.get('metadata')}")

    if cleanup:
        control.delete_memory(memoryId=memory_id, clientToken=str(uuid.uuid4()))
        print(f"\n[boto3] Deleted memory {memory_id}")
    else:
        print(f"\n[boto3] Keeping memory {memory_id} (pass --cleanup to delete)")


# === AgentCore SDK ====================================================
# create_memory_and_wait does not expose indexedKeys, so reach the wrapped
# control-plane client for CreateMemory. The data-plane calls
# (batch_create_memory_records, retrieve_memory_records) are forwarded by
# MemoryClient via __getattr__ and used directly.
def run_with_sdk(cleanup: bool = False) -> None:
    from bedrock_agentcore.memory import MemoryClient

    client = MemoryClient(region_name=REGION)

    cp = client.gmcp_client  # control plane (for indexedKeys)
    memory_id = cp.create_memory(
        name=f"RecordMetadataSdk_{int(time.time())}",
        description="Structured metadata (SDK)",
        eventExpiryDuration=30,
        indexedKeys=[
            {"key": "region", "type": "STRING"},
            {"key": "tier", "type": "STRING"},
        ],
    )["memory"]["id"]
    print(f"[sdk] Created memory {memory_id}")
    deadline = time.time() + 300
    while time.time() < deadline:
        if cp.get_memory(memoryId=memory_id)["memory"]["status"] == "ACTIVE":
            break
        time.sleep(5)

    resp = client.batch_create_memory_records(memoryId=memory_id, records=_records())
    print(f"[sdk] Created {len(resp.get('successfulRecords', []))} records")

    hits = client.retrieve_memory_records(
        memoryId=memory_id,
        namespace=NAMESPACE,
        searchCriteria={
            "searchQuery": "Acme",
            "topK": 10,
            "metadataFilters": [
                {
                    "left": {"metadataKey": "region"},
                    "operator": "EQUALS_TO",
                    "right": {"metadataValue": {"stringValue": "EU"}},
                }
            ],
        },
    )["memoryRecordSummaries"]
    print(f"\n[sdk] EU-only results ({len(hits)}):")
    for h in hits:
        print(f"  - {h['content']['text']} | meta={h.get('metadata')}")

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

"""Structured metadata on memory records.

What you learn:
    - Attach metadata when calling BatchCreateMemoryRecords
    - Filter retrieval with metadataFilters on RetrieveMemoryRecords
    - Use indexedKeys on CreateMemory to declare filterable keys

Use record metadata for hard constraints (region, tier, source, language)
that should be enforced at the index, not in the LLM prompt.

Three surfaces:
    python structured-metadata.py boto3
    python structured-metadata.py sdk    # documents the SDK gap
    python structured-metadata.py cli

SDK note: MemoryClient does not expose `indexedKeys=` on CreateMemory or
batch record APIs. Use the wrapped boto3 client (`client.gmcp_client`) or
boto3 directly for record-metadata workflows.

Prerequisites:
    pip install boto3 bedrock-agentcore
    export AWS_REGION=us-east-1
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
def run_with_boto3() -> None:
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
        memoryId=memory_id, namespace=NAMESPACE,
        searchCriteria={
            "searchQuery": "Acme", "topK": 10,
            "metadataFilters": [{
                "left": {"metadataKey": "region"},
                "operator": "EQUALS_TO",
                "right": {"metadataValue": {"stringValue": "EU"}},
            }],
        },
    )["memoryRecordSummaries"]
    print(f"\n[boto3] EU-only results ({len(hits)}):")
    for h in hits:
        print(f"  - {h['content']['text']} | meta={h.get('metadata')}")

    control.delete_memory(memoryId=memory_id, clientToken=str(uuid.uuid4()))
    print(f"\n[boto3] Deleted memory {memory_id}")


# === AgentCore SDK ====================================================
# MemoryClient.create_memory_and_wait does not expose indexedKeys, and
# there is no batch_create_memory_records helper. Use gmcp_client for
# CreateMemory + boto3-shaped batch calls, or use the boto3 path directly.
def run_with_sdk() -> None:
    print(
        "[sdk] Record metadata is not exposed by MemoryClient helpers.\n"
        "      - indexedKeys: not on create_memory_and_wait\n"
        "      - batch_create_memory_records: no helper\n"
        "      - metadataFilters on retrieve_memories: not exposed\n"
        "      Use boto3 directly (see run_with_boto3) or call methods on\n"
        "      client.gmcp_client.* with the boto3-shaped kwargs."
    )


# === AWS CLI ==========================================================
CLI_WALKTHROUGH = """\
# 1. Create memory and declare indexedKeys (cannot be removed later).
aws bedrock-agentcore-control create-memory \\
  --region "$AWS_REGION" --name "RecordMetaCli-$(date +%s)" \\
  --event-expiry-duration 30 --client-token "$(uuidgen)" \\
  --indexed-keys '[
    {"key":"region","type":"STRING"},
    {"key":"tier","type":"STRING"}
  ]'
export MEMORY_ID=<id>

# 2. Batch-create records with metadata
aws bedrock-agentcore batch-create-memory-records \\
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \\
  --records '[
    {
      "requestIdentifier":"rec-eu-premium",
      "content":{"text":"Acme prefers GDPR-compliant data residency."},
      "namespaces":["/tenants/tenant-acme/notes/"],
      "timestamp":"'"$(date +%s)"'",
      "metadata":{"region":{"stringValue":"EU"},"tier":{"stringValue":"premium"}}
    }
  ]'

# 3. Retrieve filtered to region=EU
aws bedrock-agentcore retrieve-memory-records \\
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \\
  --namespace "/tenants/tenant-acme/notes/" \\
  --search-criteria '{
    "searchQuery":"Acme",
    "topK":10,
    "metadataFilters":[{
      "left":{"metadataKey":"region"},
      "operator":"EQUALS_TO",
      "right":{"metadataValue":{"stringValue":"EU"}}
    }]
  }'

# 4. Teardown
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

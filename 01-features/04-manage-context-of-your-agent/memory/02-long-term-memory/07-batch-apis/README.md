# Batch APIs for memory records

Three data-plane APIs for direct CRUD on memory records, bypassing the strategy extraction pipeline:

| API | Purpose |
|---|---|
| `BatchCreateMemoryRecords` | Insert pre-extracted records (up to 100 per call) |
| `BatchUpdateMemoryRecords` | Overwrite content on existing records |
| `BatchDeleteMemoryRecords` | Remove records by id |

Each call reports per-record success and failure independently — partial success is the norm, so always inspect `successfulRecords` and `failedRecords`.

## What you learn

- Insert records you've extracted yourself (e.g. from a self-managed strategy worker)
- Update record content in place by `memoryRecordId`
- Delete records by id without touching the underlying events

## Run

```bash
pip install boto3 bedrock-agentcore
python batch-create-update-delete.py boto3   # default — direct service calls
python batch-create-update-delete.py sdk     # documents the SDK gap (no batch CRUD helpers)
```

## When to use

- **Self-managed strategy** — your worker has extracted records out-of-band and writes them back via `BatchCreateMemoryRecords`.
- **Back-fills and migrations** — load records from another store into a new memory resource.
- **Admin tooling** — surgical edits or deletions for compliance (right-to-be-forgotten, redaction).

## Best practices

- **Always pass `requestIdentifier`** on creates — it is your client-side key for mapping responses back to your own data, and it makes the call idempotent.
- **Inspect `failedRecords`** on every batch call. The API returns 200 even when individual records fail.
- **Cap at 100 records per call** — split larger workloads into chunks and parallelize.
- **Don't use these APIs to bypass extraction unintentionally.** If you want extraction, use `CreateEvent` with a strategy attached. Batch CRUD is for cases where you've already done the extraction yourself.
- **Updates are full overwrites** of `content.text`. There is no patch semantics.

## AWS CLI walkthrough

The same flow expressed with the AWS CLI:

```bash
# 1. Create memory (no strategies needed for direct record CRUD).
aws bedrock-agentcore-control create-memory \
  --region "$AWS_REGION" --name "BatchCli-$(date +%s)" \
  --event-expiry-duration 30 --client-token "$(uuidgen)"
export MEMORY_ID=<id>

# 2. BatchCreate — insert records you extracted yourself
aws bedrock-agentcore batch-create-memory-records \
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \
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
aws bedrock-agentcore batch-update-memory-records \
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \
  --records '[{"memoryRecordId":"<id>","content":{"text":"updated text"}}]'

# 4. BatchDelete
aws bedrock-agentcore batch-delete-memory-records \
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \
  --records '[{"memoryRecordId":"<id>"}]'

# 5. Teardown
aws bedrock-agentcore-control delete-memory \
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" --client-token "$(uuidgen)"
```

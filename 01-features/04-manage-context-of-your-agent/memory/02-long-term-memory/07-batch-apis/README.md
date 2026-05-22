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
python batch-create-update-delete.py cli     # print equivalent AWS CLI commands
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

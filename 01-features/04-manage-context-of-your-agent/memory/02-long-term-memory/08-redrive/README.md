# Redriving failed extractions

Long-term extraction runs asynchronously after `CreateEvent`. When extraction fails — model throttle, transient error, malformed payload — AgentCore records the attempt as an **extraction job** with `status=FAILED` and a `failureReason`. You can list those jobs and redrive them with `StartMemoryExtractionJob`.

## What you learn

- Use `ListMemoryExtractionJobs` with `filter.status=FAILED` to find what broke
- Inspect `failureReason`, `actorId`, `sessionId`, `strategyId` to triage
- Use `StartMemoryExtractionJob` to redrive a job by id

## Run

```bash
pip install boto3 bedrock-agentcore
export MEMORY_ID=mem_abcdef123
python redrive-failed-extractions.py boto3   # default — direct service calls
python redrive-failed-extractions.py sdk     # documents the SDK gap (no list/start extraction job helpers)
```

The script lists failed jobs, prints their failure reasons, and redrives each one. In a real deployment you'd gate the redrive on a deliberate fix.

## When to redrive vs. investigate first

| Symptom | Action |
|---|---|
| Model throttle / `ThrottlingException` in `failureReason` | Safe to redrive after a delay; consider provisioned throughput. |
| `AccessDeniedException` on the strategy's model | Fix IAM / Bedrock model access first, then redrive. |
| Validation error on payload structure | Don't redrive — the payload is bad. Delete the event or fix it. |
| Unknown / generic service error | Open a support case before redriving in bulk. |

## Best practices

- **Filter by `status=FAILED`** when listing — the unfiltered list includes successful jobs you don't care about.
- **Read `failureReason` before redriving.** A blind retry on a deterministic failure just burns tokens and produces the same error.
- **Throttle redrives.** If you have hundreds of failed jobs, space them out — the underlying cause may be capacity-related.
- **Combine with the streaming primitive.** Subscribe to `MemoryRecordCreated` events to confirm the redrive actually produced records.
- **Job ids are stable.** A redrive uses the same `jobId`; you can correlate before/after via `ListMemoryExtractionJobs`.

## AWS CLI walkthrough

The same flow expressed with the AWS CLI:

```bash
# 1. List failed extraction jobs for a memory.
aws bedrock-agentcore list-memory-extraction-jobs \
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \
  --filter '{"status":"FAILED"}'

# 2. Inspect the failureReason for each job before deciding to redrive.
#    Common reasons: ThrottlingException (model), AccessDenied (role), validation.

# 3. Redrive a single job. Only do this after fixing the underlying issue.
aws bedrock-agentcore start-memory-extraction-job \
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \
  --extraction-job '{"jobId":"<jobId-from-list>"}'

# 4. Confirm the job left the FAILED set.
aws bedrock-agentcore list-memory-extraction-jobs \
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \
  --filter '{"status":"FAILED"}'
```

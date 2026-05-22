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
python redrive-failed-extractions.py cli     # print equivalent AWS CLI commands
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

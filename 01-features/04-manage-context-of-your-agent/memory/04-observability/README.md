# Observability

AgentCore Memory emits CloudWatch metrics and logs to your account so you can monitor data-plane usage, ingestion health, and stream delivery.

## What you learn

- Read CloudWatch metrics under the `AWS/Bedrock-AgentCore` namespace
- Alarm on stream publishing failures
- Tail the per-memory ingestion log group when log delivery is enabled

## Run

```bash
export MEMORY_ARN=arn:aws:bedrock-agentcore:us-east-1:111122223333:memory/mem-abc
python observability.py
```

## What's emitted

### Data-plane metrics

`Invocations`, `Latency`, `Errors` for each data-plane operation (`CreateEvent`, `RetrieveMemoryRecords`, etc.) — scoped per memory resource.

### Ingestion metrics

`Invocations`, `Latency`, `Errors`, `NumberOfMemoryRecords` for extraction and consolidation — scoped per memory resource and strategy.

### Streaming metrics

| Metric | Meaning |
|---|---|
| `StreamPublishingSuccess` | Events successfully published to your Kinesis stream |
| `StreamPublishingFailure` | Events that failed to publish (transient + terminal) |
| `StreamUserError` | Failures caused by config issues (IAM, KMS key state) |

All three are emitted as `Count` units with dimensions `Operation=MemoryStreamEvent` and `Resource=<memory ARN>`.

### Logs

When log delivery is enabled on the memory resource, ingestion errors land in `/aws/bedrock-agentcore/memory/<memoryId>`. Streaming terminal failures include `streamArn`, `errorCode`, `errorMessage`, `eventType`, and `memoryRecordId` fields.

## Best practices

- **Alarm on `StreamPublishingFailure` and `StreamUserError`.** Treat user errors as page-worthy — they almost always mean broken IAM or KMS.
- **Watch `Errors` on `RetrieveMemoryRecords`.** A spike usually means a strategy was deleted or a namespace renamed.
- **Track `NumberOfMemoryRecords` per strategy.** A sudden drop is the canary for an extraction regression.
- **Enable log delivery in production.** Without it, ingestion failures are invisible — metrics will tell you something broke, only logs tell you what.
- **Pair alarms with a runbook.** Streaming failures usually want a redrive on the affected events; user errors want an IAM fix.

# Memory record streaming

Push-based delivery of memory record lifecycle events to an Amazon Kinesis Data Stream. Subscribe to changes instead of polling — sync memory to a data lake, trigger downstream workflows, or build event-driven personalization.

## What you learn

- Create a Kinesis Data Stream and an IAM role AgentCore can assume
- Wire `streamDeliveryResources` into `CreateMemory`
- Choose between `FULL_CONTENT` and `METADATA_ONLY` delivery
- Consume the three lifecycle event types: `MemoryRecordCreated`, `MemoryRecordUpdated`, `MemoryRecordDeleted`
- Read events from a shard via `GetShardIterator` + `GetRecords` (production should use Lambda or KCL)

## Run

```bash
pip install boto3 bedrock-agentcore
python record-streaming.py boto3   # default — direct service calls
python record-streaming.py sdk     # MemoryClient with stream_delivery_resources kwarg
python record-streaming.py cli     # print equivalent AWS CLI commands
```

> **Cost note:** Kinesis Data Streams incur [hourly charges per shard](https://aws.amazon.com/kinesis/data-streams/pricing/). The script cleans up at the end — don't skip it.

## Event types

| Event | Trigger |
|---|---|
| `StreamingEnabled` | `CreateMemory` succeeds with stream config (validation event) |
| `MemoryRecordCreated` | Long-term extraction completes, or `BatchCreateMemoryRecords` |
| `MemoryRecordUpdated` | `BatchUpdateMemoryRecords` |
| `MemoryRecordDeleted` | `DeleteMemoryRecord`, `BatchDeleteMemoryRecords`, or consolidation |

Failures are surfaced as `StreamPublishingFailure` and `StreamUserError` metrics in CloudWatch — alarm on these in production.

## Content levels

- `FULL_CONTENT` — record text included in the event. Use when downstream consumers need to act on the content directly.
- `METADATA_ONLY` — record id + namespace + lifecycle type. Use when you only need a change signal and consumers will fetch the full record on demand. Cheaper, less sensitive data on the wire.

## Best practices

- **Scope the IAM role tightly.** Permissions should be `kinesis:PutRecords` + `kinesis:DescribeStream` on a single stream ARN — nothing broader.
- **Plan shard capacity.** One shard handles ~1000 records/sec writes. Reshard for higher write volumes; AgentCore will throttle on `ProvisionedThroughputExceeded`.
- **Prefer `METADATA_ONLY`** unless you actually need the text in transit. Reduces data exposure and Kinesis throughput cost.
- **Don't poll Kinesis from a sample script in production.** Use a Lambda event source mapping or KCL consumer with checkpointing.
- **Plan for at-least-once delivery.** Make consumers idempotent — events may be replayed on retries.
- **Alarm on `StreamPublishingFailure`.** A silent stream is the worst kind of stream.

## Where to next

The `examples/` folder shows three complete patterns built on streaming: cross-region replication, personalised recommendations, and cross-customer analytics.

# Self-managed memory strategy

You own the extraction pipeline end-to-end. AgentCore handles only storage and retrieval; the *what to extract* and *how to consolidate* logic lives in your code.

Use this when:

- You need a record schema that built-in strategies don't produce.
- You want to use a non-Bedrock model, or your own fine-tuned model.
- You must pull additional context from external systems (CRM, EHR, ticket system) before deciding what to write.

## How it works

1. You configure `selfManagedConfiguration` with a payload S3 bucket, an SNS topic, and trigger conditions.
2. As `CreateEvent` calls accumulate, AgentCore evaluates the triggers. When one fires, AgentCore:
   - Writes the conversation payload to your S3 bucket.
   - Publishes a notification to your SNS topic.
3. Your subscriber (Lambda, ECS task, etc.) reads the payload from S3, runs your extraction logic, and persists the resulting records via `BatchCreateMemoryRecords` / `BatchUpdateMemoryRecords` / `BatchDeleteMemoryRecords`.

## Trigger conditions

| Trigger | When it fires |
|---|---|
| `messageBasedTrigger.messageCount` | After N messages (1–50) |
| `tokenBasedTrigger.tokenCount` | After cumulative token count |
| `timeBasedTrigger.idleSessionTimeout` | After N seconds idle (10–3000) |

You may set multiple triggers — the strategy fires when any matches.

## Run

```bash
pip install boto3 bedrock-agentcore
export MEMORY_EXECUTION_ROLE_ARN=arn:aws:iam::<acct>:role/<role>
export PAYLOAD_BUCKET=my-agentcore-payload-bucket
export TOPIC_ARN=arn:aws:sns:<region>:<acct>:agentcore-self-managed
python self-managed-strategy.py boto3   # default — direct service calls
python self-managed-strategy.py sdk     # documents the SDK gap (no selfManagedConfiguration helper)
python self-managed-strategy.py cli     # print equivalent AWS CLI commands
```

The execution role must allow:

- `s3:PutObject` on `arn:aws:s3:::$PAYLOAD_BUCKET/*`
- `sns:Publish` on `$TOPIC_ARN`
- be assumable by `bedrock-agentcore.amazonaws.com`

A working extraction subscriber (Lambda) is provided under [`../examples/single-agent/with-strands-agent/02-custom-hook/culinary-assistant-self-managed-strategy/lambda_function.py`](../examples/single-agent/with-strands-agent/02-custom-hook/culinary-assistant-self-managed-strategy/lambda_function.py).

## Best practices

- **Tune triggers to your workload.** A chat agent may want `messageCount=10`; a long-form journaling agent may want `idleSessionTimeout=300`. Triggers fire often → cost; rarely → stale memory.
- **Keep extraction idempotent.** Triggers may overlap; design the subscriber so re-running it on the same window doesn't duplicate records (use `requestIdentifier` on `BatchCreateMemoryRecords`).
- **Use `historicalContextWindowSize`** (0–50) to control how much prior conversation AgentCore includes in the delivered payload.
- **Validate before writing.** Run a guardrail step on extracted text before persisting — it's the last point you control.
- **Watch CloudWatch metrics** under `AWS/Bedrock-AgentCore` for trigger invocations and consolidation latency.
